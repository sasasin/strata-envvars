# `STRATA_EXIT_WITH_PARENT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

親プロセスが終了したとき、子プロセスも終了させるためのフラグです。Strata の同梱コードでは、`tools/mtp_fetch.py` が親の終了後に MTP ダウンロードを残さない用途で読み、ホストサーバー (`apps/host/server/index.mjs`) がデスクトップシェル終了時にホストを止める用途で読みます。両者は同じ名前を使いますが、値の判定と終了処理が異なります。

## 値と判定

| 読み取り箇所 | 有効になる値 | 無効になる値 |
|---|---|---|
| `tools/mtp_fetch.py` | 値を取得し、前後の空白を `strip()` で除いた結果が文字列全体で `1` | 未設定、空文字、空白だけ、`0`、`true`、`01`、`1x` など |
| `apps/host/server/index.mjs` | 文字列全体が厳密に `1` | 未設定、空文字、空白付きの `1`、`0`、`true`、`01` など |

数値変換や大文字小文字変換はありません。Python 側だけは前後の空白を除いてから比較します。どちらも部分一致ではありません。Python 側では `verify` コマンドの処理が先に終了するため、この監視は `inventory` と `fetch` でのみ開始されます。`fetch` ではロック取得やネットワーク処理より前に親を監視し始めます。

根拠: `tools/mtp_fetch.py:470-485`, `tools/mtp_fetch.py:212-237`, `apps/host/server/index.mjs:2204-2210`。

## 有効になる条件

- `setup.py` の `run()` は、子コマンド用の環境辞書に `setdefault("STRATA_EXIT_WITH_PARENT", "1")` を行います。したがって、呼び出し元の環境に同名キーがなければ `1` を子へ渡し、既にキーがあればその値（空文字や `0` も含む）を保ちます。このため通常の setup 起動では `tools/mtp_fetch.py` の監視が有効ですが、呼び出し元が明示的に別値を設定すると無効にできます。`run()` は setup の子コマンド一般に値を渡しますが、この Python ファイルで確認できる読み取り実装は `mtp_fetch.py` です。
- デスクトップアプリは Node ホスト起動時に `.env("STRATA_EXIT_WITH_PARENT", "1")` を設定します。`apps/host/server/index.mjs` はそのプロセス環境で値が厳密に `1` の場合にだけ監視します。この起動経路では Rust の `Command::env` により `1` を設定します。
- 上記以外の直接起動では既定値を設定する読み取りコードはありません。環境変数が未設定なら両方の監視は行われません。

根拠: `setup.py:747-765`, `setup.py:769-780`, `apps/desktop/src-tauri/src/main.rs:449-470`。

## 実行時の詳細

`mtp_fetch.py` は起動時に一度環境変数を確認します。有効なら現在の親 PID を取得し、PID が 1 以下の場合は監視を開始しません。Windows では `OpenProcess(SYNCHRONIZE, ...)` で親プロセスのハンドルを開き、取得できなければ監視を行いません。開けた場合は `WaitForSingleObject(handle, 0)` で終了を調べます。Windows 以外では、`os.getppid()` が保存した親 PID と異なるかを調べます。監視スレッドは1.5秒間隔で確認し、親終了を検出すると stderr に `the process that started this download has ended: stopping` を出して `os._exit(1)` で直ちに終了します。これは通常の Python 終了処理や `finally` を実行する経路ではありません。

ホストサーバーは有効時に起動時の `process.ppid` を保存し、1秒間隔で確認します。POSIX では `process.ppid` の変化を親の消失として扱います。Windows では元の PID に `process.kill(parent, 0)` を試し、`ESRCH` の場合に消失と判定します。親が消えた場合は `shutdown()` を呼び、タスク受付を閉じ、HTTP サーバーと接続を閉じ、share / cloudflare / native / agent の終了処理を待ちます。終了処理が完了しない場合は、control モードなら最大45秒、それ以外なら最大10秒で `process.exit(0)` するタイマーも設定されています。

Python 側は変数を `exit_with_parent()` の呼び出し時に評価し、監視スレッドは保存した親との関係だけを繰り返し調べます。ホスト側も起動時に一度だけ条件を評価して監視 interval を登録します。どちらも稼働中に環境変数を書き換えて監視を開始・停止するコードはありません。

根拠: `tools/mtp_fetch.py:212-237,470-485`, `apps/host/server/index.mjs:2191-2210`。

## 文書との照合

`docs/release-notes-0.2.1.md:96` は issue #3257 に関連して、MTP ダウンロードの孤児プロセス対策に言及しています。これは Python 側の用途と整合しますが、値の判定、OS ごとの監視方法、ホストサーバー側の別用途までは説明していません。対応する動作の根拠は上記ソースコードです。性能測定値は該当しません。
