# `strata runtime restart --wait`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime restart` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | 秒数（`float`） |
| 既定値 | `1000` 秒 |

## 役割

保存済み profile の実行中 instance を再起動する要求について、CLI が owner host から応答を待つ上限時間を指定します。新しい instance の起動準備を待つ時間は別オプション `--startup-wait` です。

## 使い方

```sh
strata runtime restart --profile office --wait 1200
```

`--profile` は必須です。実際の停止・再起動をせず比較計画だけを表示する `--plan` と同時に使った場合、`--wait` は検証も実行もされません。

## 値と既定値

- parser は `float` として値を読み取り、既定値を `1000` 秒にします。短縮別名はありません（`strata_cli/cli.py:238-246`）。
- 実行モードでは有限値 `1`〜`1800` 秒（境界を含む）が受理されます。小数も指定できます。範囲外、`NaN`、正負の無限大は拒否されます（`strata_control/management.py:113-117,305-306`）。
- `--plan` の分岐はこの範囲検査より前に処理されるため、計画表示時には `--wait` の値は restart 要求に渡りません（`strata_control/management.py:299-306`）。

## 実行時の動作

実行モードでは `--wait` が restart 操作の `timeout` として owner RPC に渡されます。owner RPC の接続・応答読み取りがこの時間内に完了しない場合、CLI 側は `runtime operation wait expired; inspect runtime status` として失敗します（`strata_control/management.py:305-306,327-333`; `strata_control/runtime.py:702-731,402-430`）。

この値は再起動要求全体への CLI 側の待機上限です。停止後に新 instance が ready になるまでの待機上限ではなく、それは `--startup-wait`（既定 300 秒、1〜600 秒）で指定します（`strata_cli/cli.py:245-246`; `strata_control/management.py:305-306,327-333`; `strata_control/runtime.py:702-711`）。停止時の猶予は host の `shutdown_timeout` に基づいて処理されます（`strata_control/runtime.py:990-1012,1043-1093`）。

再起動処理は既存 runtime が ready であること、新 profile の事前確認、source の変更条件などを確認してから既存 child を止め、新しい設定で起動します。新 instance が失敗した場合は旧設定での rollback を試みます。これらは `--wait` の値で直接切り替わる動作ではありません（`strata_control/runtime.py:1043-1130`）。

## 適用条件と副作用

`--wait` は `strata runtime restart` の実行要求に適用されます。`--plan` は待機時間を設定せず、再起動も行いません。実行時に RPC の期限が切れても、CLI の応答待ちが終わったことだけでは owner host 側の操作が中止・未実行だったとは判断できません。実装は状態確認を促しており、割り込み時には journal で完了状態を確認するよう応答します（`strata_control/runtime.py:427-430`; `strata_control/management.py:605-609`）。

## 出力とエラー

- 成功・通常の操作結果は人向け形式、または `--output json` / `--json` による JSON で出力されます。操作失敗時は `strata runtime restart` の結果に応じた非 0 終了コードになり、実行失敗では engine log の案内も stderr に出る場合があります（`strata_cli/cli.py:1331-1373`; `strata_cli/cli.py:508-515`）。
- 無効な範囲の値は validation error になります。RPC の応答待ち期限超過は `ProfileError`（終了コード 8）として報告され、runtime status の確認を促します（`strata_control/management.py:113-117,305-306`; `strata_control/runtime.py:427-430`）。
- 引数自体が数値として解釈できない場合は argparse が拒否します（parser 定義 `strata_cli/cli.py:245`）。

## 根拠

- `strata_cli/cli.py:238-254` — restart parser、必須 profile、`--wait` の型・既定値、隣接オプション。
- `strata_cli/cli.py:508-515,1331-1373` — 共通 `--json` / `--quiet` の追加、CLI から管理層への転送、人向け・JSON 出力と終了コード。
- `strata_control/management.py:113-117,292-336` — 有限秒数の検証、plan 分岐、restart timeout の伝達。
- `strata_control/runtime.py:402-430,702-731` — RPC 待機期限と期限超過経路、restart RPC 呼び出し。
- `strata_control/runtime.py:978-1012,1043-1130` — startup ready 待ち、停止、再起動と rollback の処理。
- 調査時の `git status --short --branch` は `## main...origin/main` で、未コミット変更は表示されませんでした。Release archive と実機環境別の挙動はこの調査では確認していません。
