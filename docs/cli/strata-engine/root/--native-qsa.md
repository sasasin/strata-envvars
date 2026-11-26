# `strata --native-qsa`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。内部 usage は `strata generate`） |
| オプション | `--native-qsa` |
| 別名 | なし |
| 値 | 値なしのフラグ |

## 役割

QSA attention の一部演算を native QSA kernel に切り替える実験用フラグです。重み付き RMSNorm と attention 出力 gate が対象で、QSA の attention 全体や indexer key cache/pooling を切り替えるものではありません。後者は別オプション `--native-qsa-indexer` の対象です。CUDA/HIP 系 parser と SYCL parser の両方に同じフラグがあります（`engine/src/program/generate.cpp:3920-3921`、`engine/sycl/src/program/generate.cpp:1959-1960`）。

## 使い方

```sh
# 通常の pack と token 入力に native QSA の norm / gate を適用する
strata --pack pack/full --tokens "1,2,3" --native-qsa
```

この例はエンジン parser の `--pack` と `--tokens` を併記しています。実際の pack と token ID は利用するモデル・入力に合わせてください（usage: `engine/src/program/generate.cpp:1208-1214`）。

## 値と既定値

値を取りません。parser は `--native-qsa` を見つけると `native_qsa` を `true` にし、フラグを指定しない場合の初期値は `false` です（`engine/src/program/generate.cpp:786-787,3920-3921`）。SYCL 側も同じ初期値と代入です（`engine/sycl/src/program/generate.cpp:470-471,1959-1960`）。複数回指定した場合も同じ真偽値を再設定するだけです。フラグ固有の値 validation はありません。

## 実行時の動作

起動時に設定値を native QSA kernel の有効状態へ渡します（CUDA/HIP 系: `engine/src/program/generate.cpp:6121`、SYCL: `engine/sycl/src/program/generate.cpp:3236`）。通常の QSA 層では、Q/K の重み付き RMSNorm を native 実装へ送り、attention 出力の gate も native 実装へ送ります。無効時はそれぞれ既存の `rms_norm_weighted` と `qsa_gate_apply_f32` を使います（`engine/src/core/layer.cpp:1154-1159,1317-1323`、SYCL: `engine/sycl/src/core/layer.cpp:1182-1187,1344-1350`）。decode verify 経路にも同様の分岐があり、native flag と別途 native RoPE が有効な条件では RMSNorm と RoPE を融合する経路も選べます（`engine/src/core/verify.cpp:2028-2041,2592-2603`）。

CUDA 実装では norm は F32 入力・重みを読み、RMSNorm の後に重みを乗算します。gate は query の gate 半分に sigmoid を適用し attention 出力に乗算します（`engine/src/kernels/cuda/native_qsa.cu:80-101`）。SYCL 実装にも同様の norm/gate kernel があります（`engine/sycl/src/kernels/cuda/native_qsa.dp.cpp:90-124`）。

`--native` はモデルの native preset 処理中に `native_qsa` と `native_qsa_indexer` をともに有効化します。この preset は追加のモデル shard / PLE 要件も持ちますが、これは `--native-qsa` 単独の要件ではありません（`engine/src/program/generate.cpp:5155-5164`、SYCL: `engine/sycl/src/program/generate.cpp:2588-2596`）。

## 適用条件と副作用

- フラグはプロセス起動時の engine parser で処理され、通常の QSA 層と verify の QSA 演算に適用されます。QSA 以外の層に対するスイッチではありません（`engine/src/core/layer.cpp:1154-1159,1317-1323`、`engine/src/core/verify.cpp:2028-2041,2592-2603`）。
- `--native-qsa-indexer` は独立した設定値として保持・適用されます。`--native-qsa` だけでは indexer cache/pooling を native 化しません（`engine/src/program/generate.cpp:786-787,3920-3921,6121-6122`）。
- native kernel の実行時検査では、列数・行数が正で積が `INT_MAX` 以下、epsilon が有限かつ非負、stream とポインタが有効かつ 4-byte 整列、重み領域と他領域が重ならないことを要求します。入力と出力は完全一致の in-place alias を許します（CUDA: `engine/src/kernels/cuda/native_qsa.cu:103-121,133-165`。SYCL の検査: `engine/sycl/src/kernels/cuda/native_qsa.dp.cpp:126-144,174-179`）。通常経路は内部でこれらの引数を用意しますが、実行環境での kernel 成否や性能はソース調査だけでは確認していません。
- ファイル・ネットワーク・子プロセスを操作する副作用は、このフラグの処理では確認できません。効果は GPU 演算経路の切り替えです。

## 出力とエラー

フラグ自体に専用の出力・警告・拒否条件はありません。未知の引数は stderr に `unknown argument` と usage を出して終了コード 2 になります（`engine/src/program/generate.cpp:4268-4273`）。native QSA kernel の引数検査は `std::invalid_argument` を投げます。QSA layer の norm/gate 呼び出しは例外を `err` に移して失敗を返します（`engine/src/core/layer.cpp:1161-1163,1320-1323`）。SYCL runtime の非同期エラーがどの時点で利用者向け出力になるかは、この文書のソース範囲からは確定できません。

## 根拠

- parser、既定値、help 表示: `engine/src/program/generate.cpp:786-787,1252-1253,3920-3921`。同じ option を持つ SYCL parser: `engine/sycl/src/program/generate.cpp:470-471,840-841,1959-1960`。
- native 状態の適用と `--native` との相互作用: `engine/src/program/generate.cpp:5155-5164,6121-6122`、`engine/sycl/src/program/generate.cpp:2588-2596,3236-3237`。
- CUDA/HIP 系での QSA norm / gate 分岐と例外経路: `engine/src/core/layer.cpp:1154-1163,1317-1326`。verify 経路: `engine/src/core/verify.cpp:2028-2041,2592-2603`。
- native kernel の計算と入力検査: `engine/src/kernels/cuda/native_qsa.cu:80-101,103-165`。SYCL 実装: `engine/sycl/src/kernels/cuda/native_qsa.dp.cpp:90-124,126-144,171-179,269-288`。
- 対象範囲は調査開始時点の checkout の engine parser・QSA layer/verify・CUDA/SYCL native QSA 実装です。既存バイナリの help は実行していません。
