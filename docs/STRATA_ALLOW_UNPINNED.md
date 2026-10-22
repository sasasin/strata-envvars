# `STRATA_ALLOW_UNPINNED`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

セットアップ中、Hugging Face 上で固定 revision が 404 になった場合に、現在の `main` のファイルへ切り替えて取得するためのテスター向け例外です。通常のエンジン実行時の設定ではありません。`setup.py` のモデルファイル取得と、セットアップから起動される `tools/mtp_fetch.py` の MTP チェックポイント取得が読みます。

## 値と判定

両方の読み取り箇所とも、`(os.environ.get(...) or "").strip() == "1"` で判定します。文字列全体を前後空白除去した後に `"1"` と完全一致する必要があります。

| 環境変数の値 | 判定 |
|---|---|
| 未設定、空文字、空白だけ | 無効 |
| `1`、` 1 ` | 有効 |
| `01`、`1.0`、`true`、`yes`、`0`、その他 | 無効 |

整数変換や先頭文字比較はしません。既定値は無効です。`setup.py` は有効時の注意書きをプロセス内で最初の一度だけ表示します（`_unpinned_said`）。`tools/mtp_fetch.py` は条件に遭遇するたびに stderr に切替えた revision を表示します。

## 有効になる条件

### `setup.py` の通常モデルファイル

`download()` が HTTP `HEAD` 中に `HTTPError 404` を受け、かつ URL が固定 SHA revision の Hugging Face `.../resolve/<40桁hex>/...` 形式である場合だけ、この変数が参照されます。無効なら「固定版が Hugging Face にない」として setup を停止し、Strata の更新を案内します。有効なら `/resolve/main/` に URL を置き換えて再試行し、該当ファイルの `pin` を `None` にします。そのため取得後の SHA-256 検証は行われず、ファイルサイズはサーバー応答から取得できる範囲で通常どおり確認されます。

この例外は固定版 URL 以外の 404、404 以外の HTTP エラー、単なる接続失敗には適用されません。ModelScope の URL を直接使う経路にも適用されません。固定版ファイルが存在して正常取得できる場合は、この変数が設定されていても `main` へ切り替えません。

### MTP チェックポイント

`tools/mtp_fetch.py` は index の HEAD が 404 で、URL に `REVISION` が含まれる場合、無効なら `sys.exit()` で停止し、有効なら URL を `main` に差し替えます。setup からは MTP が必要で、まだ取得されていない場合や既存 MTP データが破損と判定された場合に `fetch_mtp()` を通して起動されます。子プロセス環境は setup の環境を引き継ぐため、この変数も渡ります。

**ソース実装と説明コメントに不一致があります。** `resolve_repo()` の docstring と stderr のメッセージは、切替後も各 tensor を固定 SHA-256 と照合すると述べています。しかし切替時は `REPO` が `/resolve/main/` となり、`pinned()` は `REPO == PINNED` ではなくなるため、`fetch()` では `want = None` になります。このときサイズ確認は行いますが、該当 tensor の固定 SHA-256 照合はスキップされます（sha256 値は manifest には計算・記録されます）。したがって HF の MTP 固定版 404 に対する有効化は、MTP tensor の固定ハッシュ検証も無効にします。ModelScope 経路は `REPO = PINNED` のままなので、この特定の不一致とは異なる経路です。

## 実行時の詳細

この値は通常の setup 実行時に再評価される動的設定ではなく、取得処理が該当エラーに達した時点で環境を参照します。モデルファイルについては警告を標準出力に出し、固定 URL を `main` に変えて HEAD を再試行します。`main` のファイルが取得できない場合は通常のダウンロード失敗処理に進みます。`setup.py` の警告には `not checked against a SHA-256`、共通の一度限りの警告には `is NOT checked against a SHA-256` と表示されます。

MTP 取得では stderr に `STRATA_ALLOW_UNPINNED=1: ... reading its current files (main); every tensor is still checked against the pinned SHA256` と表示されますが、上記のとおり現行コード上の SHA 判定は切替後にスキップされます。これはコメントと実装の差であり、ハッシュ検証済みである根拠としてログ文を扱えません。

## 根拠

- `setup.py:123-131` — 値の完全一致判定、既定 OFF、一度限りの注意書き。
- `setup.py:2624-2665, 2677-2712` — 対象となる 404、停止または `/main/` への切替、pin の解除、ダウンロード後の検証分岐。
- `setup.py:769-785, 7755-7759, 8736-8748` — MTP 取得の起動条件と子プロセスへの環境引き継ぎ。
- `tools/mtp_fetch.py:32-47, 302-319` — revision、source の選択、404 時の判定と URL 差し替え。
- `tools/mtp_fetch.py:388-392, 418-430` — `pinned()` に連動する固定 SHA 判定とサイズ確認。
- `docs/SAFETY.md:115-128` — 利用者向けの一般説明。MTP fallback 時の SHA 判定は現行コードと説明メッセージの間に上記の差があるため、コードを根拠に記述した。
