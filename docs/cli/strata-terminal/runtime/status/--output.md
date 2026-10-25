# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime status` |
| オプション | `--output` |
| 別名 | なし。`--json` は同じ形式を選ぶ別オプション |
| 値 | `human` または `json` |

## 役割

プロファイルで管理されているローカル Strata runtime の状態を、人向け表示または JSON で出力します。状態の取得先や判定方法は変えず、表示形式だけを選びます。

## 使い方

```sh
strata runtime status --profile my-profile --output json
```

`--profile` は必須です。`--output` を省略すると `human` になります。`--json` も `--output json` と同じ形式を選びます（`strata_cli/cli.py:213-215, 508-515, 2232-2235`）。

## 値と既定値

- `human`: `--output` の既定値です。プロファイル名、状態、あれば instance ID、API URL、検証表示、エラーを1行で出します。
- `json`: `schema_version: 1` と status の結果オブジェクトを1つの JSON として stdout に出します（`strata_cli/cli.py:1331-1333, 1359-1369`）。
- `argparse` の `choices` により、受理値は上記2つです。別の値は parser が拒否します（`strata_cli/cli.py:215`）。

## 実行時の動作

parser は `runtime status` 専用に `--output {human,json}` を登録し、既定値を `human` にします（`strata_cli/cli.py:213-215`）。`--json` と `--quiet` は one-shot parser 群へ共通追加され、`main()` は `--json` が指定されると `a.output` を `json` にします（`strata_cli/cli.py:508-515, 2232-2235`）。

表示形式を決めた後、CLI は `management.runtime_action("status", profile, ...)` を呼びます。status action は `runtime.status(profile)` の結果をそのまま返します（`strata_cli/cli.py:1345-1356`; `strata_control/management.py:231-234`）。このオプションは status 操作の引数や結果データを変更しません。

status の実装は runtime state ファイルを読み、ファイルがなければ `stopped` を返します。state があり owner host の lease が有効なら owner へ status RPC を送り、lease がなければ `stale` を返します（`strata_control/runtime.py:444-455`）。owner 側では、server が起動中なら ready file と API を確認します。初回の status 取得時に非同期 readiness probe を開始することがあり、モデルが loaded なら1 token の生成要求も送るため、コマンドは単なるファイル読み取りではありません。`--output` の値自体はこの処理を変えません（`strata_control/runtime.py:933-976`; `strata_control/readiness.py:84-86, 101-125`）。

## 適用条件と副作用

`--output` は起動時に解析され、実行中に切り替わりません。status コマンドは runtime の開始・停止を要求せず、status 結果を表示します。ただし上記の readiness probe はローカル runtime API への GET に加え、loaded model では短い生成要求を送ります（`strata_control/runtime.py:444-455, 948-969`; `strata_control/readiness.py:101-125`）。

`--quiet` を併用した場合、`human` 出力は成功時に抑制され、失敗時には捕捉された表示が stderr に出ます。`json` 出力は quiet 処理の対象外です（`strata_cli/cli.py:2236-2248`）。

## 出力とエラー

- `human` は `<profile>: <state>` を出し、結果に含まれる instance ID、API URL、launch 検証、readiness 情報、error を続けて表示します（`strata_cli/cli.py:1362-1369`）。
- `json` は `{"schema_version": 1, ...status結果}` を stdout に出します。status 結果が `ok: false` なら、その結果を出したうえで結果の `exit_code`（なければ `6`）を終了コードにします（`strata_cli/cli.py:1359-1360, 1373`）。
- 管理対象がない場合は `stopped` として成功します。owner host を失った state は `stale` / `owner_host_lost` と終了コード `6` になります（`strata_control/runtime.py:444-455`）。state ファイルの不正・読み取り不能は `ProfileError`、owner 通信の不通は終了コード `3`、応答タイムアウトは `8`、不正な応答は `6` です（`strata_control/runtime.py:215-235, 402-440`）。CLI が例外を受けた場合、JSON 選択時は標準化した JSON error、human 時は `strata: ...` を stderr に出します（`strata_cli/cli.py:527-532, 2166-2188`）。
- `--output` に `human` / `json` 以外を渡すと argparse の usage/error 経路になり、終了コード `2` です（parser 定義: `strata_cli/cli.py:215`）。

## 根拠

- parser と共通 option: `strata_cli/cli.py:197-215, 508-515`
- `--json` の変換と quiet 処理: `strata_cli/cli.py:2232-2248`
- runtime status の呼び出し・表示・終了コード: `strata_cli/cli.py:1331-1373`
- status action の委譲: `strata_control/management.py:231-234`
- state、lease、RPC の判定: `strata_control/runtime.py:215-235, 402-455`
- owner 側 status 判定と readiness probe の開始: `strata_control/runtime.py:933-976`
- readiness probe の API 要求: `strata_control/readiness.py:84-142`

調査範囲は指定 revision の Terminal CLI と同 checkout の `strata_control` 実装です。配布 Release のバイナリや他 OS 上での実行結果は確認していません。
