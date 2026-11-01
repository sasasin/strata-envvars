# `STRATA_MTP_REVISION`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

同梱ツール `tools/mtp_fetch.py` が Qwen/Qwen3.8-Flash-Next から MTP tensor を取得するときに使う Hugging Face の revision を指定します。標準では固定 revision `de4b8e4d43b917e7706784d8bb445c9af86a3540` を選びます。この変数は Strata の engine の推論動作を直接変えず、setup が取得・準備する MTP draft layer のソースを変えます。

## 値と判定

| 環境値 | revision の選択 |
|---|---|
| 未設定 | 固定 revision `de4b8e4d43b917e7706784d8bb445c9af86a3540` |
| 空文字 | Python の `or` により未設定と同じ固定 revision |
| 空でない文字列 | 文字列をそのまま revision として URL に埋め込む |

文字列の trim、大小文字変換、commit hash 形式の検証、許可値一覧との照合はありません。したがって `main` のようなブランチ名も指定できます。`0` や `false` も空でないため revision として扱われ、真偽値として解釈されません。CLI 引数による revision 指定はありません。setup の `--mtp on/off` は MTP の取得を行うかを決め、revision を選びません。

## 有効になる条件

- 直接実行の場合、`tools/mtp_fetch.py` の `inventory` または `fetch` コマンドが revision URL を使います。`verify` はネットワーク取得をせず、固定 revision 用 hash の照合だけを行います。
- setup 経由では、モデル準備の段階で MTP runtime がまだないか、既存 runtime の tensor が固定 hash 検査で破損と判定された場合に `fetch_mtp()` がツールを起動します。ただし `--mtp off` で runtime がまだない場合は取得しません。既存 runtime が正常なら通常は再取得しません。
- `STRATA_SOURCE` が `ms` または `modelscope` の場合、ツールは `STRATA_MTP_REVISION` を読んだ後に `REPO` を ModelScope の `master` URL に置き換えます。この経路では指定 revision は取得 URL に反映されません。ModelScope 経路では固定 revision 用 SHA256 照合が有効です。

## 実行時の詳細

値は `tools/mtp_fetch.py` の import 時に一度読み、`REVISION`、`REPO` としてプロセス内に保持します。setup は `os.environ` を元に子プロセス環境を作って MTP fetcher を起動するため、明示的に削除・置換されない `STRATA_MTP_REVISION` は継承されます。setup の `--source modelscope`（または `STRATA_SOURCE` の設定）は子プロセスで ModelScope 分岐を選び、revision 指定を上書きします。setup の CLI に revision との優先順位を設定する引数はありません。

HF 経路では `REPO` が固定 revision URL と一致する場合だけ、31 tensor に対する組み込み SHA256 が取得時・verify 時に使われます。別 revision を指定すると hash 照合対象ではなくなり、取得された bytes はこの固定 hash では検証されません。`verify` も `pinned()` が偽なら空の結果を返すため、setup から見た既存 tensor の破損判定を行いません。固定 hash の対象外となる別 revision に切り替えた `fetch` は inventory の URL 不一致を検出して inventory を読み直し、既存 tensor を再利用せず削除してから取得します。同じ URL の途中取得はサイズに基づいて再開します。

要求した HF revision の index が HTTP 404 で、`STRATA_ALLOW_UNPINNED` を trim した値が厳密に `1` でない場合、stderr に `the pinned version of the checkpoint (<revision>) is no longer on Hugging Face: update Strata` を出して終了します。厳密に `1` なら stderr に fallback の通知を出し、`main` から読みます。別 revision 指定時もこの分岐は動きますが、表示される文言は「pinned version」です。ネットワークエラー等の再試行・終了メッセージは `get()` / `fetch()` の経路で出ます。setup は fetch の非0終了を最大3回試し、最後も失敗すれば `the draft layer's download keeps stopping (exit ...)` で失敗します。

## 根拠

- `tools/mtp_fetch.py:37-51` — 固定 revision、環境値の `or` 判定、HF URL の生成、ModelScope による URL 上書き。
- `tools/mtp_fetch.py:294-296,367-398,442-448` — 固定 URL 判定、inventory の revision 一致判定、取得時 hash と既存 tensor の扱い、別 revision 時の verify skip。
- `tools/mtp_fetch.py:307-324` — revision index の 404、`STRATA_ALLOW_UNPINNED` 判定、終了・`main` fallback のログ。
- `tools/mtp_fetch.py:475-489` — CLI コマンドと、`verify` と取得系コマンドの実行経路。
- `setup.py:959-977,981-997` — setup の子プロセス環境継承、fetch 実行と再試行・失敗経路。
- `setup.py:9188-9191,10058-10074` — `--mtp` の意味、既存 runtime の検査、fetch と pack/ runtime 生成への接続。
- `setup.py:7523-7531` — setup の固定 hash 検証呼び出しと終了コードの扱い。
