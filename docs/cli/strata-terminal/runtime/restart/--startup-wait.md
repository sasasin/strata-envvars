# `--startup-wait`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime restart` |
| オプション | `--startup-wait` |
| 別名 | なし |
| 値 | 秒数（有限の数値、1〜600 秒。小数可） |

## 役割

再起動後、新しい runtime が ready になるまで待つ時間を指定します。ready には、起動した server の ready 情報に加え、runtime host による readiness 検証が含まれます。既定値は300秒です。

## 使い方

```sh
strata runtime restart --profile my-profile --startup-wait 420
```

## 値と既定値

- parser は値を `float` に変換し、未指定時は `300` 秒です。
- 通常の再起動では `strata_control.management._seconds` が有限値かつ `1 <= 値 <= 600` かを検証します。小数も使えます。NaN、無限大、範囲外、数値に変換できない文字列は受理されません。
- 検証失敗は `ProfileError` となり、通常出力では stderr に `strata: ...`、JSON 出力ではエラー JSON を出し、終了コード2になります。
- `--plan` と同時に指定した値も parser では受理されますが、計画分岐はこの値の検証前に返るため、計画の計算や待機には使われません。

## 実行時の動作

`--startup-wait` は `strata_cli.cli` から `management.runtime_action` に渡され、通常実行では `runtime.restart(..., startup_wait=...)` に転送されます。`--wait` は別の値で、runtime host への操作 RPC の応答待ち時間です。両方を省略した場合、startup readiness は300秒、RPC は1000秒です。

runtime host は再起動前に現行 runtime が ready であること、保存済み profile から作った新しい起動内容、profile revision や source の条件を確認します。問題があれば停止前に失敗を返します。その後、現行 server を停止し、新しい server を起動して `startup_wait` の間 readiness を確認します。起動した子プロセスの ready 情報を検出すると generation/readiness 検証を行い、その検証にも同じ期限が適用されます。

新しい server が期限内に ready にならない、または起動に失敗した場合、Strata は新 server を停止し、旧構成の元ファイル内容がまだ利用できる場合は旧 server を再起動して rollback readiness も同じ `startup_wait` で待ちます。rollback が成功してもコマンド結果は失敗（`rolled_back: true`、終了コード6）です。rollback もできない場合は `rolled_back: false`、state `failed`、終了コード6になります。起動後に readiness を確認できない場合の内部結果には `startup_wait_expired`（終了コード8）が含まれます。

## 適用条件と副作用

- 通常の `restart` 実行に適用されます。`--plan` は drain せず計画を返す経路なので、この待機時間を消費しません。
- 時間の起点は server の停止完了後、新しい server の readiness 待ちに入ってからです。停止処理そのものの猶予は `--wait` ではなく runtime host の shutdown timeout に関係し、startup wait には含まれません。
- `--wait` を短くして RPC が先にタイムアウトした場合、CLI は「runtime operation wait expired」（終了コード8）を返し得ます。RPC クライアントのタイムアウトは host 内の再起動処理を取り消す仕組みではないため、状態確認が必要です。
- 旧 server の停止、新 server の起動、失敗時の停止と旧 server の再起動が起こり得ます。したがって成功・失敗いずれも、一時的にサービスが利用できない時間が生じます。

## 出力とエラー

通常の人向け出力は profile と最終 state を表示し、失敗時は error も表示します。JSON 出力では結果オブジェクトを出力します。restart の失敗時には、設定から取得できる engine log の場所と末尾行が stderr に追加表示されることがあります。終了コードは結果の `exit_code` を返します。入力値の範囲エラーは2、readiness の期限切れは8、restart の失敗や rollback 結果は通常6です。

## 根拠

- parser、既定値、オプション scope: `strata_cli/cli.py:238-254`
- CLI から runtime 管理処理への引き渡し: `strata_cli/cli.py:1345-1356`
- finite/range validation と restart branch、`--plan` 分岐、`--wait` との転送: `strata_control/management.py:113-117`, `strata_control/management.py:292-333`
- restart API の再検証と runtime host への RPC: `strata_control/runtime.py:702-731`
- 起動した子プロセスの readiness deadline と検証: `strata_control/runtime.py:840-900`, `strata_control/runtime.py:948-988`
- drain、新 server 起動、readiness wait、rollback: `strata_control/runtime.py:1043-1130`
- operation wait と RPC timeout の扱い: `strata_control/runtime.py:402-441`
- CLI の人向け/JSON 出力、失敗時 log hint と終了コード: `strata_cli/cli.py:1357-1388`
