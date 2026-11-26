# `strata generate --native-flash-attn-short`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--native-flash-attn-short` |
| 別名 | なし |
| 値 | 値を取らない boolean flag。既定値は `false` |

## 役割

QSA attention の decode 計算を通常の経路から短文脈専用の native FlashAttention 実装へ切り替える診断用フラグです。CUDA/HIP 系 parser と SYCL 系 parser の両方が受理します。実装は Q24×256 query、KV2×256、context 1〜256 などの固定形状を要求するため、任意のモデル形状や長文脈向けの汎用切替ではありません（`engine/src/kernels/cuda/native_flash_attn.cu:192-210`、`engine/sycl/src/kernels/cuda/native_flash_attn.dp.cpp:326-359`）。

## 使い方

```sh
# 事前トークン化した入力を使い、context 上限を 256 にして診断経路を有効化
strata generate --pack pack/full --tokens "1,2,3" --max-context 256 --native-flash-attn-short
```

実際の実行には利用可能なモデル pack と必要な PLE 入力など、通常の `strata generate` の前提が別途必要です。`--tokens` は必須の事前トークン化 prompt です（`engine/src/program/generate.cpp:1208-1214`）。

## 値と既定値

- オプション自体は値を取らず、指定すると `native_flash_attn_short` を `true` にします。未指定時は `false` です。繰り返し指定しても同じ boolean を true にするだけです（CUDA/HIP 系: `engine/src/program/generate.cpp:756-786,3914-3921`、SYCL 系: `engine/sycl/src/program/generate.cpp:455-470,1953-1960`）。
- `--max-context` の既定値は `4096` なので、この flag を使う場合は通常 `--max-context` も明示する必要があります（`engine/src/program/generate.cpp:758-760,1267-1268,5293-5295`）。
- flag が有効で `--max-context > 256` なら stderr に `strata generate: --native-flash-attn-short requires --max-context <=256` を出し、終了コード `2` で拒否します。加えて context は正数で、prompt と `--max-new` を収容しなければならず、満たさない場合も通常の context validation で終了コード `2` になります（`engine/src/program/generate.cpp:5217-5225,5293-5295`）。
- `--max-context` は parser で `std::atoll` により読み取られます（`engine/src/program/generate.cpp:3870-3872`）。この option 文字列には値を読む処理がありません。値らしい余分な引数は別引数として解析され、未認識なら `unknown argument` として拒否されます（`engine/src/program/generate.cpp:3919,4271`）。

## 実行時の動作

parser が設定した flag は、session 初期化前に `layer_set_native_flash_attn_short` へ渡されます（`engine/src/program/generate.cpp:6114-6116`; SYCL: `engine/sycl/src/program/generate.cpp:3228-3232`）。QSA layer は flag が無効で fast attention が有効な場合に通常の `qsa_decode_attn_step` を使います。有効時はこの分岐を外れ、必要な K/V を既存の gather 経路で作ってから `native_flash_attn_short_step` を呼びます（`engine/src/core/layer.cpp:1287-1308`; SYCL: `engine/sycl/src/core/layer.cpp:1309-1328`）。したがって `--no-fast-attn` との併用時も native short branch が選ばれます。

CUDA 実装は固定形状を検査してから既存 stream に kernel を launch し、入力 K/V を書き換えたり、この関数内で同期・メモリ確保したりしないと interface contract に記載されています（`engine/include/strata/kernels/native_flash_attn.hpp:11-30`, `engine/src/kernels/cuda/native_flash_attn.cu:192-210`）。SYCL 側も専用 kernel を launch し、FP16 device capability を要求します（`engine/sycl/src/kernels/cuda/native_flash_attn.dp.cpp:326-359`）。

## 適用条件と副作用

- `--max-context` は 1〜256 の範囲でなければなりません。さらに native kernel 側では Q24×256 / KV2×256、index block 4、top-k 256 以上、capacity 256 以上を要求します。通常の generate validation を通っても、その固定形状に合わない場合は kernel 呼び出し時の制約違反になります（`engine/src/kernels/cuda/native_flash_attn.cu:196-200`; SYCL: `engine/sycl/src/kernels/cuda/native_flash_attn.dp.cpp:330-346`）。
- `--gpu-only-full`、`--graph-only`、`--gpu-stages` とは併用できません。status validation に通常 decode loop を必要とするため、stderr に理由を出して終了コード `2` で拒否されます（`engine/src/program/generate.cpp:5297-5299`; SYCL: `engine/sycl/src/program/generate.cpp:2711-2713`）。
- native path は attention status 用の persistent storage が必要です。layer は context と storage を確認し、欠けていればエラーを返します（`engine/src/core/layer.cpp:1300-1308`; SYCL: `engine/sycl/src/core/layer.cpp:1320-1328`）。kernel が unsupported step を検出すると status を `UnsupportedStep` にして NaN output を書く契約です（`engine/include/strata/kernels/native_flash_attn.hpp:6-26`）。
- 各 decode 完了時に通常の sample 同期後、全 QSA layer の status を確認します。非ゼロ status があれば stderr に layer と position を出して終了コード `1` で停止します（`engine/src/program/generate.cpp:24410-24420`; SYCL: `engine/sycl/src/program/generate.cpp:13663-13673`）。

## 出力とエラー

- `--max-context >256`、上記の graph / GPU 診断 mode との併用は、起動前 validation の stderr と終了コード `2` です（`engine/src/program/generate.cpp:5293-5299`）。
- layer で status storage 不足、kernel launch / 呼び出し例外、status readback 失敗が起きた場合、layer はエラー文字列を返します（CUDA: `engine/src/core/layer.cpp:1300-1312`; SYCL: `engine/sycl/src/core/layer.cpp:1320-1338`）。
- decode 後の status が非ゼロなら、`strata generate: native attention status ...` を stderr に出し、終了コード `1` で停止します（`engine/src/program/generate.cpp:24413-24420`）。

## 根拠

- `engine/src/program/generate.cpp:756-786,1250-1253,3914-3921` — CUDA/HIP 系 options の既定値、help 表示、parser。
- `engine/src/program/generate.cpp:5217-5225,5293-5299,6114-6116` — context validation、併用拒否、core layer への設定。
- `engine/src/core/layer.cpp:1287-1313` — 通常 attention と native short path の切替、status readback。
- `engine/include/strata/kernels/native_flash_attn.hpp:6-34`, `engine/src/kernels/cuda/native_flash_attn.cu:192-210` — status 値・短文脈 adapter の契約と CUDA 実装。
- `engine/sycl/src/program/generate.cpp:455-470,839-841,1953-1960,2707-2713,3228-3232`、`engine/sycl/src/core/layer.cpp:1309-1340`、`engine/sycl/src/kernels/cuda/native_flash_attn.dp.cpp:326-359` — SYCL 系 parser と対応する実行経路。
