# `LC_MONETARY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata は `LC_MONETARY` を数値や真偽値の設定としては扱わず、地域ロケール文字列として読みます。確認できた用途は二つです。Linux のホスト地域 API では地域タグ候補として `LC_ALL`、`LANG` と優先順位を付けて参照し、Terminal の Drafting では他の環境由来の言語信号とともに語彙ファイル選択の候補にします（`app/host/server/region.mjs:49-52`; `terminal/strata_control/drafting.py:1333-1352`）。

## 値と判定

| 経路 | 未設定・空文字 | 設定時の扱い |
|---|---|---|
| ホスト地域 API（Linux） | JavaScript の `||` によりどちらも候補として飛ばされ、次の `LANG` が使われる | `LC_ALL` が truthy なら `LC_MONETARY` より優先。そうでなければ `LC_MONETARY`、次に `LANG`。数値変換や真偽値変換はしない。|
| Drafting の語彙選択 | `env.get(k, "")` が空文字なら地域候補リストに追加しない | 空でない値を `LC_CTYPE`, `LC_TIME`, `LC_NUMERIC`, `LC_MONETARY` の順にそのまま候補へ追加。|

ホスト地域 API の選ばれた文字列は前後空白を除き、最初の `.` または `@` 以降を削除し、`_` を `-` に置き換えます。言語要素は ASCII 英字2〜3文字、地域は後続要素のうち最初の ASCII 英字2文字だけを採用し、言語を小文字、地域を大文字にします。たとえば `ja_JP.UTF-8` は `ja-JP`、`C` / `POSIX` や不正な言語要素は locale / region とも `null` です。大文字小文字を区別しないのは `C` / `POSIX` 判定で、数値・範囲判定はありません（`app/host/server/region.mjs:14-23,49`）。

Drafting 側は locale 文字列を `script_of_language()` で分類します。空値、英語など分類対象外の言語は追加の語彙選択信号になりません。各値の文字列化・前後空白除去後に言語・script・modifier を見て、CJK 信号がどこか一つでもあれば既定の `cjk` 語彙になります。それ以外では、UI 信号、地域信号、キーボード信号の順に、最初の Cyrillic または対象 Latin 言語が選択を決めます（`terminal/strata_control/drafting.py:1255-1313`）。

## 有効になる条件

- ホスト API 経路で `LC_MONETARY` が地域タグ候補になるのは Linux のときだけです。Windows はレジストリ、macOS は `AppleLocale` を使い、この分岐では同変数を参照しません（`app/host/server/region.mjs:32-49`）。
- ホスト API では truthy な `LC_ALL` があればそちらが選ばれます。`LC_MONETARY` が無効なタグでも `LANG` へ再試行せず、その文字列を parse します。地域を得られなくても `locale -k int_curr_symbol` の出力から通貨コードを得る経路は別にあります（`app/host/server/region.mjs:49-52`）。
- Drafting 経路では Linux なら環境信号をそのまま使います。Windows では OS の UI / user locale 信号が環境信号より前に、macOS では優先言語 / `AppleLocale` が環境信号より前に追加されます（`terminal/strata_control/drafting.py:1333-1352`）。
- Drafting の環境信号は、DFlash2 が選ばれて `auto_vocab()` が呼ばれる場合だけ自動語彙に影響します。保存済み `draft_vocab`、引数または `user_args` の `--mtp-draft-vocab` があれば利用者指定が優先されます。エンジン形式がファイル指定に対応しない場合、現在の語彙ファイルがない場合、選ばれた同梱ファイルがない場合、またはそのファイルの ID がモデル語彙範囲に合わない場合は自動選択されません（`terminal/strata_control/drafting.py:1425-1445,1727-1743,1746-1782`）。
- 対応モデル、Drafting モード、エンジン形式や利用可能な drafter が満たされず DFlash2 にならない場合、`LC_MONETARY` による語彙選択は実行されません。サーバーは起動時に `drafting.apply()` を呼び、モデル名・backend などを渡します（`terminal/serve/server.py:3552-3563`; `terminal/strata_control/drafting.py:1704-1743`）。

## 実行時の詳細

ホスト地域 API は `GET /api/locale` ごとに `systemLocale()` を呼びます。通常経路では最初の呼び出しで `detectRegion()` の戻り値を module 内 `cached` に保存し、後続呼び出しはその値を返します。したがって最初の検出後に環境を変更しても通常経路では再読込されません。例外時は locale / region / currency / source をすべて `null` にします（`app/host/server/index.mjs:2211`; `app/host/server/region.mjs:32,49-65`）。

`STRATA_TEST_LOCALE` が非空で `STRATA_PACKAGED` が文字列として `1` ではない場合は、`systemLocale()` 呼び出しごとにそのテスト値を使い、`LC_MONETARY` を読む通常検出を通りません（`app/host/server/region.mjs:60-65`）。Linux の通常検出は `locale -k int_curr_symbol` も同期実行し、4秒の timeout を指定します。Strata は標準出力から3文字の通貨コードを抽出し、コマンド失敗は捕捉して通貨を `null` にします。このコマンド内部での環境変数解釈は Strata の挙動としては扱いません（`app/host/server/region.mjs:30-32,49-54`）。

Drafting の環境信号は `computer_language_signals()` から語彙選択時に取得されます。サーバーではモデル起動ごとに `drafting.apply()` が呼ばれ、選択した同梱語彙が使える場合は `--mtp-draft-vocab` としてエンジン引数へ渡されます。選択は設定に保存されず、各起動で再計算されます（`terminal/strata_control/drafting.py:1355-1357,1425-1445,1765-1782`; `terminal/serve/server.py:3556-3564`）。

## ログと測定値

DFlash2 の場合、語彙選択理由は `decision.vocab` に入り、`announce` が真であるサーバー起動では `[strata] drafting: ` に続けて表示されます。言語信号により同梱語彙を選んだ例の末尾は `(by this computer's language: de)`、既定語彙なら `(the default)`、明示指定なら `(set by you)` です。通常の地域 API 検出に専用ログはありません。検出に失敗してもその経路は空の地域情報を返し、専用の警告や終了処理はありません（`terminal/strata_control/drafting.py:1431-1445,1765-1768`; `terminal/serve/server.py:3565-3578`; `app/host/server/region.mjs:51-54`）。

この変数についての性能測定値は記載しません。`docs/DETAILS.md` に本挙動の追加説明は見つかりませんでした。

## 根拠

- ホスト地域検出と読み取り優先順位: `app/host/server/region.mjs:14-23,30-65`
- API ルート: `app/host/server/index.mjs:2211`
- Drafting の環境信号、言語分類、自動語彙選択: `terminal/strata_control/drafting.py:1255-1357,1425-1445`
- Drafting のモデル / engine 条件と引数反映: `terminal/strata_control/drafting.py:1691-1782`
- サーバー起動時の適用とログ: `terminal/serve/server.py:3552-3578`
