# `LC_NUMERIC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

端末アプリの Drafting 制御が、このコンピューターの地域言語信号の一つとして `LC_NUMERIC` を読みます。DFlash2 の自動ドラフト語彙選択で、他の信号から日本語・中国語・韓国語が示されず、より優先される言語信号にも判定可能なものがなく、値から認識できる言語が得られた場合に選択へ影響します。モデル本体の語彙や通常の数値書式をこのコードが変更する変数ではありません。読み取りは `terminal/strata_control/drafting.py` の `os_language_signals`、選択は同ファイルの `auto_vocab` が行います（`terminal/strata_control/drafting.py:1323-1357,1425-1445`）。

## 値と判定

`os_language_signals(env=None)` は `env` を省略すると `os.environ` を使い、地域信号を作るときに `LC_NUMERIC` を `env.get(k, "")` で読みます。値が truthy の場合だけ文字列化して追加するため、未設定と空文字はどちらも候補になりません。空白だけの値は追加後、言語タグ解析で strip されて空となり、判定されません（`terminal/strata_control/drafting.py:1323-1337`）。

値は数値として解析されません。小文字化・前後空白の除去後、`.` より後ろを除き、`_` を `-` にして言語部分・スクリプト部分を照合します。`@` 以降は modifier として扱い、`cyrillic` / `arabic` / `latin` modifier などを判定します。未認識の値を拒否したり警告したりせず、言語信号なしとして扱います（`terminal/strata_control/drafting.py:1265-1296`）。

| `LC_NUMERIC` の値 | この値から得る信号の例 |
|---|---|
| 未設定、`""`、空白だけ | 信号を追加しない／判定なし |
| `ru_RU.UTF-8`、`uk_UA` | `cyrillic` |
| `fr_FR.UTF-8`、`de_DE` | `latin` |
| `ar_SA`、`fa_IR` | `arabic` |
| `zh_CN`、`ja_JP`、`ko_KR` | `cjk`。CJK 信号が一つでもあれば自動選択は既定語彙にする |
| `C`、`POSIX`、`C.UTF-8`、`POSIX.UTF-8` | 判定なし |
| `0`、`1`、`true`、`false`、その他の未知タグ | 数値・真偽値としての意味はなく、既知言語タグに一致しなければ判定なし |

解析は大文字小文字を区別せず、`.` より後ろの encoding 部分は無視します。言語・スクリプトが既知の集合に一致するかで判定し、範囲・数値境界はありません。たとえば不正な locale 文字列は例外や環境変数固有のエラーにせず、通常は空の判定になります（`terminal/strata_control/drafting.py:1257-1296`）。

## 有効になる条件

- `drafting.apply` の判定結果が DFlash2 であること。対象外モデル、DFlash2 を使わない選択、別 drafter になる経路では `auto_vocab` に到達しません（`terminal/strata_control/drafting.py:1704-1728,1739-1743,1757-1767`）。
- 保存済み `draft_vocab`、`args` または `user_args` の `--mtp-draft-vocab` があれば、それが優先され、コンピューター言語信号を読みません（`terminal/strata_control/drafting.py:1431-1433`）。
- エンジン形式がファイル指定形式（`FORM_FILE`）または不明で、現在の語彙ファイルがあること。別形式または現在のファイルがない場合は、言語判定より先に既定扱いになります（`terminal/strata_control/drafting.py:1434-1438`）。
- 言語信号は UI 群、地域群、キーボード群の順で優先されます。ただし、どの群にあっても CJK 信号が一つでもあれば `cjk` を選びます。CJK がなく複数の判定がある場合は、UI 群を先に、次に地域群、最後にキーボード群を走査し、最初に認識した信号を採用します。地域群の順は `LC_CTYPE`、`LC_TIME`、`LC_NUMERIC`、`LC_MONETARY` です（`terminal/strata_control/drafting.py:1334-1341,1299-1313`）。Windows では取得した OS の地域値が環境由来の地域値より前に、macOS では `AppleLocale` が前に追加されます（同 `:1339-1350`）。
- `latin`、`cyrillic`、`arabic` のいずれかが選ばれても、対応する同梱語彙ファイルが存在し、対象 drafter の語彙 ID 範囲に適合するときだけ差し替えます。条件を満たさなければ現在の語彙ファイルを維持します（`terminal/strata_control/drafting.py:1237-1238,1441-1445`）。

## 実行時の詳細

サーバーはエンジン起動用の引数を組み立てる際に `drafting.apply` を呼びます。DFlash2 の分岐では `auto_vocab` が呼ばれ、明示設定がない場合に `computer_language_signals()` から環境信号を取り、`vocab_for_languages` が語彙候補を決めます（`terminal/serve/server.py:3544-3563`; `terminal/strata_control/drafting.py:1355-1357,1425-1445,1745-1768`）。

`LC_NUMERIC` の値はこの呼び出し経路で読むたびに環境マップから取得し、モジュール読み込み時のキャッシュやプロセス起動時の保存はありません。選択は設定へ永続化せず、各起動時に再計算されます（`terminal/strata_control/drafting.py:1323-1329,1425-1429,1437-1438`）。この箇所は環境変数を設定・転送しません。

言語由来の語彙を採用した場合、`decision.vocab` に語彙名と判定理由が入り、サーバーの `announce` が真なら標準出力に `[strata] drafting: draft vocabulary: <ファイル名> (by this computer's language: <言語>)` を出します。既定語彙の場合も `draft vocabulary: <ファイル名> (the default)` が記録されます。これは選択を示すログで、`announce` が偽ならこの箇所からは出力されません（`terminal/strata_control/drafting.py:1432-1445,1764-1768`; `terminal/serve/server.py:3565-3578`）。

## 根拠

- `terminal/strata_control/drafting.py:1265-1296` — locale 風文字列から言語・スクリプト信号への判定。
- `terminal/strata_control/drafting.py:1299-1313` — UI・地域・キーボード信号の優先順位。
- `terminal/strata_control/drafting.py:1323-1357` — 環境マップから `LC_NUMERIC` を含む地域信号を読む処理と OS 固有信号の追加。
- `terminal/strata_control/drafting.py:1425-1445,1745-1768` — DFlash2 自動語彙の条件、明示設定の優先、ファイル確認、適用。
- `terminal/serve/server.py:3544-3563,3565-3578` — 起動用引数の構築時の呼び出しと語彙選択ログ。
