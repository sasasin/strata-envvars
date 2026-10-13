# `MODELSCOPE_ENDPOINT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

ModelScope を配布元として明示的に選んだ場合に、Strata のセットアップ処理と同梱 MTP ダウンロードツールが接続する ModelScope のベース URL を指定する。ModelScope の選択自体はこの変数では行わない。セットアップでは `--source modelscope` または `STRATA_SOURCE=modelscope`（別名 `ms`）が必要で、未選択時は Hugging Face 経路のままである。

## 値と判定

| 環境変数の状態・値 | ベース URL |
| --- | --- |
| 未設定、空文字、空白だけ、または末尾の `/` を除いて空になる値 | `https://www.modelscope.cn` |
| その他の値 | 前後の空白と末尾の `/` を取り除いた文字列をそのまま使用 |

コードは URL の形式や到達可能性を事前検証せず、値の大文字小文字も変換しない。セットアップでの `ms_endpoint()` は呼び出しごとに環境を読み直す。`model_source()` は `STRATA_SOURCE`、`HF_ENDPOINT`、正規化後の ModelScope URL をキーにして結果をキャッシュするため、同じキーの呼び出しではソース選択を再計算しない。MTP fetch ツールでは環境変数をモジュール読み込み時に読み、URL 定数を作る。

## 有効になる条件

- セットアップは `STRATA_SOURCE` を前後空白除去・小文字化した値が `ms` または `modelscope` の場合だけ ModelScope を選ぶ。`MODELSCOPE_ENDPOINT` の設定だけでは選択されない。CLI の `--source` を指定した場合は、その値が `STRATA_SOURCE` に設定される。
- セットアップは、ModelScope を選んでも、対象 URL が既知の Hugging Face モデルファイル（`HF_REVISIONS` にあるリポジトリ）に対応する場合に限り置き換える。それ以外の URL は通常のダウンロード URL のまま。
- `tools/mtp_fetch.py` も `STRATA_SOURCE` が `ms` / `modelscope` の場合だけこの URL を使う。セットアップから起動するときは選択済みの `STRATA_SOURCE` を子プロセス環境に渡す（`MODELSCOPE_ENDPOINT` は元の環境から継承される）。

## 実行時の詳細

セットアップは `MODELSCOPE_ENDPOINT` を ModelScope のファイル URL（`/models/{repo}/resolve/master/{path}`）とファイル一覧 API（`/api/v1/models/{repo}/repo/files?Recursive=true`）のベースに使う。ModelScope のファイル URL へ 30 秒の HEAD 要求を送り、応答しなければ警告を出して Hugging Face URL へ戻る。応答した場合はその URL からダウンロードし、ModelScope のファイル一覧から取得できるサイズと SHA-256 を検証に使う。SHA-256 が公開されていない場合は未検証である旨を警告して完了マークを付ける。URL が応答するかどうか以外の妥当性チェックはなく、その後の HEAD/ダウンロード/API 要求が失敗した場合に独自の endpoint fallback をするコードは確認できない。

`tools/mtp_fetch.py` は環境変数が選択済みなら、MTP チェックポイントの `REPO` と `PINNED` の両方を `{endpoint}/models/Qwen/Qwen3.8-Flash-Next/resolve/master/` に設定する。ModelScope が現在のファイルを配信するため固定 revision URL ではないが、取得した MTP tensor はコード内の固定 SHA-256 と照合される。ModelScope 経路では `resolve_repo()` の「固定 revision が 404 なら main に切り替える」処理は通常対象にならない。

## 根拠

- `setup.py:93-108` — ModelScope の既定 URL と `MODELSCOPE_ENDPOINT` の正規化。
- `setup.py:120-128` — ModelScope を明示選択する条件と、環境値を含む選択結果キャッシュ。
- `setup.py:139-162` — ModelScope のファイル URL/API、およびファイル一覧メタデータの取得。
- `setup.py:1449-1470`, `setup.py:1527-1538` — 対象 URL の限定、到達確認、Hugging Face への fallback、SHA-256 がある場合の検証。
- `setup.py:4894-4895`, `setup.py:5477-5483`, `setup.py:5520`, `setup.py:5550-5552` — CLI 値の環境設定、選択時の表示、元の環境を引き継ぐ MTP fetch 子プロセスへの `STRATA_SOURCE` の引き渡し。
- `tools/mtp_fetch.py:38-44`, `tools/mtp_fetch.py:47-113`, `tools/mtp_fetch.py:146-173` — 選択条件、endpoint からの URL 構築、固定 tensor hash と revision 解決。
- `docs/INSTALL.md:283-289` — ModelScope の明示選択、current files の利用、ハッシュ照合についての文書説明。URL の実際の判定・fallback は上記ソースを根拠とした。
