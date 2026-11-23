# `LC_ALL`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata は `LC_ALL` を Linux 系の地域情報検出と、Control が DFlash2 用語彙ファイルを自動選択する際の言語シグナルに使う。また、Agent の更新チェックポイントで Git を呼ぶときは、親プロセスの値を引き継がず `C` に置き換えて子プロセスへ渡す。GPU エンジンの環境変数として読む箇所は見つからなかった。

地域情報検出では、Linux 系の分岐で `LC_ALL`、`LC_MONETARY`、`LANG` の順に最初の空でない値を選び、地域タグを解析する。`/api/locale` がこの結果を返す。Windows と macOS の分岐では `LC_ALL` を参照せず、それぞれの OS 設定を読む（`app/host/server/region.mjs:32-55`、`app/host/server/index.mjs:2211`）。

Control の言語シグナルでは、`LC_ALL` は `LANGUAGE`、`LC_MESSAGES`、`LANG` とともに UI 言語グループへ追加される。DFlash2 が選択された起動で自動選択条件を満たすと、その言語に対応するドラフト語彙ファイルをエンジン引数へ設定する。これはドラフト語彙の選択であり、Strata が生成結果や性能への影響を測定・保証するものではない（`terminal/strata_control/drafting.py:1323-1352,1425-1445,1764-1768`）。

## 値と判定

| 読み取り経路 | unset | 設定時に使われる値 | 空文字・無効値 |
|---|---|---|---|
| 地域情報（Linux 系） | `LC_MONETARY`、次に `LANG` へ進む | `LC_ALL || LC_MONETARY || LANG` のうち最初の truthy 値を `parseLocaleTag` に渡す。例: `de_DE.UTF-8` は `de-DE`、地域 `DE` として扱われる | 空文字は次の変数へ進む。非空の不明値は `LC_MONETARY` / `LANG` にフォールバックせず解析結果が空になる。前後空白を除去し、最初の `.` または `@` 以降を捨て、`_` を `-` に置換する。言語部は ASCII 2–3 文字のみ、地域部は後続要素の ASCII 2 文字のみ。`C` / `POSIX` は大文字小文字を区別せず空扱い。たとえば `C`、`POSIX`、`123_US` は地域タグにならない（`app/host/server/region.mjs:14-22,49`） |
| 用語選択（Control） | UI シグナルには追加されない | 空でない文字列をそのまま UI シグナルへ追加し、後段で言語タグとして分類する。例: `ru_RU.UTF-8` は `ru`（Cyrillic）、`de_DE` は `de`（Latin）として分類される | 空文字は追加されない。値の書式検証は収集時には行わず、後段が認識しない言語・スクリプトなら選択材料にならない。`C`、`POSIX`、空白だけの値も有効なスクリプトシグナルにならない。大文字小文字は小文字化して分類される（`terminal/strata_control/drafting.py:1265-1296,1333-1337`） |
| チェックポイントの Git 子プロセス | 親の `process.env` を展開した後に `LC_ALL='C'` を設定 | 常に文字列 `C` を子の `env` に明示する | 親の値が未設定・空・別の値のいずれでも、Strata が子プロセス用環境で `C` に置き換える（`app/host/server/agent/update-checkpoint.mjs:8-11`） |

地域情報経路のタグ解析は locale 名を全体として厳密検証するものではなく、修飾子や encoding 部分を切り捨ててから判定する。`LC_ALL=C.UTF-8` は `C` となり、地域なしとして扱われる。`LC_ALL=de_DE@euro` は `de-DE` として扱われる（`app/host/server/region.mjs:14-22`）。

用語選択では `LC_ALL` の文字列全体を環境変数側で比較せず、`script_of_language` が空白除去・小文字化・encoding/modifier 除去・区切り変換をして分類する。`0`、`true`、`false` も特別な boolean 値ではなく、未知の言語タグとして扱われる（`terminal/strata_control/drafting.py:1265-1296,1333-1337`）。

## 有効になる条件

