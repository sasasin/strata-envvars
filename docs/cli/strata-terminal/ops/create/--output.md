# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops create` |
| オプション | `--output` |
| 別名 | `--json`（JSON 出力を指定） |
| 値 | `human` または `json`。省略時は `human`。 |

## 役割

作成する operation recipe の結果を標準出力へ人向けテキストまたは JSON で表示します。ファイルの出力先を指定するオプションではありません。parser は `--output` の値を `human` / `json` に限定し、既定値を `human` にしています（`strata_cli/cli.py:255-267`）。

## 使い方

```sh
strata ops create nightly-check --profile workstation --kind components.verify --output json
```

`workstation` は保存済み profile 名の例です。profile と recipe 名は小文字英字で始まり、小文字英字・数字・`_`・`-` のみを使えます（`strata_control/profiles.py:25`、`strata_control/recipes.py:32-35`）。`--profile` と `--kind` は必須で、recipe 名は位置引数です（`strata_cli/cli.py:263-272`）。

## 値と既定値

- `human`: 既定値。成功時は `Created recipe <name> (<kind>) at <revision>` を標準出力に表示します（`strata_control/recipes.py:1412-1415`）。
- `json`: 成功時は `schema_version: 1`、`ok: true`、recipe、revision を含む JSON オブジェクトを1行で標準出力に表示します（`strata_cli/cli.py:535-542`）。
- `--json` は one-shot コマンド群に追加される alias です。指定すると `--output` を `json` に設定します（`strata_cli/cli.py:508-515, 2232-2235`）。
- それ以外の値は argparse の `choices` により拒否されます。省略時の形式は `human` です（`strata_cli/cli.py:266-267`）。

## 実行時の動作

`--output` は結果の表示形式だけを切り替え、recipe の内容・作成先・作成可否は変えません。作成処理は必須の profile、name、kind を `recipes.create()` に渡します（`strata_cli/cli.py:1412-1415`）。

同じコマンドで `--quiet` を指定すると human 成功メッセージは抑制されますが、`--output json` または `--json` の機械可読出力は抑制されません（`strata_cli/cli.py:2236-2248`）。

recipe は profile ディレクトリ内の `.ops/<profile>/<name>.json` に新規作成されます。既定パラメーターは kind ごとに異なり、`runtime.restart` は `startup_wait_s: 300`、`engine.calibrate.measure` は profile ディレクトリ配下の `.reports` を `report_dir` にし、`components.verify` は空の params です（`strata_control/recipes.py:117-127`）。kind は `runtime.restart`、`engine.calibrate.measure`、`components.verify` のいずれかが必須です（`strata_cli/cli.py:270-272`、`strata_control/recipes.py:28, 117-119`）。

作成時は profile の保存内容を読み、profile 名と recipe 名を検証します。recipe 用ディレクトリを作成し、profile ごとのロックを取得したうえで排他的に新規ファイルを開きます。POSIX ではファイル mode `0600` を指定し、利用可能な場合は `O_NOFOLLOW` も指定します。書き込み後に flush と fsync を行い、書き込み中に例外が起きた場合は不完全な recipe ファイルを削除します（`strata_control/recipes.py:32-64, 130-150`）。既存ファイルは上書きされません。

## 適用条件と副作用

保存済みで読み込み可能な profile が必要です。profile がない場合は `strata_control/profiles.py:150-166` の読込処理でエラーになります。`--output` を指定しても、recipe JSON の保存自体は常に実行されます。出力先ディレクトリの作成と recipe ファイルの新規作成は `recipes.create()` の副作用です（`strata_control/recipes.py:38-59, 130-150`）。

## 出力とエラー

成功時は前述の human テキストまたは JSON を stdout に出し、終了コード `0` を返します（`strata_cli/cli.py:535-542`）。`json` 指定時、通常の `ValueError` 系エラーは `{schema_version: 1, ok: false, error: {code, message}}` 形式の JSON を stdout に出し、エラーに設定された終了コードを返します。human 出力時は `strata: <message>` を stderr に出します（`strata_cli/cli.py:527-532, 2166-2173`）。

recipe 名または profile 名の形式不正、未対応 kind、profile の欠落、recipe の重複は失敗します。重複時は既存 recipe を保持し、`recipe '<name>' already exists` をエラーにします（`strata_control/recipes.py:32-35, 117-120, 130-141`）。`--output` の値の不正、必須引数の欠落、`--kind` の不正値は argparse の usage error となります（`strata_cli/cli.py:263-272`）。

## 根拠

- parser と既定値・choice・必須引数: `strata_cli/cli.py:255-272`
- JSON alias と quiet の適用: `strata_cli/cli.py:508-515, 2232-2248`
- create の dispatch と結果表示: `strata_cli/cli.py:535-542, 1391-1415`
- エラー表示と終了コード: `strata_cli/cli.py:527-532, 2166-2183`
- recipe の kind・既定値・validation・ファイル作成: `strata_control/recipes.py:28-35, 93-150`
- profile の保存場所と読込条件: `strata_control/profiles.py:25, 38-55, 150-166`
