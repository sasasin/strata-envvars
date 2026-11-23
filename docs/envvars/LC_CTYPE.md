# `LC_CTYPE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata Terminal が DFlash2 の draft vocabulary を自動選択するときに、`LC_CTYPE` をコンピューターの地域言語シグナルの一つとして読みます。認識された言語・文字体系に応じて `draft_vocab_cyrillic.bin`、`draft_vocab_arabic.bin`、`draft_vocab_latin.bin` を選ぶか、既定の語彙ファイルを維持します。`LC_CTYPE` 自体がエンジンの locale を設定したり、通常の生成言語を選んだりする処理はありません。読み取りは `terminal/strata_control/drafting.py` の `os_language_signals()`、分類と選択は `script_of_language()`、`vocab_for_languages()`、`auto_vocab()` です（`terminal/strata_control/drafting.py:1234-1262,1265-1313,1323-1352,1425-1445`）。

## 値と判定

`os_language_signals()` は明示された `env` がなければ `os.environ` を使い、`env.get("LC_CTYPE", "")` が truthy の場合に限って値を地域シグナル一覧へ追加します。未設定と空文字は一覧に入りません。値は真偽値や数値としては parse されず、`script_of_language()` が文字列化し、前後空白を除去して小文字化した後、ロケールタグの言語・script・modifier を分類します（`terminal/strata_control/drafting.py:1265-1296,1323-1337`）。

| `LC_CTYPE` の値 | 読み取り・分類結果 |
|---|---|
| unset / `""` | 地域シグナルに追加されず、この変数からの選択効果なし。 |
| `ru_RU.UTF-8`、`uk_UA`、`sr_RS@cyrillic` | Cyrillic に分類。ほかに優先されるシグナルがなければ `cyrillic` 候補。 |
| `de_DE.UTF-8`、`fr_FR`、`sr_RS@latin` | 英語以外の Latin に分類。ほかに優先されるシグナルがなければ `latin` 候補。 |
| `ar_EG.UTF-8`、`fa_IR` | Arabic に分類し、ほかに優先されるシグナルがなければ `arabic` 候補。 |
| `ja_JP.UTF-8`、`zh-Hans`、`ko_KR` | CJK に分類し、他の言語シグナルにかかわらず既定の `cjk` 語彙を選ぶ。 |
| `C`、`POSIX`、`C.UTF-8`、`POSIX.UTF-8` | シグナルなし。 |
| `0`、`1`、`true`、`false`、空白だけ、未認識タグ | 設定有無を有効スイッチとして扱わない。空白だけは trim 後空、これらの文字列も既知の言語分類に一致せず、選択材料にならない。 |

分類は大文字小文字を区別しません。`_` は `-` と同様に扱われ、最初の `.` より後の encoding suffix は除かれます。`@` より後は modifier として扱われ、`@cyrillic` / `@latin` など既知の modifier が分類に使われます。数値全体の妥当性検査、locale 名の完全一致検証はありません（`terminal/strata_control/drafting.py:1265-1296`）。

## 有効になる条件

- `apply()` の判定結果が DFlash2 であること。対象モデル、利用可能な drafter、実行モードなどの条件で MTP / off になる場合、この語彙の自動選択には進みません（`terminal/strata_control/drafting.py:1704-1726,1744-1768`）。
- 利用者が `cfg["draft_vocab"]`、`--mtp-draft-vocab` の実行引数、または保存済み `user_args` で語彙を指定していないこと。指定があれば現在の語彙を保ち、「set by you」として優先されます（`terminal/strata_control/drafting.py:1425-1435`）。
- エンジン形式がファイル名を受け取る形式（`FORM_FILE`）または未特定で、現在の語彙パスがあること。ディレクトリ形式や語彙パスなしでは環境シグナル選択を行いません（`terminal/strata_control/drafting.py:1425-1437`）。
- `LC_CTYPE` 由来の選択は他のシグナルと合成されます。UI シグナル（`LANGUAGE`、`LC_ALL`、`LC_MESSAGES`、`LANG`）を先に確認し、地域シグナル内では `LC_TIME`、`LC_NUMERIC`、`LC_MONETARY`、`LC_CTYPE` の順です。どこかに CJK シグナルが一つでもあれば既定の `cjk` が優先されます。Windows では OS の UI 言語・ユーザ locale も先頭に加わり、macOS ではユーザ設定ファイルからの言語・locale も先頭に加わります（`terminal/strata_control/drafting.py:1299-1313,1323-1352`）。
- 選ばれた非既定語彙ファイルが存在し、モデルの語彙サイズに適合する必要があります。不在・不適合なら現在の語彙（通常は既定）に戻ります（`terminal/strata_control/drafting.py:1409-1422,1441-1445`）。

## 実行時の詳細

Terminal の起動設定を `apply()` が組み立て、DFlash2 の分岐で `auto_vocab()` を呼びます。明示指定がなければ `computer_language_signals()` から `os_language_signals()` を呼び、ここで `os.environ` を参照します。該当値を保持する `static` やモジュール cache はなく、選択結果は設定へ保存されず起動ごとに計算されます。したがって、プロセス環境が呼び出し前に変わっていれば次の評価で読み直されます（`terminal/strata_control/drafting.py:1323-1357,1425-1445,1744-1768`）。

環境シグナルに認識可能な言語がなくても、読み取り例外があっても、既定語彙に戻ります。認識された選択があっても語彙ファイルがモデルに適合しなければ同様です。最終的な語彙パスは `engine_flags()` の結果として DFlash2 のエンジン引数へ組み込まれます（`terminal/strata_control/drafting.py:1441-1445,1764-1781`）。この Strata 側コードが示す効果は語彙ファイルの選択と引数設定までです。エンジン内部での候補 token 生成への効果はこの変数の Strata 側動作としては扱いません。

## ログと測定値

`LC_CTYPE` の読み取り自体に固有のログや警告はありません。Server は `decision.vocab` がある場合に `[strata] drafting: ` と選択理由を標準出力へ出します。自動選択された場合の理由部分は `draft vocabulary: <ファイル名> (by this computer's language: <言語>)`、既定語彙の場合は `draft vocabulary: <ファイル名> (the default)` です（`terminal/strata_control/drafting.py:1431-1445,1766-1768`; `terminal/serve/server.py:3577-3578`）。`docs/DETAILS.md:382` には自動語彙選択全体の性能測定が記載されていますが、`LC_CTYPE` 単独の測定ではないため、ここでは変数固有の測定値として扱いません。

## 根拠

- `terminal/strata_control/drafting.py:1323-1357` — 環境マッピングと OS 別の言語シグナル収集。
- `terminal/strata_control/drafting.py:1265-1313` — locale 文字列の分類、シグナル優先順位、CJK の既定選択。
- `terminal/strata_control/drafting.py:1425-1445,1744-1781` — 利用者指定の優先、条件付き自動選択、fallback、エンジン引数への反映。
- `terminal/serve/server.py:3577-3578` — 選択理由の標準出力ログ。
- `docs/DETAILS.md:382` — 語彙自動選択の説明との照合（測定は `LC_CTYPE` 固有ではない）。
