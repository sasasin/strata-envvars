# `--plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--plan` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は `False` |

## 役割

`strata serve` が起動に使う有効設定と、サーバー・推論エンジンへ渡す引数を計算して表示します。設定ファイルや profile の解決、設定の検証、エンジン引数の組み立ては行いますが、この分岐では foreground server の `main` を呼ばず、サービスを起動しません（`strata_cli/cli.py:915-955`）。

## 使い方

```sh
strata serve --profile /absolute/path/run-config.json --plan

# 保存 profile を指定する場合
strata serve --profile my-profile --plan --output json
```

`--profile` は必須で、`--config` は同じ引数の別名です。値が JSON ファイルへのパスならその run config を読み、名前なら保存 profile を解決します（parser: `strata_cli/cli.py:46-48`、解決: `strata_cli/cli.py:545-547`、`strata_control/profiles.py:382-388`）。

## 値と既定値

`--plan` は `argparse` の `store_true` で、値は不要です。未指定なら通常の foreground 起動経路へ進みます（`strata_cli/cli.py:63`、`strata_cli/cli.py:940-955`）。

計画に含まれる設定は、コマンドライン指定、保存 profile の override、run config、該当する環境変数、既定値の順に解決されます。`--host`、`--port`、`--parallel`、`--batch-groups`、`--max-queue`、`--queue-timeout`、`--offline`、`--batch-telemetry` の実効値と由来が `effective` / `origin` に出ます。既定値は host `127.0.0.1`、port `8095`、offline `false`、batch telemetry `false` で、残りは未指定です。batch telemetry は明示設定や profile / config がない場合に `STRATA_BATCH_TELEMETRY=1` で有効になります（`strata_cli/cli.py:745-769`）。

関連値も検証されます。port は `0..65535`、parallel は `1..1024`、max queue は `0..4096`、queue timeout は有限の `0.1..600` 秒、shutdown timeout は `0..300` 秒です。queue timeout には max queue が必要です。profile / run config の override 検証に加え、run config の `--batch` / `--slots` と parallel override、`--batch-groups` の重複、offline と MCP / before-load 設定の競合も拒否されます（`strata_cli/cli.py:920-935`、`strata_cli/cli.py:745-779`）。`--batch-groups` は `auto` または正の整数として検証されます（`strata_cli/cli.py:55,932-935`）。

## 実行時の動作

`--plan` を指定すると、run config を読み、profile / CLI / config / 環境の値から実効設定を作り、サーバー引数とエンジン引数を算出します。計画データには profile 名と revision、config のパス、model name、実効値と由来、server argv、engine executable / argv、engine 引数生成時の notes が含まれます。key・token・secret・password・credential を含む engine 引数は値を伏せます（`strata_cli/cli.py:726-742,745-826`）。

`--output human`（既定）では計画オブジェクトを整形 JSON として stdout に出します。`--output json` では `schema_version` と `ok` を含む JSON 応答になります。`--output json` は `--plan` が必要です。`--output jsonl` は foreground lifecycle 用なので `--plan` と併用できず、いずれもエラー code 2 になります（`strata_cli/cli.py:64-67,829-835,915-919,535-542`）。

`--quiet` は human 出力を抑制します。計画は `--output human` では quiet capture に入り、成功時に表示されません。JSON 出力は quiet capture を迂回します（`strata_cli/cli.py:2217-2247`）。

parser の `--json` help は「`--plan --output json` の alias」と説明しますが、実装では `--json` により output が `json` になるだけで、`plan` は有効化されません。そのため `--json` 単独は `_serve` の `--output json requires --plan` エラーになります。`--plan --json` または `--plan --output json` なら JSON 計画を出します（parser: `strata_cli/cli.py:66`、dispatch: `strata_cli/cli.py:2232-2235`、検査: `strata_cli/cli.py:915-919`）。

## 適用条件と副作用

`--plan` は config/profile の読み込みと引数生成を行います。`--ready-file` が同時指定されると、そのパスが絶対パスで親ディレクトリが存在し、既存ファイル・symlink でないことを事前検査します。この計画段階では ready file 自体は作成しません（`strata_cli/cli.py:807-810`、`serve/ready.py:16-24`）。

保存 profile を読む際、通常の read が `PermissionError` になるとアクセス権修復を一度試して再読込します。したがって `--plan` でも、権限状態によって profile ファイルのアクセス権が修復される副作用があり得ます（`strata_control/profiles.py:150-166`、`strata_control/private_files.py:476-484`）。エンジンは起動しませんが、`engine_args` は config の user args、drafting / vision / parallel 等を反映して最終 argv を作るため、生成 notes が計画に含まれます（`serve/server.py:3077-3129`）。

## 出力とエラー

無効な値や組み合わせは起動前に拒否されます。`_serve_error` は通常形式では `strata: ...` を stderr に出し、JSON 形式では `schema_version: 1` と `ok: false` を含む JSON を stdout に出します。確認された範囲では `_serve` の明示的な出力形式・範囲エラーは code 2、config/profile の読み込み問題は `ProfileError` に設定された code（読み込み失敗は code 5）で返ります（`strata_cli/cli.py:829-835,915-939`、`strata_control/profiles.py:135-147,150-166`、例外処理: `strata_cli/cli.py:2166-2188`）。

## 根拠

- `strata_cli/cli.py:46-67` — `serve` parser、必須 config、`--plan` と出力関連オプション。
- `strata_cli/cli.py:745-826` — 値の優先順位・検証、実効 server / engine argv と計画データ。
- `strata_cli/cli.py:915-955` — 計画時の分岐、出力形式の組み合わせ、通常起動との境界。
- `strata_cli/cli.py:2217-2247` — `--json` / `--quiet` の dispatch。
- `strata_control/profiles.py:135-147,150-166,382-388` — config 読み込み、profile 読み込み、参照の解決。
- `strata_control/private_files.py:476-484` — 読み込み権限エラー時の修復再試行。
- `serve/ready.py:16-24` — `--ready-file` の副作用を伴わない事前検査。
- `serve/server.py:3077-3129` — engine argv を組み立てる処理。
