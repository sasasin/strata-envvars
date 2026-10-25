# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops runs` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済みプロファイル名（必須） |

## 役割

履歴を表示する対象の保存済みプロファイルを選びます。履歴はプロファイルごとに保存され、別のプロファイルの実行記録は列挙されません。

## 使い方

```sh
strata ops runs --profile four-gpu
```

JSON で取得する場合:

```sh
strata ops runs --profile four-gpu --output json
```

## 値と既定値

- 値は必須で、省略すると `argparse` が usage と引数エラーを表示して終了コード 2 で終了します。値を取らないフラグです。
- プロファイル名は小文字英字で始まり、小文字英字・数字・`_`・`-` のみを使えます。保存済みのプロファイルが必要です。パスや run-config JSON の指定ではありません。
- `--profile` 自体に既定値はありません。`strata ops` の各サブコマンド parser に共通して必須指定として追加されていますが、この文書の対象スコープは `strata ops runs` です。

## 実行時の動作

CLI は `--profile` を `journal.list_runs(profile, limit=...)` に渡します。処理はプロファイルの保存先にある `.ops/<profile>/.runs/` を参照し、ID が32桁の小文字16進数である JSON 記録を更新日時の新しい順に読みます。ディレクトリがまだなければ空の一覧になります。

既定の表示件数は `--limit 20` です。`--limit` は整数で、1〜100 の範囲に限られます。0 以下または101以上は `ProfileError` となり、既定の human 出力では stderr に `strata: operation list limit must be 1..100` を出して終了コード 2 になります。これは `--profile` の値自体の制約ではなく、この一覧コマンドとの相互作用です。

human 出力では各記録の operation ID と state を1行に表示し、一覧が空なら `No operation runs recorded` と表示します。`--output json` では `profile` と `runs` を含む成功 JSON を出します。各正常な一覧要素には operation ID、recipe（直接操作では null）、origin、kind、state、開始・終了時刻が含まれ、`running` 状態は `completion_unverified: true` として示されます。記録ファイルを読めない、または検証できない場合、その記録は一覧から落とされず operation ID と error を持つ要素になります。

## 適用条件と副作用

- 指定名の保存済みプロファイルがない場合は一覧を取得できず、エラー `profile '<name>' is not saved; use strata profile create` と終了コード 5 になります。
- 一覧処理は run 記録の作成・編集・削除を行いません。`.runs` が存在する場合はシンボリックリンクや所有者限定アクセス権を検査し、不適切なディレクトリは拒否します。
- 履歴ディレクトリを解決する前にプロファイル本体を読み込みます。プロファイルファイルへのアクセス拒否時、実装はアクセス権修復を一度試してから再読込するため、条件によってはこのファイルのアクセス権が修復される副作用があります。
- Windows で CLI を管理者権限で起動した場合、CLI の共通初期化が後続作成ファイル用にプロセスの既定 owner/DACL をユーザーへ合わせようとします。この一覧処理自体は履歴ファイルを作成しません。

## 出力とエラー

- 名前の形式が不正な場合は終了コード 2、プロファイルが未保存の場合や `.runs` の型・アクセス権が不適切な場合は通常終了コード 5 でエラーになります。human 出力ではエラーメッセージを stderr に出します。
- `--limit` の整数変換失敗や範囲外は終了コード 2 です。整数変換失敗は parser の usage エラー、範囲外は `strata:` 付きのエラーとして扱われます。
- `--output json` の場合、コマンド処理エラーは `ok: false` と error code/message を持つ JSON になります。成功時は `ok: true`、`profile`、`runs` を含みます。

## 根拠

- parser と必須指定・型・既定値: `strata_cli/cli.py:255-270`。
- `strata ops runs` から journal への値の転送、human/JSON 表示: `strata_cli/cli.py:1391-1408`。
- プロファイル名の検証・保存先解決・プロファイル読込時のアクセス権修復: `strata_control/recipes.py:38-59`、`strata_control/profiles.py:48-55`、`strata_control/profiles.py:150-166`、`strata_control/private_files.py:476-484`。
- 一覧上限、対象ディレクトリ、降順、欠損ディレクトリ、各記録の検証とエラー要素化: `strata_control/journal.py:47-57`、`strata_control/journal.py:185-244`、`strata_control/journal.py:254-273`。
- 共通エラー・成功出力と `ProfileError` の終了コード処理: `strata_cli/cli.py:527-542`、`strata_cli/cli.py:2119-2173`、`strata_control/profiles.py:30-35`。
- CLI 起動時の Windows 向け既定アクセス権調整: `strata_cli/cli.py:2217-2223`、`strata_control/private_files.py:349-375`。

この調査ではソースコードを確認し、CLI の `--help` は実行していません。Release 配布物や他 OS 上での実動作は確認していません。
