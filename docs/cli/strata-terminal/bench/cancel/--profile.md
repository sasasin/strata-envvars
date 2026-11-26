# `strata bench cancel --profile`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench cancel` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み serving profile の ID（小文字英字で始まり、小文字英数字・`_`・`-` を続ける最大 64 文字） |

## 役割

キャンセル対象のベンチマークを profile ID と実行ディレクトリの組で照合します。profile を読み込んだあと、指定 profile の lease が指定ディレクトリを指し、その実行が進行中の場合に限り `cancel.request` を作成します。単に profile を指定するだけで他の実行中ベンチマークや server を停止するものではありません（`terminal/strata_cli/cli.py:363-366, 1239-1246`、`terminal/strata_control/benchmarking.py:105-147`）。

## 使い方

```sh
# work profile で実行中のベンチマークにキャンセルを要求する
strata bench cancel --profile work --path /absolute/path/to/run-directory

# 同じ要求を JSON で受け取る
strata bench cancel --profile work --path /absolute/path/to/run-directory --output json
```

`--path` は必須で、CLI は絶対パスでなければ終了コード 2 で拒否します。parser の説明は run directory または `results.json` を指定する形ですが、処理本体は `progress.json` も親ディレクトリへ解決します（`terminal/strata_cli/cli.py:363-366, 1241-1244`、`terminal/strata_control/benchmarking.py:138-145`）。

## 値と既定値

- `--profile` は値を取る必須オプションです。別名はありません。parser 自体には値の変換・選択肢指定はなく、実行時に profile ローダーが検証します（`terminal/strata_cli/cli.py:363-366, 1243-1244`）。
- ID は `[a-z][a-z0-9_-]{0,63}` に一致する必要があります。profile は設定ディレクトリ内の `<ID>.json` として読み込まれ、保存済みでない ID はエラーになります。内容も schema version、ID、絶対パスの `source_config`、override を含む profile として検証されます（`terminal/strata_control/profiles.py:25-26, 48-55, 120-132, 153-173`）。
- `--profile` に既定値はありません。省略すると argparse の必須引数エラーになります。`--output` の既定値は `human`、指定できる値は `human` と `json` です（`terminal/strata_cli/cli.py:363-366`）。

## 実行時の動作

CLI はまず `--path` が絶対パスかを確認し、その後 `profiles.load()` で指定 profile を読みます。`request_cancel()` は `results.json` / `progress.json` が指定された場合はその親を実行ディレクトリとし、それ以外は値自体をディレクトリとして扱います。ディレクトリが owner-only であることを確認したうえで、profile の lease に記録されたパス digest がそのディレクトリと一致し、progress の state が `running` の場合だけキャンセル要求を受理します（`terminal/strata_cli/cli.py:1239-1245`、`terminal/strata_control/benchmarking.py:78-79, 105-135, 138-149`）。

受理時には実行ディレクトリに `cancel.request` を排他的に新規作成し、`1` を書いて同期します。すでに存在する場合は通常ファイル・単一 hard link・1 byte で owner-only であることを検証します。実行中のベンチマークはこのファイルを約 0.1 秒間隔で監視し、検出すると自身が保持する HTTP stream socket を shutdown し、後続処理をキャンセル扱いにします。そのため CLI の成功は要求の受理を示し、最終結果の確認は保存されたレポートで行います（`terminal/strata_control/benchmarking.py:149-168`、`terminal/strata_cli/bench.py:57-82, 812-825, 843-887`）。

## 適用条件と副作用

- 保存済み profile が必要です。profile 名が不正、profile が未保存、または profile 内容が不正な場合は実行されません。profile 読込時に PermissionError が起きると、Strata はアクセス権を一度修復して再読込する経路を持ちます（`terminal/strata_control/profiles.py:48-55, 153-173`、`terminal/strata_control/private_files.py:479-487`）。
- 指定ディレクトリが owner-only でない場合は拒否されます。POSIX では現在ユーザー所有で mode bits だけが広すぎるファイル・ディレクトリは検査時に `0600` / `0700` へ戻されることがあります。他ユーザー所有など修復できない状態は拒否されます（`terminal/strata_control/benchmarking.py:141-144`、`terminal/strata_control/posix_owner.py:26-54`）。
- 対象の lease がない、別 profile / 別 run の lease である、run がすでに終了している、または progress が `running` でない場合はキャンセルしません（`terminal/strata_control/benchmarking.py:105-135, 145-148`）。
- 主な副作用は `cancel.request` の作成と、ベンチマークプロセス側が現在の request stream を閉じて run をキャンセル終了させることです。server 自体の停止や GPU の直接操作はこの処理にありません（`terminal/strata_control/benchmarking.py:149-163`、`terminal/strata_cli/bench.py:57-82, 843-887`）。

## 出力とエラー

- 成功時の human 出力は `Cancellation requested; check the saved report for the final outcome.`、終了コードは 0 です。JSON 出力では `ok: true`、`path`（`results.json` の絶対パス）、state（`cancel_requested` またはすでに反映済みの場合の `cancelled`）を返します（`terminal/strata_cli/cli.py:566-573, 1244-1246`、`terminal/strata_control/benchmarking.py:164-168`）。
- 相対 `--path` は終了コード 2 です。profile の形式不正は通常 2、未保存 profile や不正な保存内容、owner-only 検証・progress 読込の失敗は 5、対象 run が active でない・すでに最終レポート保存済みの場合は 6 です（`terminal/strata_cli/cli.py:1241-1244, 2248-2265`、`terminal/strata_control/profiles.py:30-35, 48-50, 153-172`、`terminal/strata_control/benchmarking.py:138-168`）。
- human mode のエラーは `strata: <message>` を stderr に出し、JSON mode は `ok: false` と code/message を含む JSON を stdout に出します（`terminal/strata_cli/cli.py:558-563, 2248-2265`）。

## 根拠

- `terminal/strata_cli/cli.py:363-366` — `bench cancel` parser、必須 `--profile` / `--path`、`--output` の値と既定値。
- `terminal/strata_cli/cli.py:1239-1246` — 相対 path の拒否、profile 読込、キャンセル処理呼び出し、成功出力。
- `terminal/strata_control/profiles.py:25-55, 120-132, 153-173` — profile ID の形式、保存先、保存済み profile の読込と検証。
- `terminal/strata_control/benchmarking.py:78-79, 105-168` — lease と run path の照合、active / running 検査、キャンセル marker 作成、返却 state。
- `terminal/strata_cli/bench.py:57-82, 695-741, 812-887` — marker の監視、progress state、stream socket の停止、最終 report / progress の保存。
- `terminal/strata_control/posix_owner.py:26-54` — POSIX owner-only 検査と mode 修復。
- `terminal/strata_cli/cli.py:558-573, 2248-2265` — human / JSON 成功・失敗出力と例外時の終了コード処理。
