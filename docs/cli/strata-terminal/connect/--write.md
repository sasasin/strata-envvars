# `--write`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--write` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`）。未指定時は `False` |

## 役割

選んだ対応アプリ用の設定ファイルを、表示だけでなく実際に作成・更新します。ファイルを書き換える前に確認し、既存ファイルはバックアップします。引数にはアプリ名が必要です。例として、OpenCode の設定を確認してから書き込むには次のようにします。

```sh
strata connect opencode --write
```

自動実行など確認入力を出せない環境では、明示的に `--yes` を加える必要があります。

```sh
strata connect opencode --write --yes
```

## 値と既定値

`--write` は真偽値です。指定しなければ設定ファイルの内容を表示するだけで、書き込みません。`--yes` は別の真偽値オプションであり、`--write` による確認を抑止します。`--yes` 単独では書き込みを有効にしません。

## 実行時の動作

CLI は `--write` を `store_true` として登録し、`run_connect` が引数を処理します。アプリの設定を生成し、書込み対象のファイル一覧が空でなければ、`--yes` がない場合は端末で確認します。応答が `y` または `yes` のときだけ各ファイルを書き込みます。それ以外の応答や入力終端では何も書かず、正常終了します。`--yes` があれば確認を飛ばして書き込みます（`strata_cli/launch/cmd.py:161-163,930-947`）。

書込み先はアプリごとに定義され、たとえば OpenCode は `~/.config/opencode/opencode.json`、Codex は `~/.codex/config.toml`、Claude Code は `~/.claude/settings.json` です。OpenCode、Claude Code、pi、OpenClaw の JSON 設定は既存 JSON との再帰 merge 対象です。同じキーは新しい設定値で置き換えられ、他の既存キーは維持されます。merge 対象外のファイルは生成内容で置き換えます（`strata_cli/launch/harness.py:209-235,263-267,275-307`）。

既存の対象ファイルは、書込み前に同じディレクトリ内の `<ファイル名>.strata-bak-<YYYYMMDD-HHMMSS>` へコピーします。書込み後は UTF-8 で末尾改行を付け、可能なら権限を `0600` にします。生成設定には API key が含まれ得るための処理です。既存の JSON が不正で merge に失敗したときは、バックアップ後に merge せず生成内容で置き換えます（`strata_cli/launch/harness.py:275-298`）。

## 適用条件と副作用

- アプリ名を省略すると対応アプリ一覧を表示して終了するため、`--write` を付けても個別のファイル書込みには進みません（`strata_cli/launch/cmd.py:845-856`）。
- `deepseek-harness` は Strata アプリ内蔵 harness で、書き込むファイルがありません。この場合は `Nothing to write for this app.` と表示して終了します（`strata_cli/launch/harness.py:233-235`, `strata_cli/launch/cmd.py:930-933`）。
- `--output json` では、`--check` がない場合は JSON を出力してその場で終了します。`--check` を付けた場合もチェック結果を JSON 出力して終了します。どちらも後続の `--write` 処理へ進まないため、JSON 出力とファイル書込みは併用できません（`strata_cli/launch/cmd.py:872-896`）。
- `--check --write` を人間向け出力で使う場合、先にサーバーへの prompt と tool call を確認します。いずれかが失敗すれば終了コード `1` で戻り、書込みは行いません（`strata_cli/launch/cmd.py:921-929`）。
- `--show-key` は表示内容のマスクを制御しますが、書込み先に生成する設定値から key を除くものではありません。書込み先ファイルには接続設定と key が保存されます（`strata_cli/launch/cmd.py:865-875,897-910`, `strata_cli/launch/harness.py:80-104,275-298`）。

## 出力とエラー

書込み前の確認文は `Write these files now? ... [y/N]` です。拒否または入力終端では `Nothing was written.` を表示し、終了コード `0` です。`--yes` なしで標準入力が端末でないときは標準エラーに `--write asks first; run it in a terminal or add --yes.` を出し、終了コード `2` で失敗します。成功時はファイルごとに `Created`、`Replaced`、`Merged` とパスを表示し、バックアップがあればその場所も表示します（`strata_cli/launch/cmd.py:934-947`, `strata_cli/launch/harness.py:297-298`）。

ファイル操作の `OSError` は CLI 共通処理でエラーとして処理され、通常は終了コード `6` になります（`strata_cli/cli.py:2176-2183`）。複数ファイルの途中で失敗した場合に、それ以前に書いたファイルを巻き戻す処理は確認できません。

## 根拠

- `strata_cli/launch/cmd.py:148-165` — `connect` コマンドの説明、`--write` と `--yes` の parser 定義。
- `strata_cli/launch/cmd.py:842-947` — アプリ解決、表示、JSON の早期終了、`--check`、確認と書込みの分岐。
- `strata_cli/launch/harness.py:209-235` — 対応アプリごとのファイル、merge 指定、ファイルなし harness。
- `strata_cli/launch/harness.py:263-307` — 設定内容生成、既存ファイルのバックアップ、JSON merge、書込みと権限設定。
- `strata_cli/cli.py:2153-2155,2176-2183` — `strata connect` の dispatch とファイル I/O エラー処理。

調査は上記 commit のソースに限定しました。対応アプリ側の現行仕様や個別 platform での設定読込み結果は実行確認していません。
