# `STRATA_INKLING_SOURCE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Inkling-2-Mini のモデルファイルと tokenizer ファイルを取得するときに、追加の HTTP(S) ダウンロード元を指定する環境変数。Inkling のモデル一覧への掲載可否にも使われる。Strata の `terminal/strata_control/inkling_family.py` がこの名前を `SOURCE_ENV` として宣言し、`sources()` と `gguf_sources()` が値を読んで URL 候補へ変換する。GPU backend やモデル実行時の計算は変更しない（`terminal/strata_control/inkling_family.py:121-165`）。

環境変数の URL は同梱の標準 URL を置き換えるのではなく、その前に候補として追加される。インストーラーは候補を順に試し、前の取得が失敗した場合に次へ進む（`terminal/strata_control/inkling_family.py:126-158`, `terminal/setup.py:10458-10485`）。

## 値と判定

Python の `os.environ.get()` で設定有無と値を調べる。数値や真偽値への変換はなく、空でない文字列を `_normalise()` に渡す。文字列は大文字小文字を区別して `http://` または `https://` で始まる場合だけ候補になり、末尾の `/` をすべて除く。前後の空白除去、URL 全体の構文検証、複数 URL 文字列の分割はしない（`terminal/strata_control/inkling_family.py:128-139`, `terminal/strata_control/inkling_family.py:168-180`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `.strata` / tokenizer のソース候補 | 環境変数由来の候補なし。同梱 `inkling-sources.json` の `sources` は引き続き候補になる | `https://mirror.example/inkling`、`http://host/repo///`（末尾 `/` は除去） | 空文字、`0`、`true`、`0anything`、` https://host/repo`、`HTTPS://host/repo`。これらは環境変数由来の候補にならない |
| GGUF のソース候補 | この環境変数由来の候補なし。同梱 `gguf_sources` は引き続き候補になる | 同じく小文字の `http://` / `https://` で始まる空でない文字列 | 同じく空文字、前後空白付き、大文字 scheme など |

値が無効でもエラーにはならず、この変数由来の候補だけが無視されます。ダウンロード一覧が空になるかは設定キー、`STRATA_INKLING_GGUF_SOURCE`、同梱 JSON の内容にもよります（`terminal/strata_control/inkling_family.py:126-180`）。

## 有効になる条件

- Inkling-2-Mini 用のファイル取得または取得元を参照する処理が呼ばれること。非 GGUF の `.strata` / tokenizer では `sources()`、GGUF ファイルでは `gguf_sources()` が選ばれる（`terminal/strata_control/inkling_family.py:161-165`）。
- インストーラーではローカルファイルの利用経路ではなくダウンロード経路に入ること。`--gguf-dir` 由来のローカルソースがあれば取得関数を通らない（`terminal/setup.py:10596-10601`, `terminal/setup.py:10646-10653`）。
- GGUF 用取得では `STRATA_INKLING_GGUF_SOURCE` が空でない有効 URL を持つ場合、その候補がこの変数より先に試される（`terminal/strata_control/inkling_family.py:142-158`）。
- `sources(cfg=...)` を呼ぶ画像ファイル取得経路では、設定辞書の `inkling_source` がこの変数より先に候補化される。明示的な `endpoint` が渡されると、その endpoint だけから URL を組み立て、この環境変数を含む `sources()` は呼ばれない（`terminal/strata_control/pictures.py:377-383`, `terminal/strata_control/pictures.py:426-430`）。
- backend、OS、CLI 値による URL 判定条件はない。利用者が起動後に `os.environ` を変更した場合も、次にソース解決関数が呼ばれれば再評価される。

## 実行時の詳細

`sources()` は設定辞書の `inkling_source`、環境変数、同梱 JSON の `sources` の順で候補リストを作る。GGUF では `gguf_sources()` が設定辞書の `inkling_gguf_source`、設定辞書の `inkling_source`、`STRATA_INKLING_GGUF_SOURCE`、この環境変数、同梱 JSON の `gguf_sources` の順に連結する。よって「override」という同梱 JSON の注記にかかわらず、実装は後続候補を削除せず、優先順をつけて追加する（`terminal/strata_control/inkling_family.py:126-158`, `terminal/data/inkling-sources.json:1-14`）。

インストーラーの `inkling_fetch()` はファイル名から候補種別を選んで `sources_for()` を呼ぶ。各ソースからそのファイルの URL を得て、各候補について最初の URL を `download()` に渡す。ダウンロード処理が `SystemExit` で失敗し、後続候補があれば `[!]  <ファイル名>: that source did not work; trying the next one` を出して続行する。候補が尽きると最後の失敗を再送出する。ソース候補自体がなければ `fail()` により終了コード 1 で停止する（`terminal/setup.py:10458-10485`, `terminal/setup.py:1039-1056`）。

読み取りは関数呼び出しごとで、値を保存する `static` 相当の cache はない。MCP の `inkling_visible()` は `sources()` が空でなければ Inkling を一覧に掲載する。CLI setup の `inkling_offered()` も同じ条件でモデル選択肢に含める。どちらも変数値を子プロセスへ転送する処理ではない（`terminal/tools/strata_mcp.py:657-664`, `terminal/setup.py:10394-10400`, `terminal/setup.py:11783-11789`）。

## ログと測定値

環境変数を読み取ったこと自体を示すログはない。ソースが空ならセットアップは `no download source for {name} is configured` と表示し、ヒント `put the file in {folder} (or set STRATA_INKLING_SOURCE) and run this again` を示して終了コード 1 になる。候補取得に失敗して次へ進む場合は前節の警告を出す。成功時は通常の `download()` が `[ok] {what} downloaded` 等を表示する（`terminal/setup.py:10466-10485`, `terminal/setup.py:1039-1056`, `terminal/setup.py:3580-3589`）。

## 根拠

- `terminal/strata_control/inkling_family.py:121-180` — 変数名、読み取り、候補順、正規化、GGUF との関係。
- `terminal/data/inkling-sources.json:1-14` — 同梱の標準 `sources` / `gguf_sources`。
- `terminal/setup.py:10394-10400`, `terminal/setup.py:10458-10485`, `terminal/setup.py:10596-10601`, `terminal/setup.py:10646-10653`, `terminal/setup.py:11783-11789` — 選択肢への反映、取得経路、ローカルファイル経路、失敗時の処理。
- `terminal/strata_control/pictures.py:334-383`, `terminal/strata_control/pictures.py:426-430` — 設定辞書・明示 endpoint を使う画像ファイル取得経路。
- `terminal/tools/strata_mcp.py:657-664` — MCP の Inkling 掲載条件。
