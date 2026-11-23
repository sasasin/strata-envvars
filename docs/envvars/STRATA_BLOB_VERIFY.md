# `STRATA_BLOB_VERIFY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Windows の native GGUF shard 読み込みで、direct read が組み立てた expert blob を通常の buffered read でも読み直し、内容を比較する診断スイッチです。データ供給方式や direct read の有効化そのものは変更しません。`FileExpertSource::open_gguf()` が初期化時に値を読み、成功した `read_direct()` の結果を `verify_blob()` に渡します（`engine/src/core/expert_source.cpp:1806-1883,1886-1893`）。

対象は native layout で pack 内に `experts.bin` がなく、`open_gguf()` からモデルの GGUF shard をその場で使う経路です。通常の `experts.bin` を開く経路ではこの verifier 初期化は呼ばれません（`engine/src/core/expert_source.cpp:1570-1580,1801-1808,1882`）。

## 値と判定

Windows build の `open_verify_handles()` は `getenv` の戻り値の先頭文字だけを確認します。未設定、空文字、または先頭が文字 `0` の値は OFF。それ以外は ON です。文字列全体の parse、数値妥当性検査、大文字小文字変換、空白除去はありません。したがって `0` と `0anything` は OFF、`1`・`true`・`false`・` 0` は ON です（最後の例は先頭が空白で `0` ではないため）。比較は大文字小文字の影響を受けません（`engine/src/core/expert_source.cpp:1946-1950`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `_WIN32` build | OFF | 空でなく先頭文字が `0` 以外（例: `1`, `true`, `false`, ` 0`） | 未設定、空文字、`0`, `0anything` |
| `_WIN32` 以外 | verifier は常に OFF | なし。この build では getenv 判定自体がコンパイル対象外 | すべて |

## 有効になる条件

- `_WIN32` build であること。読み取りと verifier 本体の比較処理はいずれも Windows 用 `#if defined(_WIN32)` 内です（`engine/src/core/expert_source.cpp:1946-1959,1968-1969,2136-2138`）。
- native expert layout で `experts.bin` がなく、`open_gguf()` が成功すること（`engine/src/core/expert_source.cpp:1570-1580,1806-1883`）。
- blob が `read_direct()` で正常に読まれること。単独コピー・非同期 fill・複数 blob fill の各経路は direct read 成功時にだけ `verify_blob()` を呼びます（`engine/src/core/expert_source.cpp:1886-1895,2583-2598,2692-2711`）。この環境変数は direct read を開始・選択しません。direct handle は別の file-tier 判定や `--ssd-experts` 等の経路で開かれます（`engine/src/core/expert_source.cpp:2766-2818,2842-2864`）。
- `STRATA_BLOB_VERIFY_DELAY_SEC` が設定されている場合、遅延後に検証するかを別途判定します。未設定または空文字なら遅延なし。非空値は `atoi` で整数化して 1000 倍し、正の値の間は `verify_blob()` が検証をスキップします。`atoi` のため先頭の空白・符号・数字以降の文字は C の変換規則に従い、数字で始まらない値は 0、負数も遅延になりません（`engine/src/core/expert_source.cpp:1951-1957,1961-1967`）。
- CLI 引数や他の環境変数が `STRATA_BLOB_VERIFY` の値を上書きする処理は見つかりません。検証遅延を変える関連変数は `STRATA_BLOB_VERIFY_DELAY_SEC` です。

## 実行時の詳細

環境変数は GGUF shard の mapping と `role_ptr_` 等を構築した後、`open_gguf()` の末尾で一度読みます。ON の場合は verifier 状態を atomic に設定し、開始時刻を保存して stderr に有効化ログを出します。後からプロセス環境を変更しても、この `FileExpertSource` の有効状態は再読込されません（`engine/src/core/expert_source.cpp:1879-1883,1946-1958`）。

検証時は対象 role の範囲を同期 buffered read で2回取得します。2回の buffered 結果が一致しないと buffered channel の不安定としてカウントし、その blob の判定を終えます。一致した場合は direct read のデータと byte 単位で比較します。不一致では詳細ログを出し、最大50件まで mmap との追加比較を試みます。検証結果は診断用で、`verify_blob()` の戻り値はなく、比較不一致や buffered read 失敗によって blob の成功扱いを変更する分岐はありません（`engine/src/core/expert_source.cpp:1961-1975,1986-2048,2059-2138`）。

## ログと測定値

有効化時の stderr は `strata nan879-verify: ON (STRATA_BLOB_VERIFY=1): ... every read_direct blob is re-read and compared` です。遅延が正なら末尾に `; verification holds off for the startup fill (STRATA_BLOB_VERIFY_DELAY_SEC)` が加わります（`engine/src/core/expert_source.cpp:1954-1958`）。

buffered handle の open に失敗した場合はその場で戻り、専用ログは出ません。seek/read/short read の失敗では `BUFFERED READ FAILED (...)` と `BUFFERED READ FAILED layer ...` を出します。一致する2回の buffered read と direct read の内容が異なる場合は `MISMATCH ...` と周辺 byte の16進表示を出し、追加比較では `ARBITRATION ...`、open/map 失敗時は `ARBITRATION open failed ...` / `ARBITRATION map failed ...` を出します。比較対象数が0でも verifier が ON なら破棄時に `total blobs compared ..., mismatches ..., unstable channel reads ..., mmap arbitrations ...` の集計を stderr に出します（`engine/src/core/expert_source.cpp:1045-1053,1991-2006,2031-2069,2070-2129`）。

この調査では build・実行・性能測定をしていません。Strata の設計資料にこの診断の測定値は見つかりませんでした。

## 根拠

- `engine/src/core/expert_source.cpp:1570-1580,1801-1883` — native GGUF の選択と verifier 初期化。
- `engine/src/core/expert_source.cpp:1946-1959` — Windows guard、値判定、遅延値の取得、有効化ログ。
- `engine/src/core/expert_source.cpp:1961-2138` — 遅延判定、buffered reread、比較、失敗・不一致ログ。
- `engine/src/core/expert_source.cpp:1886-1895,2583-2598,2692-2711` — direct read 成功後に検証を呼ぶ経路。
- `engine/src/core/expert_source.cpp:2766-2818,2842-2864` — direct handle の設定は別の処理で行うこと。
- `engine/src/core/expert_source.cpp:1045-1053` — 終了時集計。
