# `STRATA_BLOB_VERIFY_DELAY_SEC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Windows の `FileExpertSource` が GGUF shards を in-place で扱う経路で、診断用 blob 検証を開始するまでの猶予を秒で指定する。単独では働かず、`STRATA_BLOB_VERIFY` が有効でなければこの変数は読み取られない。猶予中に待機するのではなく、その期間に呼ばれた `verify_blob` が直ちに戻り、期限後に呼ばれた blob から buffered read との比較を行う。したがって、モデルの読み込みや生成そのものを遅らせたり、検証済みデータを変えたりする値ではない（`engine/src/core/expert_source.cpp:1946-1958,1961-1967`）。

## 値と判定

`STRATA_BLOB_VERIFY` が Windows ビルドで有効な場合に限り、GGUF in-place source の open 完了時に `std::getenv` で読み、空でない文字列を `atoi` で `int` に変換して 1000 倍し、`verify_delay_ms_` に格納する。文字列全体の数値検査、clamp、無効値のエラーや警告はない（`engine/src/core/expert_source.cpp:1946-1953`）。

| 条件 | 未設定 | 有効になる値（例） | 遅延にならない値（例） |
|---|---|---|---|
| Windows、`STRATA_BLOB_VERIFY` 有効、GGUF in-place source | 0 ms | `1` → 1000 ms、`12` → 12000 ms、`2sec` → 2000 ms | `0`、`0anything`、`-1`、`true`、空文字 → 0 ms |
| `STRATA_BLOB_VERIFY` が未設定・空文字・先頭が `0`、または Windows 以外 | この変数を読まず、実質的に遅延なし | 該当なし | この変数による遅延なし |

`atoi` は先頭の空白と符号を許し、最初の数値部分までを変換するため、`"  +3tail"` は 3000 ms、`"1.5"` は 1000 ms となる。数値に変換できない先頭（例: `true`）は 0 になる。正の変換結果だけが遅延条件を満たし、0 と負数は遅延なし。入力全体や小数形式の検査はなく、範囲外入力もコードで検査されない（`engine/src/core/expert_source.cpp:1951-1952,1964-1967`）。

## 有効になる条件

- `_WIN32` のコードでのみ環境変数を読み、タイマーを設定する。Linux 等では `open_verify_handles()` の本文がプリプロセッサ条件で除かれる（`engine/src/core/expert_source.cpp:1946-1953`）。
- `STRATA_BLOB_VERIFY` が設定済み・空でなく、先頭文字が `0` でない必要がある。`1` との完全一致ではないため、`true` や ` 0` も有効判定になる一方、空文字や `0anything` は無効（`engine/src/core/expert_source.cpp:1947-1952`）。
- `strata generate` で `--mmap-experts` が選ばれ、`experts.bin` がなく、native pack の GGUF shards を in-place で開く経路が対象。通常の `experts.bin` 経路では `open_verify_handles()` を呼ばず、検証タイマーも設定しない（`engine/src/program/generate.cpp:8550-8560`, `engine/src/core/expert_source.cpp:1570-1580,1880-1883`）。
- `verify_blob` は `role_ptr_` が空の場合や layer/expert が範囲外の場合にも戻る。また実際の比較には `read_direct` が成功して `verify_blob` が呼ばれる必要がある（`engine/src/core/expert_source.cpp:1886-1893,1961-1967`）。`copy_from_files` と複数の stage-fill 経路は呼び出すが、`copy_blobs` の一括 `read_direct` 成功経路は成功時に `verify_blob` を呼ばない（`engine/src/core/expert_source.cpp:2583-2597,2692-2710,3889-3910`）。
- 遅延秒数を上書きする CLI 引数や設定ファイルは確認できない。遅延値の唯一の読み取りは上記の `getenv` 箇所。

## 実行時の詳細

`FileExpertSource::open_gguf` は GGUF shard の mapping と role ranges を準備した後、open 成功直前に `open_verify_handles()` を呼ぶ。この関数は companion の `STRATA_BLOB_VERIFY` を確認し、有効なら遅延秒数を一度読み、`verify_t0_` をセットして stderr に診断開始行を出す（`engine/src/core/expert_source.cpp:1879-1883,1946-1958`）。`FileExpertSource` インスタンス内に遅延値と開始時刻を保持し、各 `verify_blob` 呼び出しは経過ミリ秒と比較する。環境変数をリクエストごとには再読せず、プロセス実行中の環境変更は反映しない（同 `:1951-1953,1961-1967`）。

経過時間が設定値未満なら、その blob の検証だけを飛ばして返る。期限到来後の呼び出しは各 role の範囲を buffered handle で二度読みし、両 buffered read が一致する場合に `read_direct` の bytes と比較する。buffered reads 同士が異なる場合は判定を出さず、direct read と異なる場合は mismatch を記録する。失敗時も `verify_blob` 内の診断処理であり、delay 値による待ち・timeout・プロセス終了はない（`engine/src/core/expert_source.cpp:1961-1971,2001-2048`）。

## ログと測定値

遅延値が正の場合、open 時の stderr 行に `; verification holds off for the startup fill (STRATA_BLOB_VERIFY_DELAY_SEC)` が付く。正でない値ならこの句は付かない。検証は開始時刻からの経過時間で判定し、期限に達したこと自体のログはない（`engine/src/core/expert_source.cpp:1954-1958,1964-1967`）。後続の比較では buffered read 失敗時に `strata nan879-verify: BUFFERED READ FAILED ...`、差異時に `strata nan879-verify: MISMATCH ...` を stderr に出す。これらは delay 固有のログではなく、比較が実行された経路のログ（同 `:2001-2039,2045-2068`）。

`docs/DETAILS.md` にこの変数の仕様や測定値の記載は見つからなかったため、性能・正確性に関する数値は記載しない。

## 根拠

- `engine/src/core/expert_source.cpp:1879-1883` — GGUF in-place open 完了時の verifier 初期化。
- `engine/src/core/expert_source.cpp:1946-1958` — Windows 条件、companion 変数判定、対象変数の変換、開始ログ。
- `engine/src/core/expert_source.cpp:1961-1967` — 検証呼び出し時の遅延判定。
- `engine/src/core/expert_source.cpp:2001-2068` — buffered read の失敗・不一致の stderr 診断。
- `engine/src/program/generate.cpp:8550-8560` — `--mmap-experts` における `FileExpertSource` の利用。
- `engine/src/core/expert_source.cpp:2583-2597,2692-2710,3889-3910` — stage fill と bulk read の verifier 呼び出し差。
