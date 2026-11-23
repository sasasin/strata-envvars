# `LC_MESSAGES`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata Control は `LC_MESSAGES` を、このコンピューターの表示言語シグナルの一つとして読み、条件を満たす DFlash2 起動で使う draft vocabulary の自動選択に反映する。`LC_MESSAGES` 自体がエンジンの生成言語を設定したり、通常の MTP 起動を変更したりする処理ではない。読み取りは `terminal/strata_control/drafting.py` の `os_language_signals()`、選択は `auto_vocab()` と `apply()` にある（`terminal/strata_control/drafting.py:1323-1352,1425-1445,1746-1768`）。

## 値と判定

この値は真偽値や数値として parse されない。`os_language_signals()` は `LC_ALL`、`LC_MESSAGES`、`LANG` の順で、値が truthy なものだけ文字列にして `ui` リストへ加える。未設定と空文字は加えられず、空白だけの値は一度加わるが、後段の `script_of_language()` で trim されてシグナルなしになる（`terminal/strata_control/drafting.py:1333-1337,1265-1296`）。

| 条件 | 未設定 | 有効になる値（例） | シグナルにならない値（例） |
|---|---|---|---|
| `os_language_signals()` が環境を読む場合 | `LC_MESSAGES` を追加しない | `de_DE.UTF-8`、`ru_RU.UTF-8`、`zh_CN.UTF-8` など、後段で認識される言語・script tag | 空文字、空白のみ、`C`、`POSIX`、`C.UTF-8`、`POSIX.UTF-8`、認識対象外のタグ（例: `nonsense`） |

タグ判定では前後の空白を除き、小文字化し、`@modifier` と `.encoding` を外し、`_` を `-` として扱う。既知の言語コードまたは script 名を比較するため、比較は大文字小文字を区別しない。値全体の妥当性検証や locale のシステム設定は行わない。たとえば `1`、`true`、`0anything` は真偽値としての特別扱いを受けず、言語タグとして解釈され、既知タグに該当しなければ何も選ばない（`terminal/strata_control/drafting.py:1265-1296`）。

## 有効になる条件

- `drafting.apply()` が DFlash2 を選んで `decision.drafter == "dflash2"` となる必要がある。モデル、backend、利用可能な drafter・vocabulary、設定された drafting モードなどの上位判定により MTP または `off` が選ばれた場合、この読み取り・自動選択は通らない（`terminal/strata_control/drafting.py:1704-1726,1735-1768`）。
- `auto_vocab()` が自動選択を続ける必要がある。設定の `draft_vocab`、引数の `--mtp-draft-vocab`、または保存された `user_args` の同引数があれば利用者指定を優先する。また engine の形式が `FORM_FILE` でも未知 (`None`) でもない場合、または現在の vocabulary がない場合は既定選択で戻る（`terminal/strata_control/drafting.py:1425-1438`）。
- 読み取った言語の結果が `cyrillic`、`arabic`、または `latin` なら対応する同梱 vocabulary を候補にする。ただしファイルが存在し、`vocab_ids_fit()` がモデルの語彙サイズ内に収まると判定した場合だけ差し替える。それ以外は現在の既定 vocabulary のまま（`terminal/strata_control/drafting.py:1409-1422,1441-1445`）。
- どの入力言語シグナルにも中国語・日本語・韓国語系のタグがあれば `cjk`（既定）を維持する。それがなければ UI シグナルを地域形式より先に調べ、各グループでは最初に認識した script を選ぶ。`LC_MESSAGES` は UI グループ内で `LANGUAGE` の要素の後、`LC_ALL` の後、`LANG` の前に置かれる。したがって先行する認識可能な値により選択が決まることがあり、どこかに CJK シグナルがあればそれが優先する（`terminal/strata_control/drafting.py:1333-1336,1299-1313`）。
- この判定箇所自体には OS・CUDA/HIP/Metal/SYCL build macro による分岐はない。OS 判定は同じ関数の Windows/macOS 固有シグナル追加に使われるが、環境値の取得は共通処理である（`terminal/strata_control/drafting.py:1327-1352`）。

## 実行時の詳細

`computer_language_signals()` が `os_language_signals()` を呼び、引数で環境を差し替えない通常経路では呼び出し時点の `os.environ` を参照する。モジュール起動時の cache はなく、DFlash2 の各 `apply()` で自動選択に到達するたびに読み直す。選択結果は run config に保存せず、その起動の engine 引数に vocabulary path として組み立てる（`terminal/strata_control/drafting.py:1323-1337,1355-1357,1425-1429,1437-1445,1764-1782`）。

`LC_MESSAGES` の値は `LANGUAGE`、`LC_ALL`、`LANG` と合わせて `ui` 信号に入る。`LANGUAGE` は `:` で分割され、空要素を除いてから追加される。地域形式の `LC_CTYPE`、`LC_TIME`、`LC_NUMERIC`、`LC_MONETARY` は別の `region` 群に入り、UI 群より後に判定される（`terminal/strata_control/drafting.py:1333-1337,1299-1313`）。環境へのアクセスで例外が起きた場合はその信号群を空にし、`auto_vocab()` 全体で例外が起きた場合も既定 `cjk` を使う（`terminal/strata_control/drafting.py:1333-1338,1436-1445`）。

選ばれたファイルは DFlash2 の `--mtp-draft-vocab FILE` 引数（古い engine 形式では `--mtp DIR` が指す `draft_vocab.bin`）に使われる。server はサポートログとして `[strata] drafting: ...` を標準出力へ出すが、選択理由の文字列は記録用であり、これ自体は追加設定ではない（`terminal/strata_control/drafting.py:1019-1025,1766-1782`; `terminal/serve/server.py:3577-3578`）。`docs/DETAILS.md` も、利用者が選択を保存していない場合にコンピューターの言語で vocabulary を選び、起動ごとに決めて保存しない説明をしている（`docs/DETAILS.md:382`）。

## ログと測定値

server 経路では `decision.vocab` が空でない場合、標準出力へ `[strata] drafting: <理由>` を出す。自動選択できた場合の理由は `draft vocabulary: <ファイル名> (by this computer's language: <言語>)`、利用者指定なら `(set by you)`、自動変更しない場合は `(the default)` を含む。環境読み取りが失敗した場合もこの判定は既定 vocabulary を選ぶため、環境値の失敗だけでログエラーやプロセス終了にはならない（`terminal/strata_control/drafting.py:1431-1445`; `terminal/serve/server.py:3577-3578`）。

## 根拠

- 候補一覧への掲載: `docs/envvars/000_envvers.md:530`。
- 環境値の取得と OS 固有シグナル: `terminal/strata_control/drafting.py:1323-1352`。
- 言語タグの分類と優先順: `terminal/strata_control/drafting.py:1265-1313`。
- DFlash2 自動選択、利用者指定の優先、既定 fallback: `terminal/strata_control/drafting.py:1409-1445,1746-1782`。
- server の記録ログ: `terminal/serve/server.py:3577-3578`。
- 関連する利用者向け説明: `docs/DETAILS.md:382`。
