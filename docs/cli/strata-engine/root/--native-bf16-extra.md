# `--native-bf16-extra`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジン） |
| オプション | `--native-bf16-extra` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

実験的な BF16 projection 経路を PLE の value projection と shared expert の scalar gate で有効にします。`--native-bf16` が SSM/router/indexer 向けであるのに対し、このフラグは別の PLE/shared gate 用スイッチです。help では「experimental CUDA-oracle」と説明されています（`src/program/generate.cpp:844-845`）。

## 使い方

```sh
strata generate --pack ./model.pack --tokens "1,2,3" --native-bf16-extra
```

`--pack` と `--tokens` はエンジンの基本引数です。実際のモデル・実行環境で利用できるかは、対応する engine build とモデル経路に依存します。

## 値と既定値

- 値は不要です。parser はこの引数を認識すると `native_bf16_extra = true` にします。初期値は `false` なので、省略時は従来経路です（`src/program/generate.cpp:443,2488-2489`）。
- 数値や文字列の検証はありません。フラグを複数回指定しても同じ boolean を `true` にするだけです。
- 値を続けて書いてもこのフラグの値として消費されません。後続の文字列は別の引数として解析され、未知の引数ならエラーになります（`src/program/generate.cpp:2416-2421,2787-2792`）。

## 実行時の動作

engine 起動時にこの boolean が PLE と shared expert のカーネルスイッチへそれぞれ渡されます（`src/program/generate.cpp:3932-3935`）。

- **PLE:** PLE の `pre_value` がない場合、通常は activation を BF16 に変換して従来 GEMV を行います。有効時はその変換を経ず、FP32 activation と BF16 weight を使う `bf16_gemv_fp32_mmvf` に切り替えます。`pre_value` がある場合は、事前計算値をコピーする分岐が先なので、この value projection ではフラグは使われません。後続の PLE 非線形処理はこの独立スイッチでは変更しないと実装コメントに記されています（`src/kernels/cuda/ple.cu:324-333`、SYCL 移植側 `sycl/src/kernels/cuda/ple.dp.cpp:478-502`）。
- **Shared expert:** 通常は BF16 に丸めた入力を scalar gate に使います。有効時は元の FP32 hidden state と BF16 gate weight で gate を計算し、sigmoid と出力 scaling を行います（`src/kernels/cuda/shared_expert.cu:247-265,468`、SYCL 移植側 `sycl/src/kernels/cuda/shared_expert.dp.cpp:377-405,604-613`）。複数 token かつ `STRATA_DEC_BATCH` が未設定または非ゼロの場合は batched GEMV と行単位の sigmoid/scale に進みます。環境変数が `0` 相当なら token ごとの分岐です（同上）。
- `--native` プリセットを選ぶと parser が `native_bf16_extra` も含む一連の native スイッチを有効化します。このプリセットには PLE GGUF が必要で、PLE を無効にした場合や PLE weight のある shard が見つからない場合は終了コード 2 で拒否されます（`src/program/generate.cpp:3247-3267`）。

## 適用条件と副作用

このフラグ単独について parser 段階の GPU 機能検査や、別フラグとの必須組み合わせ検査はありません。フラグをセットしても、実際に PLE value projection / shared expert gate が呼ばれる推論経路でなければ効果はありません。PLE の `pre_value` 分岐では上記の通り切り替わりません。

実行時には GPU 上の BF16 GEMV および gate 後処理カーネルを選択します。数値経路を変更する実験用スイッチであり、速度や精度の改善を保証する測定根拠はこの調査では確認していません。CUDA 実装と SYCL 移植実装を確認しましたが、全 GPU・backend での利用可否、Release 配布物への収録状況は確認していません。

## 出力とエラー

このオプション自体に専用の stdout/stderr 出力や option-specific な parser validation はありません。未知の引数は `unknown argument: <引数>` を stderr に出し、usage を表示して終了コード 2 になります（`src/program/generate.cpp:2787-2792`）。実行中の kernel 失敗は各 CUDA/SYCL 経路の実行時処理に委ねられ、このフラグ固有のエラーメッセージや終了コードは確認できませんでした。

## 根拠

- option の既定値・help・parser: `src/program/generate.cpp:443,844-845,2488-2489`
- native preset による自動有効化と PLE 条件: `src/program/generate.cpp:3247-3267`
- PLE / shared expert への伝播: `src/program/generate.cpp:3932-3935`
- PLE value projection: `src/kernels/cuda/ple.cu:324-333`; SYCL 移植側 `sycl/src/kernels/cuda/ple.dp.cpp:478-502`
- shared expert gate と batch 条件: `src/kernels/cuda/shared_expert.cu:247-265,468`; SYCL 移植側 `sycl/src/kernels/cuda/shared_expert.dp.cpp:377-405,604-613`
- 未知引数の失敗経路: `src/program/generate.cpp:2787-2792`
