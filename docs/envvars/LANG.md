# `LANG`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata は `LANG` を3通り扱う。Linux の `/api/locale` では地域タグ候補として `LC_ALL` と `LC_MONETARY` の後に評価する。端末の起動処理では、DFlash2 の draft vocabulary を自動選択するための表示言語シグナルとして読む。Web の coding agent 起動時には、環境変数名の許可リストに `LANG` が含まれるため、値があれば agent の子プロセス環境へ渡す。いずれも `LANG` 自体を変更せず、端末の自動選択はユーザーが保存・指定した語彙を優先する（`app/host/server/region.mjs:32-52,58-65`、`terminal/strata_control/drafting.py:1323-1357,1425-1445`、`app/host/server/agent/harness-runtime.mjs:20-36,75-83`）。

## 値と判定

| 読み取り経路 | unset / 空文字 | 有効になる値 | その他の値 |
|---|---|---|---|
| Linux 地域情報 (`detectRegion`) | `env.LC_ALL || env.LC_MONETARY || env.LANG` の順に選ぶ。`LANG` が unset または空なら候補にならない。 | locale 文字列を `parseLocaleTag` に渡す。前後空白を除き、最初の `.` または `@` 以降を落とし、`_` を `-` に置換。先頭が2～3文字の英字なら小文字の言語コードとし、後続要素の2文字英字を地域コードとして採る。例 `de_DE.UTF-8` → `de-DE` / `DE`。 | 空、`C` / `POSIX`（大文字小文字を問わない）、不正な先頭言語タグでは locale・region は null。`en` のように地域部分がなければ locale は `en`、region は null。文字列全体の locale 検証はしない。 |
| Draft vocabulary 用言語シグナル (`os_language_signals`) | `env.get("LANG")` が falsey のときリストに加えない。unset と空文字は同じ扱い。 | 空でない値をそのまま UI シグナルに加え、`script_of_language` が判定する。例 `ru_RU.UTF-8` → Cyrillic、`de_DE.UTF-8` → Latin、`ja_JP.UTF-8` → CJK。 | trim 後に空になる空白だけの値は何のシグナルにもならない。大文字小文字を区別せず判定し、`.` より後は無視する。未知の言語、`C`、`POSIX` は分類なし。 |
| coding agent 子プロセス (`agentEnvironment`) | `undefined` の値は渡さない。空文字は undefined ではないため許可リストを通れば渡す。 | `KEEP` 正規表現は大文字小文字を無視して名前 `LANG` を許可する。値の内容は解釈しない。 | 他の値検証・変換なし。`externalEnvironment` が元環境を選んだ後に、秘密名の除外と許可リストを適用する。 |

根拠: `app/host/server/region.mjs:14-22,32-52`、`terminal/strata_control/drafting.py:1265-1296,1323-1337`、`app/host/server/agent/harness-runtime.mjs:20-36`。

## 有効になる条件

- 地域情報の読み取りで `LANG` が参照されるのは Linux 系の分岐だけ。優先順位は `LC_ALL`、`LC_MONETARY`、`LANG`。Windows はレジストリ、macOS は `defaults read -g AppleLocale` を使うため `LANG` をこの経路では読まない（`app/host/server/region.mjs:32-52`）。
- `/api/locale` は `systemLocale()` を呼ぶ。初回の通常呼び出し結果をプロセス内 `cached` に保存し、以後再利用する。したがって通常起動後に環境値を変えても反映されない。`STRATA_TEST_LOCALE` が設定され `STRATA_PACKAGED !== '1'` の場合はテスト用値を返し、OS locale 判定を通らない（`app/host/server/index.mjs:2211`、`app/host/server/region.mjs:58-65`）。
- Draft vocabulary の自動選択は、サーバーの `drafting.apply` が DFlash2 分岐へ進んだ場合に限る。保存済み `draft_vocab`、実行引数 `--mtp-draft-vocab`、または保存済み `user_args` の同引数があればユーザー指定が優先される。engine の形式が `FORM_FILE` 以外、または現在の語彙ファイルがない場合も言語による選び直しをしない（`terminal/strata_control/drafting.py:1425-1438,1746-1768`）。
- Draft vocabulary は `LANG` だけでは決まらない。`LANGUAGE`、`LC_ALL`、`LC_MESSAGES` も同じ UI シグナル群に加わる。Windows の UI locale と macOS の設定言語も追加される。CJK シグナルが一つでもあれば既定の CJK 語彙を選ぶ。そうでなければ UI シグナル、地域シグナル、keyboard シグナルの順で最初の対応言語を採る（`terminal/strata_control/drafting.py:1299-1313,1323-1352`）。
- 言語により選ばれた非既定語彙ファイルが存在し、`vocab_ids_fit` でモデル語彙サイズに収まる場合だけ採用される。ファイルがない、または適合しない場合は現在の語彙ファイルへ戻る（`terminal/strata_control/drafting.py:1441-1445`）。
- coding agent への転送は agent プロセス開始時に `agentEnvironment(process.env, ...)` が環境のフィルター済みコピーを作る場合に限る。AppImage 内では `externalEnvironment` が元の起動環境を選ぶため、起動環境に `LANG` が存在しなければ値は補われない（`app/host/server/agent/harness-runtime.mjs:25-36,75-83`、`app/host/server/external-env.mjs:63-70`）。

