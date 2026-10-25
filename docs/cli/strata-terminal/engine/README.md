# `strata engine`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の Strata checkout は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata engine` |
| 実装 | `strata_cli/cli.py`、`strata_control/calibration.py` |

## 役割

`strata engine` はエンジン設定のキャリブレーション操作をまとめるコマンド階層です。この revision で登録されているサブコマンドは `calibrate` のみです。キャリブレーションは、デコード設定の測定、測定レポートの確認、設定への適用、適用前の設定への復元を分けて行います（`strata_cli/cli.py:174-189`）。

## 使い方

```sh
# 対象 profile / run config の事前確認。エンジン起動・設定変更なし
strata engine calibrate --profile office --plan

# 測定。実行中のモデルを停止し、新しいレポートの保存先を指定する
strata engine calibrate --profile office --measure --exclusive --out ./calibration.json

# レポートの適用可否を確認してから適用
strata engine calibrate --profile office --review-result ./calibration.json
strata engine calibrate --profile office --apply-result ./calibration.json --exclusive

# 適用前の状態へ戻せるか確認し、確認後に復元
strata engine calibrate --profile office --review-rollback ./calibration.json
strata engine calibrate --profile office --rollback-result ./calibration.json --exclusive
```

`--profile` は必須で、保存済みプロファイル名または明示した JSON run config のパスを解決します（`strata_control/profiles.py:382-388`）。操作は `--plan`、`--measure`、`--review-result`、`--apply-result`、`--review-rollback`、`--rollback-result` のうち一つを選びます。詳細は [`calibrate` コマンド概要](calibrate/README.md) と、各操作の [`--plan`](calibrate/--plan.md)、[`--measure`](calibrate/--measure.md)、[`--review-result`](calibrate/--review-result.md)、[`--apply-result`](calibrate/--apply-result.md)、[`--review-rollback`](calibrate/--review-rollback.md)、[`--rollback-result`](calibrate/--rollback-result.md) を参照してください。これらは索引に掲載された文書パスです。

## 実行モードと主な動作

- **計画 (`--plan`)**: コンポーネントと対象設定を確認し、測定予定の設定群を示します。エンジンを起動せず、run config も書き換えません。表示上の所要時間目安は約15〜30分です（`strata_control/calibration.py:95-111`; `strata_cli/cli.py:1114-1126`）。
- **測定 (`--measure`)**: `--exclusive` と `--out REPORT.json` が必要です。decode sweep を実行し、エンジン・モデル・設定・ハードウェア等の識別情報と候補設定を含むレポートを新規作成します。既存の出力ファイルは拒否され、設定ファイルは変更されません（`strata_cli/cli.py:1065-1075`; `strata_control/calibration.py:270-336`）。
- **結果確認 (`--review-result`)**: レポートの形式と内容、経過時間、設定・エンジン・モデル・ハードウェアの同一性を確認し、候補値と現在値を表示します。状態を変更しません。レポートが古い、または対象環境が変化した場合は適用不可として返します（`strata_control/calibration.py:339-385`; `strata_cli/cli.py:1076-1085`）。
- **適用 (`--apply-result`)**: `--exclusive` が必要です。対象の稼働状態とレポートの鮮度を再確認し、候補設定でエンジンを一時起動してトークン生成を確認した後、run config と setup のキャリブレーション記録を更新します。更新前の config / 設定のバックアップと適用記録を残します（`strata_cli/cli.py:1086-1095`; `strata_control/calibration.py:526-626`）。
- **復元確認・復元 (`--review-rollback`, `--rollback-result`)**: 復元確認はファイルを変更せず、バックアップ、現在の config / setup 設定、環境の同一性、対象ポートの稼働状態を検査します。復元実行は `--exclusive` が必要で、復元候補の smoke generation 後に適用前の config と setup 設定を戻します（`strata_control/calibration.py:646-681,684-735`; `strata_cli/cli.py:1096-1113`）。

## 注意点

測定・適用・復元の実行前には、対象デバイスを使うモデルと Strata runtime instance を停止してください。処理はプロファイルのポートで待受中のサーバーがある場合や、管理対象 runtime instance が残っている場合に拒否されます。実行時には排他 lease と profile lock を利用します（`strata_control/calibration.py:205-229,270-286,526-540,684-697`）。

Terminal archive には `setup.py` と `tools/calibrate.py` が含まれないため、キャリブレーション機能を使うにはそれらを含む full Strata folder が必要です。`STRATA_INSTALL_DIR` でそのフォルダーを指定できます。利用できない場合は、機能は終了コード5の説明付きエラーで停止します（`strata_control/calibration.py:41-64,67-79`）。

測定レポートは最大2 MiBで、適用可否は作成後30日を超えた場合や対象設定等の識別情報が変わった場合に失われます。適用・復元時の smoke generation が失敗した場合、設定は変更されません。通常の CLI は人向け出力、`--output json`（または `--json`）は JSON 出力です。処理エラーは標準エラー側のエラー表示と非ゼロ終了コードになり、レビューで適用不可の場合は終了コード6です（`strata_control/calibration.py:33-38,339-359,363-385,526-571,684-720`; `strata_cli/cli.py:508-515,2166-2193`）。

## 関連文書

- [CLI オプション索引](../../README.md) — `strata-terminal` のコマンド階層とオプション文書。
- [`strata engine calibrate` の概要](calibrate/README.md) — 6つの測定・確認・適用操作。

## 根拠

- `strata_cli/cli.py:174-189` — `engine` / `calibrate` の parser、必須引数、相互排他の action 群。
- `strata_cli/cli.py:1059-1126,2142-2143,2166-2193` — 各操作の dispatch、前提条件、出力・終了コードの処理。
- `strata_control/calibration.py:41-79,95-111` — full folder の要件と読み取り専用計画。
- `strata_control/calibration.py:205-229,270-336,339-385` — 排他条件、測定、レポート保存・鮮度確認。
- `strata_control/calibration.py:526-626,646-735` — 適用・バックアップ・復元の確認と副作用。
