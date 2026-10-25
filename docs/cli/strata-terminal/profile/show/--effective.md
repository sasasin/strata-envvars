# `--effective`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile show` |
| オプション | `--effective` |
| 別名 | なし |
| 値 | 値なしの真偽フラグ。既定値は `False` |

## 役割

保存プロファイルの表示に、参照 run config とプロファイル設定から解決した設定値・値の出所・起動計画を追加します。実際のサーバーや推論エンジンは起動しません。

## 使い方

```sh
strata profile show four-gpu --effective
strata profile show four-gpu --effective --output json
```

`four-gpu` は保存済みプロファイル名です。`--effective` は `show` parser にのみ定義され、`--output` は `human`（既定）または `json` を受け付けます（`strata_cli/cli.py:77-80`）。

## 値と既定値

値を取らない `store_true` フラグで、未指定時は `False` です。指定すると `profile show` の結果へ `plan` を追加します（`strata_cli/cli.py:77-80, 1015-1020`）。`--effective=false` のような値指定は受け付けず、余分な引数として parser エラーになります（`strata_cli/cli.py:2223-2231`）。

有効値の優先順位は、コマンド指定値、保存プロファイルの override、run config、環境変数（`batch_telemetry` のみ）、組み込み既定値です。このコマンドは起動時の値を渡さないため、通常はプロファイル override が run config より優先されます。既定値は `host=127.0.0.1`、`port=8095`、`parallel` / `batch_groups` / `max_queue` / `queue_timeout` は未設定、`offline=false`、`batch_telemetry=false` です。`batch_telemetry` は run config に値がない場合に限って `STRATA_BATCH_TELEMETRY=1` を true、それ以外の環境変数値を false として解釈します（`strata_cli/cli.py:745-765`）。

## 実行時の動作

フラグ指定時、保存プロファイルと revision を読み、`_launch_plan` を通じて run config を読み込みます。解決した値ごとに `saved_profile`、`run_config`、`environment`、`default` の出所も計算されます（`strata_cli/cli.py:958-969, 1015-1019, 745-779, 782-785`）。

出力の `plan` には、解決値と出所、プロファイル ID/revision、参照 config のパスと model 名、server 起動引数、engine 実行ファイルと引数、生成時の notes が含まれます。engine 引数内の key/token/secret/password/credential を含むフラグ値は redact されます（`strata_cli/cli.py:726-742, 782-826`）。既定の human 出力は整形 JSON、`--output json` は `schema_version` と `ok` を含む一行 JSON です（`strata_cli/cli.py:527-542`）。

計画生成では `engine_args` が呼ばれ、config による引数補完や drafting 設定の解決も反映されます。drafting の自動判定は GPU arch 情報を取得しようとしますが、取得時の例外は無視して既定のカード分類へ進みます（`serve/server.py:3061-3074, 3077-3129`）。ここで得られるのは計画値であり、実際に engine が受理した値や起動後の状態ではありません。

## 適用条件と副作用

`--effective` は `profile show` のスコープです。位置引数 `name` は保存済みプロファイルとして読み込まれ、ファイルパスは受け付けません（`strata_cli/cli.py:77-80, 958-969`; `strata_control/profiles.py:150-166, 382-388`）。run config の読み込み、プロファイル内容の検証、起動計画の生成を行いますが、`show` の分岐は `_success` で結果を出して戻り、サーバー起動処理へは進みません（`strata_cli/cli.py:1015-1020`）。

通常は表示のみですが、プロファイルファイルの読み込みで PermissionError が起きた場合、アクセス修復を一度試み、修復成功時はプロファイルの権限/ACL を変更して再読込します（`strata_control/profiles.py:150-166`; `strata_control/private_files.py:476-484`）。Windows では CLI 起動時にユーザー既定の所有者/DACL を設定しようとします（`strata_cli/cli.py:2217-2222`; `strata_control/private_files.py:349-389`）。

有効値は override validation にかけられます。`host` は空でなく空白を含まない文字列、`port` は `0..65535`、`parallel` は `1..1024`、`max_queue` は `0..4096`、`queue_timeout` は有限値 `0.1..600` 秒、`batch_groups` は `auto` または `1..1024`、boolean 設定は真偽値である必要があります。また `queue_timeout` は `max_queue` を必要とし、config の `args` に `--batch`/`--slots` がある場合の非 config `parallel`、`--batch-groups` がある場合の `batch_groups` override、MCP server または `before_load` を含む config と `offline=true` は拒否されます（`strata_cli/cli.py:745-779`; `strata_control/profiles.py:98-117`）。

## 出力とエラー

プロファイルがない場合、壊れた内容、非 regular file、1 MiB 超過、無効な schema、参照 run config の読み込み失敗、または上記の設定矛盾ではエラーになります。通常出力では `strata: <message>` を stderr に出し、JSON 出力では `ok:false` と error code/message を stdout に出します（`strata_control/profiles.py:120-166`; `strata_cli/cli.py:527-532, 2166-2183`）。プロファイル未保存や読み込み失敗は `5`、それ以外の profile validation エラーは既定で `2` です（`strata_control/profiles.py:30-35, 150-166`; `strata_cli/cli.py:2166-2173`）。

## 根拠

- parser、`--effective` の適用箇所と出力: `strata_cli/cli.py:69-80, 958-1020`
- 値の優先順位、validation と相互作用: `strata_cli/cli.py:745-779`; `strata_control/profiles.py:98-117`
- launch plan と引数の秘匿: `strata_cli/cli.py:726-826`
- engine 引数の計画生成: `serve/server.py:3061-3074, 3077-3129`
- プロファイル読込、参照先、権限修復: `strata_control/profiles.py:120-166, 382-388`; `strata_control/private_files.py:476-484`
- CLI のエラー整形: `strata_cli/cli.py:527-542, 2166-2188`

調査範囲は上記 commit の checkout に含まれる Terminal CLI ソースです。Release 配布物との照合や各 OS/backend 上の実行確認は行っていません。
