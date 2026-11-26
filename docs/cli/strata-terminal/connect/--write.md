# `strata connect --write`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--write` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は無効 |

## 役割

選択したクライアントアプリ向けに Strata 接続設定を生成し、アプリの設定ファイルへ書き込みます。対象アプリ名を省略すると対応アプリ一覧を表示するだけで、`--write` の書き込み処理には入りません。アプリごとの設定ファイル、JSON の既存設定との統合可否、出力先は harness 定義で決まります。

## 使い方

```sh
# 書き込まず、OpenCode 設定の作成・バックアップ内容を確認する
strata connect opencode --write --dry-run

# 確認プロンプトを省略して設定を書き込む
strata connect opencode --write --yes
```

## 値と既定値

`--write` は `argparse` の `store_true` フラグで、値や別名はありません。指定しなければ無効です。`--write` なしでは、選択アプリ向け設定を表示する動作になります。`--yes` は確認を省略し、`--dry-run` はファイル変更をせず予定アクションを返します。なお、実装は `--dry-run` 単独でも書き込み処理のプレビューを呼び出します（parser の説明文は `--write` との併用を案内しています）。`--if-unchanged` は書き込み処理が呼ばれた場合にのみ使われ、最終的な書き込み内容と既存ファイルが一致すれば内容の書き込みとバックアップを省きます。通常実行では mode `0600` の設定を試みます。

## 実行時の動作

1. `strata connect <app>` がアプリ用設定をレンダリングします。URL・API key・model は明示値、実行中 launch 情報、既定値などから組み立てられます。
2. `--check` も指定されていれば、書き込みより先にサーバーを検査します。検査失敗時は終了コード 1 で戻り、書き込みません。
3. `--write` または `--dry-run` が指定されると、レンダリングした各ファイルを順番に処理します。ファイルがないアプリは何も書かず、`Nothing to write for this app.` と報告します。
4. `--dry-run` でなければ、`--yes` がない場合に確認します。標準入力が TTY でなければ書き込みを拒否して終了コード 2 になります。TTY では `y` / `yes` 以外の入力はキャンセル扱いで、ファイル変更なし・終了コード 0 です。`--yes` はこの確認を省略します。
5. 既存ファイルは `<ファイル名>.strata-bak-<時刻>` にコピーしてから書き込みます。JSON の merge 対象では既存キーを保持し、同じキーは新しい設定を優先します。既存 JSON が不正なら merge を行わず置換します。書き込みファイルには可能な範囲で mode `0600` を設定します。

たとえば OpenCode は `~/.config/opencode/opencode.json` を JSON merge 対象として登録しています。別アプリでは複数ファイルへの書き込みや merge なしの置換となる場合があります。

## 適用条件と副作用

- `--write` はアプリ名が指定され、対象アプリが見つかり、レンダリング結果にファイルがある場合にファイルへ作用します。未知のアプリ名は候補一覧付きで stderr に出力され、終了コード 2 です。
- 確認なしで書き込むには `--yes` が必要です。非 TTY から `--write` を実行する場合も `--yes` を指定する必要があります。`--dry-run` は確認を行わず、ファイルシステムを変更しません。
- `--output json` でも `--write` の処理は実行されます。確認プロンプトは stderr に出し、結果は JSON に含めます。
- 複数ファイルの場合は順番に処理され、途中のファイルで書き込みエラーになると後続ファイルは書かれません。それ以前に完了したファイルは元に戻されません。
- `--check` が失敗すれば `--write` を併用していても書き込みません。

## 出力とエラー

人間向け出力では作成・統合・置換・プレビューしたパスと、作成されたバックアップ先を表示します。JSON 出力では各ファイルの `action`、`path`、`backup` などを `write.written` に含めます。

確認入力が必要なのに標準入力が TTY でない場合は「`--write asks first; run it in a terminal or add --yes.`」を stderr に出し、終了コード 2 です。ファイル操作の `OSError` は対象パスとエラーを報告し、終了コード 1 になります。JSON 出力では失敗ファイルを `failed`、その後の未処理ファイルを `not_written` として示します。ユーザーが確認を拒否した場合は「Nothing was written.」となり、終了コード 0 です。

## 根拠

- `terminal/strata_cli/launch/cmd.py:163-183` — `strata connect` parser と、`--write`、`--dry-run`、`--if-unchanged`、`--yes` の定義。
- `terminal/strata_cli/cli.py:516-517` — launch/connect parser の登録。
- `terminal/strata_cli/cli.py:2235-2237` — `connect` を `run_connect` へ渡す dispatch。
- `terminal/strata_cli/launch/cmd.py:1019-1050` — 確認、TTY 判定、dry-run、順次書き込み、例外処理と終了コード。
- `terminal/strata_cli/launch/cmd.py:1052-1080` — アプリ選択、設定値の決定、レンダリング。
- `terminal/strata_cli/launch/cmd.py:1087-1119` — JSON 出力時の `--check` 先行、失敗時の書き込み抑止、書き込み結果。
- `terminal/strata_cli/launch/cmd.py:1120-1168` — 人間向け表示、`--check` と書き込みの実行順、結果と失敗表示。
- `terminal/strata_cli/launch/harness.py:65-85, 286-311` — harness ごとの出力ファイル、形式、merge 指定。OpenCode の出力先と JSON merge 設定。
- `terminal/strata_cli/launch/harness.py:343-347` — harness の設定ファイルをレンダリングする処理。
- `terminal/strata_cli/launch/harness.py:351-399` — パス展開、JSON merge、未変更判定、バックアップ、dry-run、書き込み、mode 設定。