## 実行時の詳細

- Linux の `detectRegion` は選んだ locale を `parseLocaleTag` に渡す一方、通貨コードについて別途 `locale -k int_curr_symbol` を実行して出力を読む。成功し、region または通貨が得られた場合に `source: 'linux'` を返す。コマンド実行または解析で例外が起きた場合は `NONE`（すべて null）を返し、例外を外へ出さない。`LANG` が region のない言語タグでも、通貨が取得されれば結果オブジェクトが返る（`app/host/server/region.mjs:30-55`）。
- 端末の `os_language_signals()` は `os.environ` を関数呼び出しごとに参照し、関数内またはモジュール内の cache はない。`auto_vocab()` も各該当起動でこの関数を呼び、言語に基づく選択は config に書き戻さない（`terminal/strata_control/drafting.py:1323-1357,1425-1445`）。
- `script_of_language` は言語コードや明示 script/modifier を分類する。CJK のシグナルがどこかにあれば CJK 語彙のままにし、それ以外は優先順の最初の Cyrillic / Arabic / 非英語 Latin 語彙を使う。英語だけ、未知の言語、`C` / `POSIX` など分類できるシグナルがなければ既定の CJK 語彙を維持する（`terminal/strata_control/drafting.py:1255-1313`）。
- coding agent には Strata が `LANG` を環境コピーへ保持して子 Node プロセスへ渡す。Strata は値を解析せず、子プロセス側の利用方法もここでは扱わない（`app/host/server/agent/harness-runtime.mjs:25-36,75-83`）。

## ログと測定値

- Linux の地域情報読み取りには `LANG` 固有のログや警告はない。`/api/locale` は locale、region、currency、source を JSON で返し、判定全体が失敗した場合は全フィールド null の結果になる（`app/host/server/index.mjs:2211`、`app/host/server/region.mjs:12,52-55`）。
- DFlash2 の起動を通知する経路では、サーバーが `[strata] drafting: {decision.vocab}` を stdout に出す。自動選択時の値は `draft vocabulary: {ファイル名} (by this computer's language: {language})`、既定値の場合は `draft vocabulary: {ファイル名} (the default)`。この行はサポート用ログで、語彙ファイルが変わることによる生成内容や精度の保証を示さない（`terminal/strata_control/drafting.py:1431-1445,1766-1768`、`terminal/serve/server.py:3565-3578`）。
- `docs/DETAILS.md:382` は自動選択を Cyrillic / Latin と説明しているが、調査対象コードは Arabic も分類・選択する（`terminal/strata_control/drafting.py:1237-1238,1255-1261,1282-1296`）。また資料の測定値は同行に記載される RTX PRO 5000 (IQ3_S) の例であり、`LANG` の一般的な性能効果を示す値ではない。

## 根拠

- `app/host/server/region.mjs:14-22,30-65` — locale タグの処理、Linux の環境変数優先順、結果 cache。
- `app/host/server/index.mjs:2211` — `/api/locale` からの呼び出し。
- `terminal/strata_control/drafting.py:1255-1357,1425-1445,1691-1782` — 言語分類、環境読み取り、DFlash2 語彙選択と優先条件。
- `terminal/serve/server.py:3555-3578` — 起動時適用と stdout ログ。
- `app/host/server/agent/harness-runtime.mjs:20-36,75-83`、`app/host/server/external-env.mjs:63-70` — agent 子プロセスへの環境転送。
- `docs/DETAILS.md:382` — draft vocabulary の説明と測定例。
