# `STRATA_MTP_REVISION`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

`tools/mtp_fetch.py` が Hugging Face から Qwen3.8-Flash-Next の MTP tensor を取得する際に参照するリビジョンを指定します。Strata エンジンの実行時設定ではなく、同梱取得ツールの設定です。未指定時は固定 commit `de4b8e4d43b917e7706784d8bb445c9af86a3540` を使います。

## 値と判定

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | `PINNED_REVISION` の固定 commit を使う |
| 空文字 | Python の `or` により空文字を偽として扱い、固定 commit を使う |
| 空でない文字列 | 文字列を加工・検証せず `REVISION` として参照 URL に埋め込む |

大文字小文字の変換、空白除去、commit hash の形式確認はありません。たとえば `main` は `.../resolve/main/` を指定します。環境変数は `tools/mtp_fetch.py` の import 時に一度 `os.environ.get()` で読み取られ、そのプロセスの実行中には再評価されません。

根拠: `tools/mtp_fetch.py:29-37`。

## 有効になる条件と検証への影響

対象は Hugging Face 経由の MTP 取得です。設定した文字列は `REPO` の URL に入り、`inventory` と `fetch` が読む index・shard の取得元になります。`verify` はこの参照 URL がハッシュ定義用の固定 URL `PINNED` と等しい場合だけ、固定 commit の SHA-256 による検証を行います。別 revision を指定すると `verify()` は空のエラー一覧を返し、固定 commit に対する正誤は検査しません。その場合の `fetch` も固定ハッシュとの照合を行わず、取得 tensor の digest を manifest に記録します。

ただし、`STRATA_SOURCE` が `ms` または `modelscope` の場合は ModelScope の `master` URL に切り替えられ、`REPO` と `PINNED` の両方がその URL になります。この分岐では `STRATA_MTP_REVISION` の指定にかかわらず revision 指定は URL に反映されません。ハッシュ比較は固定 SHA-256 定義を使います。

根拠: `tools/mtp_fetch.py:34-43,146-148,213-260,265-271`。

## 実行時の詳細

`inventory` / `fetch` の開始時には `resolve_repo()` が index URL に HEAD リクエストを行います。指定 URL が HTTP 404 で、かつ URL がすでに `/resolve/main/` ではない場合、stderr に `the checkpoint's pinned revision <値> is gone: reading its current files (main)` と出し、参照先を `main` に切り替えます。ネットワークの `OSError` はここでは無視され、後続の取得処理に進みます。リビジョンを切り替えた後は `REPO != PINNED` となるため、固定 commit の tensor ハッシュ比較は無効です。

`setup.py` は `env = dict(os.environ, STRATA_GGUF_PY=...)` を作って子プロセスへ渡し、MTP 取得時にはさらに `STRATA_SOURCE` を加えて `tools/mtp_fetch.py fetch` を起動します。そのため setup の親プロセスに設定された `STRATA_MTP_REVISION` は子プロセスにも引き継がれます。setup が既存 MTP tensor の破損確認のため `verify` を呼ぶ場合も同じ `env` を渡します。alternate revision を指定したときは `verify` が固定 revision との照合をしないため、この確認はその tensor 群について空結果になります。

根拠: `tools/mtp_fetch.py:159-173,298-310`; `setup.py:4611-4619,5520-5520,5541-5554`。

## 関連資料

`tools/mtp_fetch.py` の冒頭コメントは、固定 revision によって各インストールで同じ tensor を読むこと、`STRATA_MTP_REVISION` で上書きできること、および固定 revision がなくなった場合に `main` を読むことを説明しています。取得手順の例は `docs/ORCA.md:37` にあります。性能や生成結果への影響をこの変数について測定した資料は確認できませんでした。

## 根拠

- `tools/mtp_fetch.py:29-43` — 固定値、環境変数の評価、URL 構築、ModelScope 分岐。
- `tools/mtp_fetch.py:146-148,159-173` — 固定版判定と 404 時の fallback。
- `tools/mtp_fetch.py:213-260,265-271` — fetch 時のハッシュ適用と verify の条件。
- `setup.py:4611-4619,5520,5541-5554` — setup の子プロセスへの環境引き継ぎと取得・検証呼び出し。
