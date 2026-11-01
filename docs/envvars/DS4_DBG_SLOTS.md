# `DS4_DBG_SLOTS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek-V4.1 エンジンの診断用スイッチです。Metal ビルドで条件を満たした MXFP4 レイヤーについて、常駐 expert のファイル上のバイト列と VRAM slot のバイト列を比較し、差分数と最初の差分位置を stderr に出します。モデル計算の選択や結果を切り替える設定ではありません。

## 値と判定

値の内容は parse されず、`getenv(name) != nullptr` という設定有無だけで判定されます。

| ビルド | 未設定 | 設定時（空文字を含む） |
|---|---|---|
| Metal | 無効 | 有効。`0`、`false`、その他どの文字列でも有効 |
| CUDA / HIP など Metal 以外 | 無効 | 無効。`ds4_dbg()` が定数 `false` を返す |

数値変換、範囲、無効値時の fallback はありません。CLI 引数や別の環境変数との優先順位もありません。

## 有効になる条件

- `STRATA_BUILD_DSV41=ON` で `strata-dsv41` をビルドしていること。この CMake オプションは既定で `OFF` です。
- `STRATA_METAL` が定義されたビルドであること。Metal 以外では `ds4_dbg()` は常に `false` です。
- DS4 `layer()` が実行され、対象レイヤーの `l.il < 2`（先頭2レイヤー）かつ形式が `MXFP4` であること。
- 比較対象となる expert が resident slot を持つこと（`l.slot[e] >= 0`）。1回のレイヤー呼び出しでは先頭から最大3体を表示します。

したがって、変数を設定しても非 Metal ビルド、他のエンジン、後続レイヤー、MXFP4 以外の形式、resident expert がない場合にはこの比較ログは出ません。

## 実行時の詳細

Metal の `ds4_dbg("DS4_DBG_SLOTS")` は `std::getenv()` をその場で呼びます。判定を static cache していないため `layer()` の呼び出しごとに環境を参照します。プロセス起動後に環境を変更した場合の反映可否は、実行環境による `getenv` の状態に依存します。Strata 内でこの値を CLI や子プロセスへ転送する処理はありません。

条件を満たすと、各 resident expert のファイルデータを `read_mx_file()` で読み、`host_view()` から得た slot のバイト列と `l.blob` バイト比較します。stderr には `DBG slot il=... e=... slot=... blob=... mismatching bytes=... first=...` が出力されます。差分がなければ `mismatching bytes=0` です。この分岐自体は診断出力だけで、差分を理由に終了したり計算を変更したりしません。

`read_mx_file()` の戻り値はこの診断分岐で無視されています。読み込み失敗時の診断行の値は信頼できる比較結果とは限らず、この箇所から専用の警告やエラー終了は発生しません。

## 根拠

- `src/dsv41/ds4_launch.h:30-36` — Metal では `getenv` による存在判定、Metal 以外では常に `false`。
- `src/dsv41/ds4_model.cu:9961-9969,9970-9983` — 判定が行われるレイヤー処理、レイヤー番号・形式・resident slot の条件、最大3件の比較と stderr 出力。
- `src/dsv41/ds4_model.cu:2041-2047` — ファイルから expert blob を読む処理と失敗を bool で返す実装。呼び出し側の `9976` はその戻り値を確認しません。
- `CMakeLists.txt:906-920` — DSV41 専用実行ファイルと `STRATA_BUILD_DSV41` オプション（既定 `OFF`）。
- `docs/DETAILS.md` には `DS4_DBG_SLOTS` の説明を確認できませんでした。
