# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench cancel` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |
| 既定値 | `human` |

## 役割

キャンセル要求の結果を人向けの短いメッセージで表示するか、機械処理向け JSON で表示するかを選びます。索引上のスコープは `strata bench cancel` です（`docs/cli/README.md:643-650`）。同じ `--output` でも `bench run` や `bench report` は別スコープであり、ここでは扱いません。

## 使い方

```sh
strata bench cancel --profile four-gpu --path /absolute/path/to/benchmark-run --output json
```

`--profile` には保存済み serving profile、`--path` には run の絶対パスを指定します。キャンセル対象の扱いは `--output` の値に左右されません。

## 値と既定値

parser は `choices=("human", "json")`、既定値 `"human"` として定義しています。別名はありません（`strata_cli/cli.py:335-338`）。選択肢以外の値は argparse の引数検証で拒否されます（同 `strata_cli/cli.py:2223-2231`）。

## 実行時の動作

`--output json` のとき CLI は machine 出力を有効にし、成功時に `schema_version: 1`、`ok: true` とキャンセル処理の結果（`path`、`state`）を JSON に出します。`human`（既定）の成功時は `Cancellation requested; check the saved report for the final outcome.` を表示します（`strata_cli/cli.py:1130-1132, 1175-1182, 535-542`）。このオプションは表示形式だけを切り替え、ファイルへの書き出し先を指定するものではありません。

表示形式とは独立して、コマンドは `--path` が絶対パスか確認し、保存済み profile を読み込んでからキャンセルを要求します（`strata_cli/cli.py:1175-1181`）。`--path` が run directory、`results.json`、または `progress.json` の場合は対応する出力 directory を特定します。対象 directory が不正（POSIX では owner-only でない場合を含む）、profile と path に対応する実行中 lease がない、または progress が `running` でない場合は拒否します（`strata_control/benchmarking.py:138-148`）。

要求が受理されると、directory に `cancel.request` marker を mode `0600` で新規作成して同期し、再確認した progress 状態を返します。POSIX では出力 directory と既存 marker の owner-only 条件も検査します。すでに同じ有効な marker があれば再利用します。返る `state` は通常 `cancel_requested`、処理側がすでに最終状態を保存していた場合は `cancelled` です（`strata_control/benchmarking.py:149-168`）。このコマンドの成功応答は停止完了の保証ではなく、実行側が marker を監視して処理を止め、最終 report を保存します。実行側は marker を最大約0.1秒間隔で確認し、検知時にベンチマークが所有する応答 socket を閉じます（`strata_cli/bench.py:57-82`）。最終化では `cancelled` と `successful: false` を report と progress に記録します（同 `strata_cli/bench.py:843-887`）。

## 適用条件と副作用

このオプション単体にはファイル・ネットワーク・benchmark の副作用はありません。副作用を起こすのはコマンドのキャンセル処理で、検証を通過した実行中 run の directory に `cancel.request` を作成します。runner が要求を検知した後に benchmark-owned stream を閉じ、キャンセル済みの結果を保存します（`strata_control/benchmarking.py:145-168`; `strata_cli/bench.py:57-82, 843-887`）。POSIX では出力 directory と marker の所有者・権限も検査します。Windows の ACL 等はこの調査で確認していません。

## 出力とエラー

- `human` のエラーは `strata: <message>` を stderr に出します。`json` では `schema_version: 1`、`ok: false`、`error.code` と `error.message` を含む JSON を出します（`strata_cli/cli.py:527-532, 2166-2188`）。
- 相対 `--path` は終了コード `2` で拒否されます（`strata_cli/cli.py:1177-1178`）。
- profile が保存されていない、path が存在しない、または検証に失敗した場合もエラーになります。profile 読み込み失敗は `ProfileError`（`ValueError` の派生）として扱われます（`strata_control/profiles.py:30-35, 150-166`）。
- 対象 directory / marker の権限・形式が不適切な場合は主に終了コード `5`、対象 run が有効な実行中でない、または最終 report 保存済みの場合は終了コード `6` で拒否されます（`strata_control/benchmarking.py:138-168`）。エラーコードは JSON 時は上記 JSON の `error.code` に入り、人向け出力時は終了コードになります。
- 成功時の終了コードは `0` です（`strata_cli/cli.py:535-542`）。

## 根拠

- 索引とコマンド階層: `docs/cli/README.md:643-650`（調査対象リポジトリ側の索引）。
- parser、必須引数、値の選択肢と既定値: `strata_cli/cli.py:335-338`。
- path/profile の確認と成功応答: `strata_cli/cli.py:1175-1182`。
- profile 読み込みとエラー型: `strata_control/profiles.py:30-35, 150-166`。
- exact-run lease、progress 検査、marker 作成と結果状態: `strata_control/benchmarking.py:105-168`。
- runner による marker 検出とキャンセル後の report/progress 保存: `strata_cli/bench.py:57-82, 843-887`。
- 成功・エラーの人向け / JSON 表示: `strata_cli/cli.py:527-542, 2166-2188`。

調査範囲は記載した checkout のソースです。同一 revision の CLI help、Release 配布物、Windows など個別 platform での実動作は確認していません。
