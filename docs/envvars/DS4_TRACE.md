# `DS4_TRACE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 のモデル実装が選択した expert ID をバイナリファイルへ記録します。`strata-dsv41` の `Model::Impl` が生成されるときに環境変数を読み、設定されていれば指定パスを `wb` モードで開きます。ルーティング記録を収集する診断・解析用フックで、通常の推論結果や expert 選択を変更しません。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未設定 | ファイルを開かず、記録しない |
| 設定あり、空文字 | `fopen("", "wb")` を試みる。通常は開けず、記録しない |
| 設定あり、パス文字列 | そのパスを `wb` で開く。既存ファイルは切り詰められる |
| パスを開けない | `trace_f` が null のままとなり、記録しない。専用の警告・エラーは出さない |

値の数値変換や真偽文字列の parse はありません。空文字を含め、`getenv()` が null でないかだけで記録先を選びます。`fopen` の戻り値は確認しますが、各 `fwrite` の戻り値は確認しません。

## 有効になる条件

- Strata 同梱の DeepSeek V4.1 実装 `src/dsv41/ds4_model.cu` を使う実行経路であること。ほかのモデル実装へ一般化できる設定ではありません。
- `DS4_TRACE` は `Model::Impl` の生成時に読み込まれます。実行中に環境を変更しても、そのモデルインスタンスの `trace_f` は変わりません。
- MTP 層 (`l.mtp`) は記録対象外です。
- `DS4_TRACE_AHEAD` が設定されていると、decode の route-request 記録に lookahead の予測 expert ID も追加されます。こちらも値の内容ではなく、記録時点で `getenv()` が null かどうかで判定されます。`DS4_TRACE` が有効で route-request を処理するとき、初回判定を関数内 `static` に保存します。

## 実行時の詳細

モデルの window/decode 経路では、service thread が受け取った各 non-MTP layer の routing request を、layer byte、token 数 byte、各 token の `k_exp` 個の expert ID (`int16`) の順に書きます。`DS4_TRACE_AHEAD` が設定されている場合、token 数 byte の bit 7 を立て、続けて2 byteの lookahead 件数と予測 ID 群を書きます。件数は実際の配列上限に clamp されます。詳細は `src/dsv41/ds4_model.cu:6481-6504` です。

chunked prompt 経路では、各 non-MTP layer について `mi == 0` のときに routing ID 配列を device から host へコピーし、layer byte（bit 7 を立てる）、下位 byte を先に置く `uint16` token 数、各 token の `k_exp` 個の `int16` expert ID を記録します。`DS4_TRACE_AHEAD` の追加形式はこの chunk record には適用されません（`src/dsv41/ds4_model.cu:7356-7366`）。expert ID は C++ の `int16` のメモリ表現で書かれ、ファイル全体に形式識別子は付きません。

ファイルは `Model::Impl` のメンバーとして開かれ、同じモデルの複数 feed 呼び出しにわたって追記されます。ソース上、trace stream に対する `fflush` / `fclose` は見当たりません。`fopen` に失敗しても stderr の警告はなく、書き込み失敗も検査されません。

## 根拠

- `src/dsv41/ds4_model.cu:800,1157`: `Model::Impl` 内で環境を読み、`wb` でファイルを開く。
- `src/dsv41/ds4_model.cu:6481-6504`: decode の route-request と任意の ahead 記録。
- `src/dsv41/ds4_model.cu:7356-7366`: chunked prompt の記録。
- `src/dsv41/ds4_model.cu:1243-1286`: `Impl` の破棄処理。ここに trace stream の flush / close はない。
- `src/dsv41/ds4_main.cpp:1097-1124`: `--profile-run` が model feed を繰り返し、expert profile と routing trace を収集する経路の説明。これはコメント上の用途確認であり、値の挙動の根拠は上記実装。
- `docs/DETAILS.md:86-88,297-301`: 通常の Strata routing dump / adaptive tier replay の説明はありますが、`DS4_TRACE` の固有形式や失敗時の挙動は説明していません。
