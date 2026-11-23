# `DRAFTING`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この環境変数は Strata の通常プロセス全般が読む設定ではなく、Docker の標準起動経路で drafter 選択を `strata launch --drafting` に渡す入力である。`tools/docker/entrypoint.sh` は非空値だけを CLI 引数として追加する。Docker 以外の経路や、Docker イメージに `strata ...` / 別コマンドを指定した経路では、この変数を処理せずコマンドを直接実行する（`tools/docker/entrypoint.sh:68-71,245`）。

CLI は `auto`、`mtp`、`dflash2`、`off` を受け付ける。`auto` はモデル・backend・利用可能な drafter に基づく選択、`mtp` / `dflash2` は選択を指定し、`off` は drafter を無効にする。したがって、この変数自体がモデルや engine に渡るわけではなく、Docker entrypoint が CLI に転送した後、Terminal の設定と起動処理が選択を行う（`terminal/strata_cli/launch/cmd.py:101-104,256-257`; `terminal/strata_cli/launch/runner.py:1995-2004`; `terminal/strata_control/drafting.py:1-9`）。

## 値と判定

entrypoint は shell の `[ -n "${DRAFTING:-}" ]` で設定値の有無を見て、空でなければ元の文字列を `--drafting` の値にする。値の小文字化・前後空白除去・許容値検査は後段の CLI `_choice` が行う。`_choice` は `strip().lower()` 後の文字列全体を列挙値と照合するため、大文字小文字と前後空白は無視されるが、部分一致や数値変換はしない（`tools/docker/entrypoint.sh:245`; `terminal/strata_cli/launch/cmd.py:35-43`; `terminal/strata_cli/launch/settings.py:31-32`）。

| Docker standard launch input | entrypoint behavior | CLI interpretation |
| --- | --- | --- |
| 未設定 | 引数を追加しない | 保存済み preset があればその値を使う。新規の選択は `None` / Auto 相当 |
| 空文字 `""` | 引数を追加しない | 上と同じ。設定ありの空文字とは扱わない |
| `auto`, `mtp`, `dflash2`, `off` | `--drafting <value>` を追加 | 有効。大文字小文字を問わず、前後空白を除いて一致 |
| ` AUTO ` など有効語の大小文字・前後空白違い | 生の値を引数に渡す | trim・小文字化後に有効 |
| `0`, `1`, `true`, `false`, `0anything`, 空白だけ、その他の文字列 | 非空なら引数を追加 | 無効。文字全体が選択肢に一致しない |

CLI の無効値エラーは `'<元の値>' is not a drafting setting. [Did you mean ...] Choose one of: auto, mtp, dflash2, off.` の形式（近い候補がある場合は候補文を含む）。このエラーで launch は失敗し、Docker entrypoint は launch の非 0 終了を `strata launch stopped with code <rc> (the lines above say why). ...` として報告して終了する（`terminal/strata_cli/launch/cmd.py:35-43`; `tools/docker/entrypoint.sh:310-312`）。

## 有効になる条件

- `tools/docker/entrypoint.sh` の通常起動（引数なし、または先頭引数が `run` / `serve`）であること。別コマンド指定時は先行分岐で `exec` され、環境変数は CLI に転送されない（`tools/docker/entrypoint.sh:68-71`）。
- entrypoint から `strata launch` に転送されること。`--drafting` が与えられると `s.drafting` に入り、保存済み run config の drafting 値より今回の指定が優先する。引数がなければ既存 preset/config の選択を保持し、新規時は Auto の既定経路を使う（`terminal/strata_cli/launch/cmd.py:256-257`; `terminal/strata_cli/launch/runner.py:695-697,1995-2004`; `terminal/strata_cli/launch/settings.py:118`）。
- `auto` の実際の drafter は model family/name、backend、GPU/モデル状態などを見て決まる。たとえば `mtp=false` の設定では Auto を off にし、split engine が適用される場合は MTP に切り替える。選択した drafterが実行不能・未準備の場合の fallback と理由表示は drafting 判定処理が扱う（`terminal/strata_cli/launch/runner.py:1995-2004`; `terminal/strata_control/drafting.py:1548-1575,1830`）。
- Auto と `dflash2` は同一ではない。CLI の説明では Auto は DFlash2 対応モデル・engine の場合に DFlash2、それ以外は MTP。複数 request 時の Auto は MTP を選ぶ。`dflash2` 指定でも対象外など実行不可なら MTP 単独へ fallback し、起動時に理由を表示する（`terminal/strata_cli/launch/cmd.py:101-104`）。

## 実行時の詳細

値は Docker entrypoint 起動時に shell が一度展開し、`strata launch` の引数列へ渡す。entrypoint が値を cache したり、サーバーへ環境変数として転送したりはしない（`tools/docker/entrypoint.sh:245,295-304`）。CLI parser は起動引数の解析時に値を検証し、起動設定へ反映する。`s.drafting` が設定されていれば生成する設定の `drafting` に保存済み値を上書きする（`terminal/strata_cli/launch/cmd.py:256-257`; `terminal/strata_cli/launch/runner.py:695-697`）。

Docker 起動では `have=1` となり、preset が既にある場合は `--preset <name> --save-preset <name>` を付ける。新規の場合も選択値とともに preset を保存する。このため非空の `DRAFTING` はその起動だけでなく Docker の preset に記録され、次回 `DRAFTING` が unset/empty でも保存設定が使われ得る。明示的な非空値がなければ既存 preset の設定を保持する（`tools/docker/entrypoint.sh:245,264-268`; `terminal/strata_cli/launch/runner.py:695-697`）。

## 根拠

- `tools/docker/entrypoint.sh:18` — Docker entrypoint の設定名と値の説明。
- `tools/docker/entrypoint.sh:68-71` — 独自コマンド経路は通常 launch を迂回。
- `tools/docker/entrypoint.sh:245,264-268,295-312` — 非空判定、CLI 転送、preset 保存、失敗時の終了報告。
- `terminal/strata_cli/launch/cmd.py:35-43,101-104,256-257` — 値の正規化・検証、CLI の選択肢・説明、設定反映。
- `terminal/strata_cli/launch/settings.py:31-32,118` — 選択肢と Auto の内部既定値。
- `terminal/strata_cli/launch/runner.py:695-697,1995-2004` — 明示値と保存値の優先順位、モデル状態・split engine に応じた決定入力。
- `terminal/strata_control/drafting.py:1-9,1548-1575,1830` — drafter 選択と fallback の実装。
