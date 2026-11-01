# `strata update --force`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 値なしのフラグ |

## 役割

通常は再提示を抑止するエンジン版を、もう一度更新候補として扱わせます。対象は、この版のテスト起動に失敗した場合と、一度 rollback した場合です。`--force` は候補選択の抑止を解除する指定で、エンジンのテスト起動や更新時の検証を省略しません（`strata_cli/update_cmd.py:43`、`strata_control/updater.py:610-620,1038-1049`）。

## 使い方

```sh
strata update --force
```

候補を表示するだけなら次のように指定できます。`--check` は feed を読み、エンジン・Control・アプリの更新内容を報告しますが、feed 以外はダウンロードしません（`strata_cli/update_cmd.py:52,235-241`、`strata_control/updater.py:631-639`）。

```sh
strata update --force --check
```

## 値と既定値

値や別名はありません。parser は `argparse` の `action="store_true"` で、未指定時は false、指定時は true になります。値を後置する構文ではありません（`strata_cli/update_cmd.py:37-46`）。

## 実行時の動作

更新 feed からこの PC 向けに選ばれた版が、インストール済み版より新しい場合、updater は通常、同じ版・同じ manifest のテスト起動失敗記録がある候補を `failed-before` として保留します。また rollback 元として記録された版は `skipped` として保留します。`--force` があるとこの保留判定を行わず候補を `available` として扱い、更新を続けます。失敗記録は同じ版の失敗から24時間を超えると再試行を妨げません（`strata_control/updater.py:598-621,1327-1334`）。

実際の更新では候補 engine package を取得して staging 領域に展開・検証し、そこから新 engine を起動してモデルを読み込み、1 token の応答まで確認します。テストが通った後に live の engine へ切り替え、以前の版を rollback 用に保持します。失敗時は新しい版を切り替えず、現在の engine を維持します。これらの手順は `--force` の有無で省略されません（`strata_control/updater.py:6-21,1054-1065,1068-1096,1097-1148`）。

`--check` と併用した場合は候補判定だけに反映され、更新処理には進みません。`--no-engine` を指定すれば engine 更新自体が対象外になります。Control と `--app` の処理は engine 候補の `force` 判定とは別です（`strata_cli/update_cmd.py:52-56,235-245`、`strata_control/updater.py:631-639,1466-1489`）。

## 適用条件と副作用

`--force` が候補を通すのは、通常の選択で `available` となる新しい候補が、テスト失敗または rollback の記録によって保留されている場合です。feed に適合する候補がない場合や、feed の候補がインストール済み版より古い場合に downgrade する指定ではありません。engine の署名・manifest・各ファイルの hash・PC との適合性確認、および serving 中の engine を更新しない規則は引き続き適用されます（`strata_control/updater.py:588-620,1038-1058`、module 概要 `strata_control/updater.py:6-21`）。

通常の `strata update` と同様に、実行すると feed と engine package をネットワークから取得し、component directory 内の staging/state/log を使います。テスト起動に失敗した場合は失敗記録を保存し、ログと診断記録を best effort で保持します。成功時は新 engine に切り替え、前の engine を rollback 用に残し、古い不要 engine を整理します（`strata_control/updater.py:800-857,1054-1065,1087-1096,1112-1148`）。

## 出力とエラー

通常出力では更新結果を component ごとに表示します。更新失敗は `strata: <理由>` を stderr に出し、失敗種別に応じた終了コードを返します。module docstring では `6` を network または test-start failure（旧版を使用継続）、`5` を署名・hash 等の拒否、`7` を engine serving 中、`130` を中断として定義しています。テスト起動失敗では `--force` を次の手順として案内する経路があり、再試行に失敗した場合は engine log の保存先も案内します（`strata_cli/update_cmd.py:10-11,187-192,245-266`、`strata_control/updater.py:85-128,893-915`）。

## 根拠

- `strata_cli/update_cmd.py:37-56` — 共通 parser の `--force` 定義、`strata update` の parser と隣接 option。
- `strata_cli/update_cmd.py:183-206,235-266` — parser 値を `Context.force` へ渡す箇所、check/update の分岐、出力とエラー経路。
- `strata_control/updater.py:321-339,573-621` — `Context.force` と候補選択、失敗・rollback 記録による抑止。
- `strata_control/updater.py:1038-1058,1068-1096,1112-1148` — 保留候補の実行、テスト起動、成功後の切替と失敗記録。
- `strata_control/updater.py:631-647,1466-1489` — check の read-only 更新判定と更新処理の component 順序。
- 調査時の Strata checkout は `git status --short --branch` で `## main...origin/main` と表示され、未コミット変更はありませんでした。
