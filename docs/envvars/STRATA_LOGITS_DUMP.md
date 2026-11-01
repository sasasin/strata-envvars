# `STRATA_LOGITS_DUMP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

通常の verify window で計算した head logits を指定パスへバイナリ形式で保存します。実装コメントでは sampler が見た window の logits を診断用に保存する tap とされています。KVA 専用ではなく、KVA の有効・無効を切り替える環境変数でもありません（`src/core/verify.cpp:3410-3415`、`docs/KVA.md:123`）。

`STRATA_LOGITS_DUMP` は `src/core/verify.cpp` の `std::getenv("STRATA_LOGITS_DUMP")` で直接読み取られます。全リポジトリの名前検索で確認できたコード参照はこの読み取りとその直前のコメントだけです。helper 経由や動的な名前の読み取りはありません。候補一覧の名前は、この実装で実際に環境から読まれています。

## 値と判定

| 環境値 | Strata の処理 |
|---|---|
| 未設定 | dump 部分を実行しない。 |
| 設定あり（空文字を含む） | 値をパスとして `std::fopen(path, "wb")` に渡す。文字列比較、数値変換、空白除去、範囲検査はしない。 |

空文字も `getenv` が null でないため有効側の分岐に入りますが、空文字パスでの `fopen` が成功するかは OS のファイル API に委ねられ、Strata は失敗を通知しません。`fopen` 成功時は `"wb"` で開くため、そのパスに既存ファイルがあれば最初に切り詰めます。

CLI 引数による上書きや別環境変数との優先順位はありません。CLI の `--dump-logits` は `src/program/generate.cpp` にある別の出力機能で、この環境変数の値を設定・変更しません（`src/program/generate.cpp:546,1005,3047,8007-8014`）。

## 有効になる条件

- `Verifier::run()` が実行され、関数末尾近くの dump 部分まで正常に到達すること。window の CUDA stream 同期、sampling、出力 token の取り出しより後に処理されます（`src/core/verify.cpp:3333-3358,3395-3415`）。
- layer split の先行 stage は `le_ < g.n_layers` の分岐で次 stage に渡して戻るため、その stage では dump しません。最終 stage の run が到達すればそこで対象になります（`src/core/verify.cpp:3355-3358`）。
- `STRATA_GPU_METAL` ビルドでは `Verifier::run()` が Metal の `window_run()` を呼んで早期 return するため、この dump コードを通りません（`src/core/verify.cpp:3056-3061`）。
- `run_slot_rows()` による slot batch と `pl_finish()` による pipelined finish には同じ書き込み処理がありません（`src/core/verify.cpp:4387-4405,5024-5048`）。環境変数を設定しただけで全推論経路の logits が記録されるわけではありません。

ソース上、この分岐に OS、GPU 世代、KVA 状態、CLI フラグによる追加 gate はありません。非 Metal の通常 `run()` 経路で、設定値がありファイルを開けた場合に動作します。

## 実行時の詳細

各対象 window の処理時に `getenv` を評価します。環境値があると、最初に条件へ入った時点で `static std::FILE*` が `fopen(path, "wb")` を一度だけ実行し、その結果（失敗時の null も含む）を後続呼び出しでも使います。最初の open 後に環境値を書き換えても別パスへ切り替わらず、open 失敗後も再試行しません。外側の `getenv` 判定自体は呼び出しごとに行われるので、最初の対象 window まで unset で、その後 set された場合は、その時点のパスで初回 open します（`src/core/verify.cpp:3415-3418`）。

記録は次の順序のバイナリです。ヘッダーは4個の native `int32`（magic `0x53474F4C`、window の `T`、`n_vocab`、record 番号）、続いて native `int64` の `pos0`、最後に `T * n_vocab` 個の native `float` logits を row-major で書きます。row 0 は `pos0` の位置です。各 window で device logits を host vector へコピーし、成功した場合にヘッダーとデータを書いて `fflush` します。record 番号は成功した device-to-host copy の後で増えます（`src/core/verify.cpp:3419-3427`）。

`fopen` が失敗した場合は何も書かず、警告も出しません。device-to-host copy が失敗すると、最初の一度だけ stderr に `strata verify: STRATA_LOGITS_DUMP copy failed: <CUDA error string>` を出し、CUDA の last error を取得して dump をスキップします。どちらの失敗も、この dump 部分から `run()` を失敗扱いにはしません。`fwrite` と `fflush` の戻り値も検査されません（`src/core/verify.cpp:3416-3434`）。

## 根拠

- 全参照検索: `docs/KVA.md:123,145-148` と `src/core/verify.cpp:3410-3432`。実際の読み取りは `src/core/verify.cpp:3415`。
- 値の確認、static file handle、バイナリ構造、copy・書き込み・エラー処理: `src/core/verify.cpp:3415-3434`。
- 対象となる通常 verify window と最終 stage の分岐: `src/core/verify.cpp:3333-3358,3395-3415`。
- Metal と batch/pipelined 経路: `src/core/verify.cpp:3056-3061,4387-4405,5024-5048`。
- `docs/KVA.md` は KVA 条件下の likelihood 比較でこの変数を logits 保存に使うと述べていますが、測定値は同文書の記載です。本調査では測定を再実行していません（`docs/KVA.md:145-148`）。
