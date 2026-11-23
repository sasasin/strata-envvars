# `LC_TIME`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Terminal の Control は `LC_TIME` を地域形式の言語タグとして読み、DFlash2 が使う draft vocabulary の自動選択に利用する。日付・時刻の表示形式を Strata が設定する処理はこの参照箇所にはない。`os_language_signals()` が地域シグナルへ値を追加し、`auto_vocab()` がそのシグナルを選択関数へ渡す（`terminal/strata_control/drafting.py:1323-1337,1436-1445`）。

この値は起動設定の自動選択に使われるもので、生成結果の言語を指定したり、常に DFlash2 の語彙を変更したりするものではない。DFlash2 の対象モデル・実行経路に限り、後述の条件がそろうと選ばれた語彙ファイルをエンジン引数へ渡す（`terminal/strata_control/drafting.py:1425-1445,1745-1771`）。

## 値と判定

Strata は `os.environ`（または関数に明示して渡された mapping）の `.get("LC_TIME", "")` を用い、値が truthy の場合にのみ `str()` で文字列化して地域シグナルへ追加する。数値変換や許容値一覧との完全一致検査はしない（`terminal/strata_control/drafting.py:1323-1337`）。

続く `script_of_language()` は前後空白を除去し、小文字化して locale タグを分類する。`@` より後ろを modifier として分け、`.` より後ろの文字コード指定を除き、`_` を `-` として分割した先頭言語コードおよびサブタグを判定する。認識済みの言語コード・script・modifier なら `cjk` / `cyrillic` / `arabic` / `latin` 等を返し、それ以外は空のシグナルになる。したがって値全体の厳密な locale 検証ではなく、認識可能な先頭コードやタグを含む値は受理され得る（`terminal/strata_control/drafting.py:1255-1296`）。

| 条件 | 未設定 | 自動分類へ渡る例 | シグナルにならない例 |
|---|---|---|---|
| 全 OS の環境 mapping | `LC_TIME` がない場合は空文字扱いで省略 | `ru_RU.UTF-8` → Cyrillic、`de_DE.UTF-8` → Latin、`zh_CN` → CJK | 空文字は省略。`C`、`POSIX`、`C.UTF-8`、`POSIX.UTF-8` は分類なし。`0anything` や `TRUE` も認識コードに一致せず分類なし |

大文字小文字は区別せず、前後空白は除去される。たとえば `RU_ru` も `ru` として分類される。数値としての妥当性、文字列全体の厳密な形式、`0` / `1` の真偽値は検査しない。空文字は設定済みとして扱われない（`terminal/strata_control/drafting.py:1265-1296,1333-1337`）。

## 有効になる条件

- `drafting.apply()` の判定が `dflash2` になり、DFlash2 用語彙の自動選択まで到達すること。DFlash2 以外の drafter、非対応モデル、利用不能な構成ではこの選択処理は行われない（`terminal/strata_control/drafting.py:1704-1726,1745-1767`）。
- `draft_vocab` の保存済み選択、`--mtp-draft-vocab`（引数または設定内 `user_args`）がないこと。いずれかがあれば利用者指定が優先され、コンピューターの言語シグナルは使われない（`terminal/strata_control/drafting.py:1425-1438`）。
- エンジン形式が `FORM_FILE` または不明 (`None`) で、現在の語彙ファイルがあること。形式が `FORM_DIR` / `FORM_NONE`、または現在のファイルがない場合はコンピューターの言語による選択を行わず既定語彙を維持する（`terminal/strata_control/drafting.py:1427-1435`）。
- どの UI・地域・キーボードシグナルにも中国語・日本語・韓国語系が含まれないこと。CJK シグナルが一つでもあれば既定の `cjk` を選ぶ。CJK がなく、認識できる Cyrillic / Arabic / Latin 系シグナルがある場合は、その候補が語彙選択に使われる（`terminal/strata_control/drafting.py:1234-1245,1255-1313`）。
- `LC_TIME` は地域シグナル一覧の2番目で、`LC_CTYPE` の後、`LC_NUMERIC` と `LC_MONETARY` の前に追加される。UI シグナルが候補を決めなければ、地域一覧内の先行する認識済みシグナルが `LC_TIME` より優先される。Windows のユーザーロケール、および macOS の `AppleLocale` は環境由来の地域シグナルより前に置かれる（`terminal/strata_control/drafting.py:1333-1350`）。
- `vocab_for_languages()` 中に例外が起きた場合も `cjk` 既定へ戻る。選択した同梱ファイルが存在し、対象モデルの語彙 ID 範囲に適合する場合に限り、そのファイルへ切り替わる（`terminal/strata_control/drafting.py:1410-1422,1436-1445`）。

## 実行時の詳細

サーバーが起動ごとにエンジン引数を組み立てる際、`terminal/serve/server.py` から `drafting.apply()` を呼ぶ。DFlash2 の場合、設定済みの語彙指定がなければ `auto_vocab()` が `computer_language_signals()` を呼び、現在の環境から `LC_TIME` を含む地域シグナルを集める。値をモジュールや関数の static cache に保存する処理はなく、`auto_vocab()` の説明どおり選択は各起動で再計算され、設定ファイルへ書き込まれない（`terminal/serve/server.py:3547-3563`; `terminal/strata_control/drafting.py:1355-1357,1425-1445,1764-1768`）。

選択された語彙ファイルは通常 `--mtp-draft-vocab <file>` としてエンジン引数に設定される。エンジンが `--mtp DIR` 形式しか扱えない場合は親フォルダーを `--mtp` に渡す（`terminal/strata_control/drafting.py:1019-1025,1764-1781`）。

## ログと測定値

サーバー起動時に `announce` が真で、`decision.vocab` が設定されている場合、stdout に `[strata] drafting: ` と選択理由の行を出す。環境由来の語彙が適用されれば、たとえば `drafting: draft vocabulary: <file> (by this computer's language: ru)` の形式になる。利用者指定なら `(set by you)`、既定語彙なら `(the default)` と出る。`announce` が偽の場合、この箇所の行は出ない（`terminal/serve/server.py:3565-3578`; `terminal/strata_control/drafting.py:1432-1445`）。

この環境変数に個別に結び付いた測定値は記載しない。`docs/DETAILS.md:382` にコンピューターの言語を使う語彙自動選択と測定例があるが、それらは `LC_TIME` 単独の効果を測定したものではない。

## 根拠

- `terminal/strata_control/drafting.py:1323-1337` — 環境 mapping の選択、`LC_TIME` を含む地域シグナルの読み取り。
- `terminal/strata_control/drafting.py:1255-1313` — locale タグの分類と、UI・地域・キーボード間の語彙選択規則。
- `terminal/strata_control/drafting.py:1425-1445,1745-1781` — 利用者指定との優先関係、DFlash2 語彙の自動選択、実行引数への設定。
- `terminal/serve/server.py:3547-3578` — サーバー起動時の呼び出しと観測可能なログ。
- `docs/DETAILS.md:382` — 自動選択の説明との照合（測定値は `LC_TIME` 単独の根拠として使用していない）。
