# `LANGUAGE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

Terminal の起動処理が DFlash2 用 draft vocabulary を自動選択するとき、`LANGUAGE` の言語タグをコンピューターの UI 言語信号として使う。これは Strata の UI 翻訳言語を切り替える設定ではない。自動選択されたファイルは DFlash2 起動引数 `--mtp-draft-vocab`（一部の旧 engine 形式では `--mtp` のディレクトリ引数）に渡される。読み取りは `terminal/strata_control/drafting.py` の `os_language_signals`、選択と引数への反映は同ファイルの `auto_vocab` と `engine_flags` で行う（`terminal/strata_control/drafting.py:1323-1357, 1425-1445, 1019-1025, 1764-1781`）。

## 値と判定

Strata は値を真偽値や数値に変換しない。`env.get("LANGUAGE", "").split(":")` でコロン区切りにし、空要素を除いて UI 言語候補へ追加する。その後 `script_of_language` が各タグを前後空白除去・小文字化し、`_` を `-` と同等に扱い、`.` 以降の locale encoding を切り落として言語・script・`@modifier` を判定する（`terminal/strata_control/drafting.py:1265-1296, 1333-1336`）。

| `LANGUAGE` の状態・例 | UI 信号としての扱い |
|---|---|
| 未設定 | 空文字を分割した空要素は除かれ、`LANGUAGE` からは信号なし。ほかの OS / locale 信号は引き続き調べる。 |
| 空文字、`:`、`::` | 空要素を除くため `LANGUAGE` からは信号なし。 |
| `ru:de` | 候補順は `ru`, `de`。CJK 信号がどこにもなければ、最初に認識された非英語 script の候補で決めるため `ru` が選ばれる。 |
| `zh:ru` | CJK 信号が一つでもあれば他の候補より優先して既定の CJK vocabulary を選ぶ。 |
| `ru_RU.UTF-8`, `sr-Latn-RS`, `sr_RS@latin` | 区切り・encoding・modifier を処理して、それぞれ Cyrillic または Latin script として判定する。 |
| `en`, `C`, `POSIX`, `0`, `false`、未知のタグ | エラーにはせず、そのタグ単独では非既定 vocabulary を選ばない。英語・`C` / `POSIX`・未知 script は分類なし。 |

大文字小文字は区別しない。`true` / `1` のような有効値規則はなく、空白だけの要素も分類なしになる。受理範囲は数値境界ではなく、コード内の言語・script 集合（CJK、Cyrillic、Arabic、Latin-script の非英語）による（`terminal/strata_control/drafting.py:1255-1262, 1265-1296`）。

## 有効になる条件

- DFlash2 がこの起動で選ばれている必要がある。MTP または drafting off の分岐では `auto_vocab` を呼ばない（`terminal/strata_control/drafting.py:1746-1768`）。
- 利用者が `cfg["draft_vocab"]` を保存している、または `--mtp-draft-vocab` を実引数 / 保存済み `user_args` で指定している場合はその選択が優先され、コンピューターの言語信号を読まない（`terminal/strata_control/drafting.py:1425-1433`）。
- engine 形式が `FORM_FILE`（`--mtp-draft-vocab FILE` 対応）または不明 (`None`) で、現在の vocabulary ファイル `current` が存在する必要がある。別形式 (`FORM_DIR`, `FORM_NONE`) または `current is None` なら既定のまま戻る（`terminal/strata_control/drafting.py:1425-1438`）。
- 認識された非 CJK 言語により `cyrillic`、`arabic`、`latin` が選ばれた場合でも、同梱ファイルが存在し、その ID がモデル vocabulary の範囲に収まる必要がある。満たさない場合は既定ファイルへ戻る（`terminal/strata_control/drafting.py:1439-1445, 1409-1422`）。
- UI 信号の優先順は `LANGUAGE` のリスト、`LC_ALL`、`LC_MESSAGES`、`LANG`。地域信号 (`LC_CTYPE`, `LC_TIME`, `LC_NUMERIC`, `LC_MONETARY`) はその後、キーボード信号はさらに後で判定される。ただし全信号のどこかに中国語・日本語・韓国語または対応 script があれば既定 vocabulary が優先される。残りの信号に Cyrillic と Latin の両方があれば UI、地域、キーボードの順で最初に見つかったものが決める（`terminal/strata_control/drafting.py:1299-1313, 1333-1352`）。
- Windows では OS の優先 UI 言語が環境由来 UI 信号の前に加わり、地域とキーボード情報も OS から取得する。macOS (`Darwin`) では `.GlobalPreferences.plist` の `AppleLanguages` / `AppleLocale` が環境信号より前に加わる。したがってこれらの OS 信号がある場合、`LANGUAGE` より先に候補を決めることがある。Linux などではこの関数が受け取った環境値を使う（`terminal/strata_control/drafting.py:1339-1352`）。

## 実行時の詳細

`computer_language_signals()` は引数なしで `os_language_signals()` を呼び、その時点の `os.environ` を参照する。`LANGUAGE` を含む環境値は関数内にキャッシュされない。DFlash2 起動の形を整えるたび `auto_vocab` が呼ばれ、そこで環境信号を取得する。起動前に環境値が変われば次の呼び出しに反映されるが、すでに構成された起動引数には反映されない（`terminal/strata_control/drafting.py:1323-1357, 1425-1438, 1764-1771`）。

選択結果は設定ファイルへ保存されず、その起動の `cfg["args"]` に組み立てた engine 引数としてのみ渡される。ファイル形式が `FORM_DIR` の場合は `--mtp <vocabulary の親ディレクトリ>`、それ以外でファイルがある場合は `--mtp-draft-vocab <ファイル>` を使う（`terminal/strata_control/drafting.py:1019-1025, 1764-1781`）。この処理はサーバーの起動構成時にも使われる（`terminal/serve/server.py:3560-3564`）。

## ログと測定値

サーバーが起動内容を告知する経路では、選択理由の行が stdout に `[strata] drafting: ...` として出る。自動選択時は、たとえば `drafting: draft vocabulary: <ファイル名> (by this computer's language: <言語>)`、既定へ戻ったときは `drafting: draft vocabulary: <ファイル名> (the default)` となる。明示選択時は `(set by you)` が付く。告知しない経路では出ず、LANGUAGE 自体の値を不正として警告する処理や、この選択による終了・失敗経路はない（`terminal/strata_control/drafting.py:1431-1445`; `terminal/serve/server.py:3565-3578`）。

## 根拠

- 環境・OS 信号の取得: `terminal/strata_control/drafting.py:1316-1357, 1360-1406`
- 言語タグの分類と候補の優先: `terminal/strata_control/drafting.py:1255-1313`
- 手動指定の優先、既定への fallback、ログ文言: `terminal/strata_control/drafting.py:1409-1445`
- DFlash2 引数の組み立てと起動ログ: `terminal/strata_control/drafting.py:1019-1025, 1746-1781`; `terminal/serve/server.py:3560-3578`
