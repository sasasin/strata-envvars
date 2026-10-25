# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime stop` |
| オプション | `--json` |
| 別名 | `--output json`（同じ JSON 出力を選択） |
| 値 | 値を取らないフラグ。JSON 出力を有効にする |

## 役割

`runtime stop` の結果を機械処理しやすい JSON で標準出力へ出します。停止処理自体の内容や確認条件は変えません。索引上も `runtime/stop` のオプションです。

## 使い方

停止せずに、現在の所有者・インスタンスと停止計画を JSON で確認する例:

```sh
strata runtime stop --profile my-profile --plan --json
```

実際に停止するときは `--plan` を外します。停止は稼働中インスタンスに作用します。計画で表示された ID を実行前提条件にする場合は `--if-owner-id` と `--if-instance-id` も指定できます。

## 値と既定値

`--json` は `store_true` フラグで、値は不要です。指定しない場合は既定の `--output human` のままです。`--output` は `human` または `json` を受け取り、既定値は `human` です。`main()` は `--json` が真なら `a.output` を `json` に設定するため、`--output human --json` と併記した場合も JSON になります。`--json` の繰り返し指定は真のままです。

## 実行時の動作

`runtime stop` parser 自体は `--output` を定義し、`--json` は parser 構築の最後に one-shot parser 群へ共通追加されます。この群には `runtime_stop` が含まれます。したがってこのオプションは `strata runtime stop` で有効で、グローバルな全コマンド共通フラグではありません（`strata runtime stop --json` のようにサブコマンド後に置きます）。

`--json` が指定されると、通常の実行結果は `schema_version: 1` と runtime operation の返却データを含む JSON オブジェクトとして stdout に1行出ます。成功した `--plan` は同じ共通形式で `ok: true` と `plan` を返します。失敗結果も operation の `ok: false`、`error`、`exit_code` 等を JSON に含め、プロセス終了コードはその結果の `exit_code`（なければ 6）になります。`--output json` も同じ経路です。

このフラグを指定すると `--quiet` の有無によらず JSON 出力経路が選ばれ、人間向け出力を捕捉する quiet 処理には入りません。runtime stop は `--wait`（省略時 330 秒）、`--plan`、所有者・インスタンス ID 条件を `management.runtime_action()` に渡して結果を得ます。`--json` はこれらの停止条件や停止動作を変更しません。

## 適用条件と副作用

通常の `runtime stop` は所有中のローカル runtime に停止要求を送り、停止処理と drain を行います。`--plan` を付けた場合は計画を返すだけで、停止しません。ID 条件が指定されると、現在の owner/instance が一致することを確認し、不一致なら実行を拒否します。これらは `--json` 固有の副作用ではなく、同コマンドの処理です。

`--json` 自体はプロファイル・ファイル・ネットワークを変更しませんが、併用するコマンド実行は `--plan` の有無に応じて停止操作を行います。

## 出力とエラー

- 処理結果は stdout の JSON です。通常の成功は `{"schema_version":1,...}`、計画成功は `{"schema_version":1,"ok":true,"plan":...}` 形式です。
- 実行結果として返る失敗は JSON の `ok: false` を伴い、結果に応じた終了コードを返します。
- runtime 処理で `ValueError`（`ProfileError` を含む）などが送出された場合も、`--json` 有効時は `schema_version`、`ok: false`、数値の `error.code` と `error.message` を含む JSON を stdout に出します。
- 不明な引数や必須の `--profile` 欠落など parser 段階のエラーは `--json` の正規化より前に処理されます。この場合は argparse の usage/error が stderr に出て、終了コード 2 となり、JSON 形式は保証されません。

## 根拠

- `strata_cli/cli.py:226-232` — `runtime stop` の parser、`--output` の選択肢と既定値。
- `strata_cli/cli.py:508-515` — one-shot parser 群に `runtime_stop` を含め、値を取らない `--json` を追加する箇所。
- `strata_cli/cli.py:2217-2236` — 引数解析後に `--json` から `output="json"` へ変換し、JSON モードでは quiet の人間向け捕捉を通らず `_run()` へ進む経路。
- `strata_cli/cli.py:1331-1373` — runtime dispatcher の JSON 成功・失敗結果と終了コード。plan 成功は `_success()` に包まれる。
- `strata_cli/cli.py:527-542` — JSON エラー・成功共通出力形式。
- `strata_cli/cli.py:2166-2193` — 例外を JSON エラー化する条件と終了コード。
- `strata_control/management.py:113-117, 271-291` — stop の wait 範囲検証、plan と実行の分岐、ID 条件の照合、runtime stop 呼び出し。
- `strata_control/runtime.py:602-611, 614-640` — stop 計画が停止せず情報を返すこと、および通常の stop 呼び出し。
- `strata_control/runtime.py:990-1012, 1209-1224` — drain/停止処理の結果と、owner/instance の再確認後にそれを呼ぶ経路。
