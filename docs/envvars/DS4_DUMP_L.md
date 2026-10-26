# `DS4_DUMP_L`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 用の `strata-dsv41` エンジンが、層ごとの residual stream をバイナリファイルへ記録します。通常の `strata generate` の環境変数ではなく、`STRATA_BUILD_DSV41` が有効なときにビルドされる独立実行ファイルの診断機能です。同梱の `tools/dsv41/dumpscan.py` と `dumpcmp.py` は、この形式の記録を読み取ります。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未設定 | ファイルを開かず、記録しない。 |
| 設定あり | 値全体をパスとして `fopen(path, "wb")` に渡す。数値や特定の文字列への parse はしない。 |
| 空文字、または開けないパス | `fopen` が失敗すると `dump_l` は null になり、記録しない。失敗を知らせるログやエラー処理はこの箇所にない。 |

`"wb"` で開くため、成功時は既存ファイルを上書きします。値は `Impl` のメンバー初期化時に読み取られ、同じモデル実体が存続する間は再評価されません。実行中に環境を変更しても、その実体の出力先は変わりません。

## 有効になる条件

- CMake の `STRATA_BUILD_DSV41` が有効で、かつ `STRATA_HIP_GFX906` が無効の構成でビルドされる `strata-dsv41` が対象です。オプションの既定値は OFF です。
- `DS4_DUMP_L` が設定され、指定パスを `fopen` できる必要があります。
- 推論経路によって記録地点は異なります。chunk prompt 経路と window 経路では層処理後の状態を記録します。MTP の専用経路には attention 後の記録箇所もあり、そのレコードでは layer 番号に `1000` を加えます。
- 複数メンバーで処理する経路では `mi == 0` のメンバーだけが書き込みます。

## 実行時の詳細

各レコードは、3 個の 64-bit 整数 `[layer, p0, T]` に続けて、`T * hc * dim` 個の 32-bit float を書きます。float 配列は GPU 上の residual stream をホスト vector にコピーして取得し、コピー用 stream を同期した後に出力します。複数スレッドからの記録は mutex で保護され、レコードごとに `fflush` されます。`fwrite` / `fflush` の戻り値は確認されず、書き込み途中の失敗を呼び出し側へ返す処理もありません。

同梱ツールは、各レコードの先頭 24 byte を `[layer, p0, T]` として読み、その後を float32 配列として解釈します。`dumpscan.py` は指定 position の stream を調べ、`dumpcmp.py layers` は二つのダンプ間の相対誤差を比較します。

## 根拠

- `CMakeLists.txt:800-811`: DSV41 オプションの既定値、ビルド条件、実行ファイルへの `ds4_model.cu` の組み込み。
- `src/dsv41/ds4_model.cu:1128-1130`: 環境変数の唯一の読み取り箇所、出力ファイルのオープン方法、形式の概要。
- `src/dsv41/ds4_model.cu:1231-1240`: GPU からのコピー、レコードヘッダー・データの書き込み、flush。
- `src/dsv41/ds4_model.cu:7568-7570, 7755-7757`: chunk prompt 経路での層ごとの記録。
- `src/dsv41/ds4_model.cu:8773-8777`: window 経路での記録と `mi == 0` 条件。
- `src/dsv41/ds4_model.cu:9043-9046`: MTP 経路で attention 後に `1000 + l.il` として記録。
- `tools/dsv41/dumpscan.py:22-29`, `tools/dsv41/dumpcmp.py:21-30`: 同梱ツールが読むレコード形式。

リポジトリ全体での完全一致検索では、環境変数の読み取りは `src/dsv41/ds4_model.cu` の1箇所でした。ほかの出現箇所はコメントまたは同梱解析ツールの説明です。
