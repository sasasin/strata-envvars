# `strata generate --native-ple-postops`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--native-ple-postops` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

PLE（per-layer token embedding）の投影後に行う正規化、ゲート、畳み込み、残差演算で、既定の処理に代えて pinned native arithmetic を選びます。実験的なオプションです。キーと値の射影方法を選ぶオプションとは独立しています。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --native-ple-postops
```

`--tokens` はカンマ区切りのトークン ID です。実際に使用する pack の PLE 設定に合わせて `--pack` を指定してください。

## 値と既定値

値を取らず、指定すると内部フラグを `true` にします。既定値は `false` です。短縮別名、数値や文字列の引数、値の範囲検証はありません。パーサは同じ指定を複数回受けても真偽値を再設定します（`engine/src/program/generate.cpp:803,3923`）。

## 実行時の動作

`strata generate` はセッション初期化前にこの値を PLE カーネル設定へ渡します（`engine/src/program/generate.cpp:6141-6142`）。PLE ブロックでは、フラグが有効な場合に native postops カーネルを呼び、無効時の個別カーネル列を通りません。対象の処理はキーと query の正規化、ゲート、ゲート値の適用、畳み込み入力の正規化、履歴畳み込み、残差加算です（CUDA: `engine/src/kernels/cuda/ple.cu:322-354`、SYCL: `engine/sycl/src/kernels/cuda/ple.dp.cpp:522-529`）。

設定はセッションのグラフ capture より前に行われ、すでに capture 済みのグラフには反映されません（`engine/include/strata/kernels/ple.hpp:38-42`）。`--native` プリセットを使う場合は、このフラグも自動で有効になります（`engine/src/program/generate.cpp:5155-5164`）。

キー射影の `--native-ple-key` や値射影の native BF16 設定とは独立です。ここで切り替えるのは postprojection arithmetic です（`engine/include/strata/kernels/ple.hpp:38-42`、`engine/src/kernels/cuda/ple.cu:327-354`）。

## 適用条件と副作用

PLE を無効にする `--no-ple` と併用できません。併用すると `stderr` に `strata generate: --native-ple-postops requires PLE enabled` を出し、終了コード `2` で終了します（`engine/src/program/generate.cpp:5209-5211`）。通常は PLE が有効であることに加え、`--no-ple` を指定しない場合は PLE を含む pack（または `--ple-gguf`）が必要です（`engine/src/program/generate.cpp:5213-5215`）。

このフラグによる追加のファイル・ネットワーク操作はありません。PLE の GPU 演算経路を選びます。help 表示では experimental とされています（`engine/src/program/generate.cpp:1255`）。ソースからは、対応する実行環境やモデルごとの性能差までは確認できません。

## 出力とエラー

フラグ自体の有効化を知らせる出力は確認できません。`--no-ple` との併用時は上記の `stderr` メッセージと終了コード `2` になります。native カーネルの実行時エラーについて、フラグ固有の CLI エラー文や終了コードは特定できませんでした。

## 根拠

- `engine/src/program/generate.cpp:803,3923` — 既定値とフラグのパーサ登録。
- `engine/src/program/generate.cpp:1208-1214,1255` — `strata generate` の usage とオプションの help 表示。
- `engine/src/program/generate.cpp:5155-5164,5205-5215,6141-6142` — `--native` との関係、PLE 無効時の検証、カーネル設定を行う時点。
- `engine/include/strata/kernels/ple.hpp:38-42` — native postops の対象、既定値、グラフ capture との関係、射影設定との独立性。
- `engine/src/kernels/cuda/ple.cu:322-354` — CUDA PLE ブロックでの分岐と既定処理。
- `engine/sycl/src/kernels/cuda/ple.dp.cpp:522-529` — SYCL PLE ブロックでの native postops 呼び出し。
