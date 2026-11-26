# `strata generate --cpu-oracle-q8-0`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--cpu-oracle-q8-0` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。指定すると有効 |

## 役割

CPU 上の expert 計算で、通常の activation 量子化と dot reduction の代わりに、x86 Q8_0 oracle 用の契約を選びます。モデルや重みを変更するオプションではなく、実行中の CPU expert 計算経路を切り替えます。CUDA と SYCL の `generate` 実装に同じフラグがあります。

## 使い方

```sh
# pack/full と token ID 1,2,3 を入力し、CPU expert の Q8_0 oracle 経路を選ぶ
strata generate --pack pack/full --tokens "1,2,3" --cpu-oracle-q8-0
```

`--pack` と token 入力は `generate` の別の必須・入力引数です。この例の pack は実行環境に存在するものへ置き換えてください。

## 値と既定値

値は不要です。parser はオプションを見つけると `cpu_oracle_q8_0` を `true` にし、`Options` の初期値は `false` です。したがって未指定時は従来の CPU quantizer と reduction のままです。同じフラグを複数回指定しても同じ bool を再度 `true` にするだけです。値を後置した場合、その値は別引数として解釈され、未知引数として失敗します（CUDA parser: `engine/src/program/generate.cpp:805, 3925, 4268-4273`、SYCL parser: `engine/sycl/src/program/generate.cpp:489, 1964`）。

## 実行時の動作

1. parser は設定を受理し、expert cache/profile との併用を検査した後、`expert_set_oracle_q8_0()` で CPU kernel 側のプロセス内フラグを設定します（`engine/src/program/generate.cpp:5322-5330`、`engine/src/kernels/cpu/expert_layout.cpp:400-411`。SYCL 側は `engine/sycl/src/program/generate.cpp:2736-2744`）。
2. フラグ有効時、各32要素 chunk の最大絶対値から scale を作り、FP16 に丸めた scale を使って nearest-even の整数コードを生成します。通常経路の half-away rounding と FP32 scale とは異なります（`engine/src/kernels/cpu/expert.cpp:76-111, 385-410`、型・既定契約の説明は `engine/include/strata/kernels/cpu/expert.hpp:57-67`）。
3. expert の gate/up と down 投影で oracle の row dot を使い、Q2_0 のコード offset を chunk ごとに除いた後、chunk scale と weight scale を順に積算します（`engine/src/kernels/cpu/expert.cpp:262-312, 364-376, 452-474`）。
4. CPU expert pool はこのモードで分割・複数 token 用 kernel を使わず、single-token 経路へフォールバックします（`engine/src/kernels/cpu/pool.cpp:1500-1513, 1520-1529`、`engine/src/kernels/cpu/expert.cpp:605-610`）。

ヘッダーはこの設定を worker thread 起動前に行い、request 中に変更しないこと、GPU expert cache との parity が未確立であることを記しています（`engine/include/strata/kernels/cpu/expert.hpp:111-117`）。このオプション自体によるファイル出力は確認できません。

## 適用条件と副作用

- `--expert-cache` の値が0以外、または `--expert-profile` が指定されている場合は併用できません。stderr に `--cpu-oracle-q8-0 cannot be combined with --expert-cache or --expert-profile until the GPU expert contract matches` を出し、`generate` は 2 を返します。`--expert-cache auto` も0以外の設定としてこの条件に該当します（`engine/src/program/generate.cpp:5322-5325`、SYCL: `engine/sycl/src/program/generate.cpp:2736-2739`）。
- x86 以外の通常ビルドでは、このフラグを指定すると stderr に scalar quantizer は対象契約である x86 Q8_0 ではない旨を出して 2 を返します（CUDA: `engine/src/program/generate.cpp:5370-5375`）。SYCL の該当箇所は x86 専用分岐外にあり、同じ拒否分岐は確認できません（`engine/sycl/src/program/generate.cpp:2741-2757`）。
- フラグなしでも既存の AVX2/CPU ISA 要件は別途適用されます。上記の x86 oracle quantizer は AVX 命令を使う実装です。実行可能な CPU ISA の詳細なビルド境界は、このオプション文書の調査だけでは全構成を特定できません。
- CPU カーネルのヘッダーは GPU expert cache との契約一致が未確立と明記しています。cache/profile 併用は parser 後の検証で拒否されます。

## 出力とエラー

上記の cache/profile 併用拒否と CUDA の非 x86 拒否はいずれも stderr に診断を出し、終了コード 2 を返します。フラグに値を誤って付けた場合や未知引数も、CUDA parser では `unknown argument` と usage を stderr に出し 2 を返します（`engine/src/program/generate.cpp:4268-4273`）。正常時にこのフラグ専用のメッセージを出す処理は確認できません。

## 補足

CUDA/SYCL の usage は `--native` の説明で CPU q8_0 contract が含まれる旨を示します（CUDA: `engine/src/program/generate.cpp:1257-1260`、SYCL: `engine/sycl/src/program/generate.cpp:845-849`）。ただし、この checkout の両 parser で `cpu_oracle_q8_0` を `true` にする代入は当該フラグの parser 分岐だけで、`--native` の処理による自動有効化は確認できません（CUDA: `engine/src/program/generate.cpp:3925, 5112-5125`、SYCL: `engine/sycl/src/program/generate.cpp:1964`）。そのため `--native` のみで有効になるとは扱わず、明示的にこのフラグを指定してください。

## 根拠

- `engine/src/program/generate.cpp:805, 1257-1260, 3925, 4268-4273, 5322-5375` — CUDA 実装の既定値、usage、parser、失敗経路、設定適用。
- `engine/sycl/src/program/generate.cpp:489, 845-849, 1964, 2736-2757` — SYCL 実装の parser、併用検査、設定適用、CPU 条件。
- `engine/include/strata/kernels/cpu/expert.hpp:57-67, 111-117` — activation contract、API の適用範囲と制約。
- `engine/src/kernels/cpu/expert.cpp:76-112, 262-312, 364-376, 385-410, 452-474, 605-610` — oracle quantizer、dot reduction、expert 使用箇所と multi-token fallback。
- `engine/src/kernels/cpu/expert_layout.cpp:400-411` — プロセス内 oracle フラグ。
- `engine/src/kernels/cpu/pool.cpp:1500-1513, 1520-1529` — pool の分割経路からの fallback。
