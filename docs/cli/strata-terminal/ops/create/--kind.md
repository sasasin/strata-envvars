# `--kind`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops create` |
| オプション | `--kind` |
| 別名 | なし |
| 値 | `runtime.restart`、`engine.calibrate.measure`、`components.verify` のいずれか。必須。 |

## 役割

新しいローカル operator recipe の種類を選びます。recipe は既存の Strata 操作を型付きデータとして記録し、実行可能なコマンド文字列を含みません。`--kind` は作成する recipe の `kind` と、種類別の初期 `params` を決めます。`strata_cli/cli.py:270-272`、`strata_control/recipes.py:1-5,117-127`

## 使い方

```sh
strata ops create nightly-restart --profile work --kind runtime.restart
strata ops create gpu-check --profile work --kind components.verify
```

`NAME` は位置引数で、`--profile PROFILE` も必須です。`--kind` を省略すると argparse が引数不足として拒否します。`strata_cli/cli.py:255-272`

## 値と既定値

| 値 | 作成時の初期 `params` | 後続 recipe 操作での意味 |
| --- | --- | --- |
| `runtime.restart` | `{"startup_wait_s": 300}` | `ops run` が保存済み serving profile の runtime を再起動するときの startup wait 秒数。recipe 検証では整数 `1..600` を要求します。 |
| `engine.calibrate.measure` | `report_dir` を profile ディレクトリの絶対パスにある `.reports` に設定 | `ops run` が排他的な calibration 測定を行い、新しい report を保存します。測定のたびに `--exclusive` が必要です。 |
| `components.verify` | 空の `{}` | `ops run` が component 検証を行います。`live` を後から設定しなければ `false` として扱います。 |

parser に既定値はなく、`required=True` です。したがって表の `params` は `--kind` の省略時 fallback ではなく、選択した kind から recipe を作るときの種類別初期値です。`strata_cli/cli.py:270-272`、`strata_control/recipes.py:103-127,340-355`

## 実行時の動作

parser は上記3値以外を choices 違反として拒否します。処理側でも `recipes.create(profile, name, kind)` を呼び、`_default` が kind を再検証して schema version 1 の recipe (`profile`, `id`, `kind`, `params`) を組み立てます。`strata_cli/cli.py:270-272,1412-1415`、`strata_control/recipes.py:28,93-127,130-132`

`create` は profile を読み込んでから `.ops/<profile>/<name>.json` を作成し、kind と初期 params を保存します。保存後は recipe を再読込して revision を返し、CLI は human 形式で作成名・kind・revision、または JSON 形式で recipe と revision を出力します。このコマンド自体は recipe を保存するだけで、restart、calibration、component 検証を実行しません。実行は別の `strata ops run` です。`strata_control/recipes.py:38-64,130-150`、`strata_cli/cli.py:1412-1415`

出力形式は同じ one-shot parser に追加される `--output {human,json}`（既定 `human`）または alias `--json` で選びます。`--quiet` も共通追加されますが、JSON 出力時には抑制処理に入りません。`strata_cli/cli.py:266-267,508-515,535-542,2232-2247`

## 適用条件と副作用

- `--kind` の対象は `strata ops create` の parser です。他の `ops` subcommand にこの引数は登録されません。`strata_cli/cli.py:255-272`
- profile 名と recipe 名は小文字英字で始まり、小文字英字・数字・`_`・`-` のみを使えます。profile が読み込めない場合は作成前に失敗します。`strata_control/recipes.py:32-35,38-40,130-134`
- 新規作成時に `.ops` と profile 用の recipe ディレクトリが必要に応じて作られます。POSIX では owner-only の `0700` directory と `0600` recipe file を要求・作成します。ファイルは既存ファイルを開かない `O_EXCL` で作り、recipe ごとに profile lock を使って書き込み、flush と `fsync` を行います。既存の同名 recipe は上書きせずエラーです。`strata_control/recipes.py:38-59,130-149`
- calibration kind を選んでも、作成時に engine 起動や report directory 作成は行いません。report directory と report file は `ops run` の calibration 分岐で扱われます。`strata_control/recipes.py:117-127,413-423`

## 出力とエラー

成功時は終了コード `0` です。既定の human 出力は `Created recipe NAME (KIND) at REVISION`、JSON 出力は `schema_version: 1`, `ok: true`, `recipe`, `revision` を含みます。`strata_cli/cli.py:1412-1415,535-542`

未指定値・未対応値は argparse の usage/error 経路で終了コード `2` になります。profile/name の不正、profile 読み込み失敗、同名 recipe の存在など実行時エラーは `_run` の `ValueError`/`OSError` 処理から出力されます。通常は stderr に `strata: ...`、JSON モードでは標準出力に `ok: false` と error を出し、エラー型に応じた終了コードを返します（同名 recipe は `ProfileError` の既定コード `2`）。書き込み途中で例外が起きた場合は、作成しかけた recipe file を削除します。`strata_cli/cli.py:527-532,2166-2183,2223-2231`、`strata_control/profiles.py:30-35`、`strata_control/recipes.py:130-149`

## 根拠

- Strata `strata_cli/cli.py:255-272` — `ops create` parser、必須 `--profile` と `--kind` の choices。
- Strata `strata_cli/cli.py:508-515,1391-1415` — 共通の `--output`/`--json`/`--quiet`、create の呼び出しと成功出力。
- Strata `strata_cli/cli.py:527-542,2166-2183,2223-2231` — human/JSON error、例外処理、parser error の終了経路。
- Strata `strata_control/recipes.py:28,32-64,93-150` — kind 集合、profile/name 検証、recipe schema/初期値、ファイル作成と失敗時 cleanup。
- Strata `strata_control/recipes.py:329-360,363-428` — kind ごとの plan/run 時の意味、副作用、および calibration の実行条件。