- 地域情報 API では `process.platform` が `win32` / `darwin` 以外のときだけ `LC_ALL` を選択に使う。Windows はレジストリ、macOS は `defaults read -g AppleLocale` を読む。Linux 系経路で `LC_ALL` が空なら `LC_MONETARY`、`LANG` の順に代替される（`app/host/server/region.mjs:32-52`）。
- `/api/locale` の通常応答は `systemLocale()` のキャッシュを使う。最初の呼び出しで検出結果を保存し、その後の `LC_ALL` 変更はこのプロセスでは反映されない。`STRATA_TEST_LOCALE` が truthy で、かつ `STRATA_PACKAGED !== '1'` の場合はそちらを毎回優先し、`LC_ALL` による検出・キャッシュを通らない（`app/host/server/region.mjs:58-65`）。
- Control では自動検出を使う前に、保存済み `cfg['draft_vocab']` または `--mtp-draft-vocab` の指定があれば利用者の選択が優先される。自動選択は DFlash2 が最終的に選ばれた起動だけで呼ばれる（`terminal/strata_control/drafting.py:1431-1445,1757-1768`）。
- 自動選択は `form` が `None` または `FORM_FILE` で、現在の語彙ファイルが存在するときだけ言語シグナルを使う。別形式や語彙ファイルなしなら既定の現在値を返す。非 CJK の分類結果も、対応する同梱ファイルがあり、語彙 ID がモデルの語彙範囲に合う場合だけ採用される。例外、ファイル欠落、適合失敗時は現在の語彙へ戻る（`terminal/strata_control/drafting.py:1425-1445`）。
- 言語シグナルは `computer_language_signals()` から `os.environ` を読むため、Control プロセスの現在の環境が対象になる。関数内にキャッシュはなく、`drafting.apply` の DFlash2 起動処理ごとに判定される（`terminal/strata_control/drafting.py:1323-1329,1355-1357,1764-1768`）。
- UI シグナルの先頭には `LANGUAGE` のコロン区切り要素が入り、その後 `LC_ALL`、`LC_MESSAGES`、`LANG` の順で加わる。CJK 言語・スクリプトが UI / 地域 / キーボードのどこかにあれば既定 `cjk` が選ばれる。それがなく、UI に認識対象の Cyrillic / Arabic / 非英語 Latin のシグナルがあれば、UI 内で最初に該当したものが選択される。したがって `LC_ALL` が有効でも `LANGUAGE` のシグナルや他のグループによって結果が変わり得る（`terminal/strata_control/drafting.py:1299-1313,1333-1336`）。
- Agent の更新チェックポイントでは `workspaceState` が Git コマンドを実行するたび、親環境をコピーして `LC_ALL: 'C'` を上書きする。これは `LC_ALL` を読んで分岐する経路ではなく、親の設定値にかかわらず固定値を渡す処理である（`app/host/server/agent/update-checkpoint.mjs:8-22`）。
- Agent Harness の子プロセス環境では `KEEP` が `LC_ALL` を許可リストに含め、`agentEnvironment` が `externalEnvironment(base)` から得た値を通す。Harness 起動時はその環境を `spawn` に渡す。AppImage では `externalEnvironment` が元の起動環境を使う場合があり、外部環境を復元できない場合には AppImage 専有項目を除いた環境を使う（`app/host/server/agent/harness-runtime.mjs:20-36,75-83`、`app/host/server/external-env.mjs:28-40,43-70`）。

## 実行時の詳細

`/api/locale` は GET のたびに `systemLocale()` を呼ぶが、通常の結果は初回だけ `detectRegion()` で計算して `cached` に保存される。Linux 系経路では `LC_ALL` などから選んだ値のタグ解析とは別に、`locale -k int_curr_symbol` を実行して、その標準出力から通貨コードを読み取る。コマンド実行は 4 秒 timeout 付きで、例外時は通貨情報を `null` とする。タグ解析も通貨コマンドも失敗し、地域情報もなければ `NONE`（locale / region / currency / source が null）を返す（`app/host/server/region.mjs:30-55,58-65`）。

Control の `os_language_signals` は `env` 引数がなければ `os.environ` を用い、設定値が truthy な `LC_ALL` を UI シグナルへ追加する。`vocab_for_languages` がそれを他の UI / 地域 / キーボードシグナルと判定し、`auto_vocab` は利用者指定がない場合に限って語彙を返す。採用時は `drafting.apply` が `engine_flags` の作成にそのファイルを渡し、Strata が開始用引数を組み立てる。値や選択は設定ファイルに自動保存されず、次回起動時に再判定される（`terminal/strata_control/drafting.py:1323-1357,1425-1445,1764-1768`）。

チェックポイント処理は `workspaceState` 内の各 `git` 呼び出しで `{ ...process.env, LC_ALL: 'C' }` を作り、`execFile` に渡す。親プロセスの環境変化が後続呼び出しにあれば他の変数は再コピーされるが、`LC_ALL` は毎回 `C` で上書きされる（`app/host/server/agent/update-checkpoint.mjs:7-22`）。

Harness は起動時に `agentEnvironment(process.env, ...)` で環境を構築する。許可リストにある `LC_ALL` の値は子の環境に引き継がれ、起動後に親の環境を変えても既に起動した Harness の環境は変わらない（`app/host/server/agent/harness-runtime.mjs:20-36,75-83`）。

## ログと測定値

`/api/locale` は検出結果を JSON として返す。地域検出のために `locale` コマンドを起動できない、timeout する、または出力から通貨コードを得られない場合、Strata はこの経路で警告ログを出さず、通貨を `null` にする。外側の検出例外も `NONE` に落とす（`app/host/server/region.mjs:30-55`）。

語彙自動選択処理は `draft vocabulary: <file> (by this computer's language: <language>)` または `(the default)` 等の理由文字列を `Decision.vocab` に格納するが、このリポジトリ内でその文字列をログ出力する箇所は確認できなかった。LC_ALL 別の測定値は確認できず、`docs/DETAILS.md` にも LC_ALL の記載はない（`terminal/strata_control/drafting.py:1431-1445,1764-1768`）。

## 根拠

- 地域タグの解析と platform 分岐: `app/host/server/region.mjs:14-22,30-65`
- `/api/locale` からの呼び出し: `app/host/server/index.mjs:2211`
- Control の言語分類と環境変数読取: `terminal/strata_control/drafting.py:1265-1313,1323-1357`
- DFlash2 起動時の優先順位・語彙ファイル判定・引数設定: `terminal/strata_control/drafting.py:1425-1445,1757-1768`
- Git チェックポイント子プロセスへの固定値設定: `app/host/server/agent/update-checkpoint.mjs:7-22`
- Harness 環境の許可と転送: `app/host/server/agent/harness-runtime.mjs:20-36,75-83`、`app/host/server/external-env.mjs:28-40,43-70`
