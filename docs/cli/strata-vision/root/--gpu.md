# `--gpu`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision`（`strata-vision-hip` / `strata-vision-sycl` を含む） |
| オプション | `--gpu` |
| 別名 | なし |
| 値 | 取らないフラグ。省略時は CPU 読み込み。 |

## 役割

画像 encoder（vision tower）の実行先を GPU に切り替えます。GPU 対応としてビルドされた reader で指定すると、画像 encoder の重みを GPU にロードし、起動時の warm-up と以後の画像 embedding 計算を GPU で行います。GPU 番号や複数 GPU の指定機能ではなく、実際に使うデバイスはビルドと実行環境に依存します。

## 使い方

```sh
# サーバーから使う GPU 対応の画像 reader を起動する例（起動後は ENC / QUIT の入力を待つ）
strata-vision --mmproj /path/to/mmproj.gguf --gpu
```

`--mmproj` は必須です。`strata-vision` は常駐 reader として標準入力から `ENC <画像パス> <出力パス>` または `QUIT` を受け付けます。サーバーは設定で GPU reader を選んだとき `--gpu` を付けて起動します。

## 値と既定値

- 値・別名はありません。parser は引数が `--gpu` と完全一致した場合に内部フラグを真にします。省略時の初期値は `false` です。
- `--gpu 0` のように値を続けても GPU 番号としては解釈せず、余分な `0` は未知引数エラーになります。繰り返し指定は同じ真偽値を再設定します。
- `--mmproj` が空または省略なら usage を標準エラーへ出して終了コード 2 です。未知引数も標準エラーへ出し、コード 2 で終了します。

## 実行時の動作

`--gpu` がない場合、CUDA/HIP の GPU が reader から見えないよう `CUDA_VISIBLE_DEVICES` と `HIP_VISIBLE_DEVICES` を `-1` に設定してから reader を実行します。指定した場合はこの CPU 用のマスクを設定せず、GPU 対応 reader が GPU backend を初期化します。reader は GPU index `0` を渡して重みをロードします。このオプション自体にデバイス番号の構文はありません。

ビルドによって GPU backend は異なります。CUDA、HIP、SYCL、macOS の Metal が別々のビルド設定で組み込まれ、HIP / SYCL はそれぞれ `strata-vision-hip` / `strata-vision-sycl` という実行名になります。GPU 対応なしのビルドでは、フラグを受理しても reader は `ERR this build has no GPU backend for the own tower` を標準出力へ出し、終了コード 3 で失敗します。

HIP reader は起動前に GPU の有無と、検出した GPU architecture がビルド対象に含まれるかを確認します。不一致時は kernel 実行前に `ERR` 行を出してコード 3 で終了します（`STRATA_VISION_ARCH_CHECK=0` はこの architecture 確認を省略します）。また GPU reader は attention head size が 96 を超える encoder を拒否し、reader の GPU 初期化・重みロード・warm-up が失敗した場合も `ERR` を出して起動を中止します。

## 適用条件と副作用

- GPU 処理には GPU backend を含むビルドと利用可能な対応デバイスが必要です。reader は起動時に encoder を GPU にロードし、最大 4096 image tokens の画像を使って warm-up するため、起動時に GPU メモリを確保します。より大きな token limit の画像では後続処理で buffer が拡張されます。
- サーバー経由では GPU reader の起動に失敗すると、CPU reader が用意されている構成ではサーバーが CPU reader に切り替えて続行します。直接起動した場合は reader 自身のエラー終了となり、同じ自動切り替えはありません。
- サーバーは `--gpu` を画像 reader の設定から付与します。サーバー設定の `gpu` が真なら起動引数に追加し、偽なら追加しません。

## 出力とエラー

- 起動成功時は標準出力に `READY <次元> own` を出します。サーバーは GPU reader の `ERR` 応答や起動失敗を検出して CPU fallback を試みます。
- GPU reader の encoder・デバイス・warm-up の失敗は、通常 `ERR <理由>` を標準出力に出して非 0 で終了します。GPU backend なし、GPU が見つからない、HIP architecture 不一致はコード 3、encoder の形式・ロードや warm-up の失敗はコード 1 です。
- 引数エラーと `--mmproj` 不足は標準エラーに表示され、終了コード 2 です。

## 根拠

- `terminal/tools/vision/strata_vision.cpp:56-72` — option parser、既定値を持つ設定の生成、値を取らない `--gpu`。
- `terminal/tools/vision/strata_vision.cpp:91-125` — 未知引数・必須 `--mmproj` のエラー、CPU 時の device visibility 設定、HIP の device / architecture 検証。
- `terminal/tools/vision/own/own_reader.h:14-20` — `gpu` の初期値 `false` と reader 設定。
- `terminal/tools/vision/own/own_reader.cpp:52-80, 91-118` — GPU backend がない場合の失敗、GPU reader の選択・device 0 へのロード、head size 制限、warm-up とエラー応答。
- `terminal/tools/vision/CMakeLists.txt:25-39, 77-98`、`terminal/tools/vision/own/CMakeLists.txt:120-163` — CUDA / HIP / SYCL / Metal backend と実行名のビルド条件。
- `terminal/serve/server.py:2967-2975, 3017-3029` — CPU fallback の用意、設定に基づく `--gpu` の付与。
- `terminal/serve/server.py:3042-3057, 3130-3147` — GPU reader 起動失敗時の CPU reader への切り替えと起動応答の処理。
