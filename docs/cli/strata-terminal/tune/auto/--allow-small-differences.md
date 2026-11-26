# `strata tune auto --allow-small-differences`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--allow-small-differences` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ（省略時 `false`） |

## 役割

自動チューニングで、標準設定と回答が少し異なる可能性のある「placement」分類の候補も試すよう許可します。候補を無条件に実行するものではなく、backend、モデル系統、チューニング目的、ハードウェア条件などの候補ごとの適用条件は引き続き評価されます。フラグを付けない場合、その分類の候補は計画から除外されます。`terminal/strata_control/tune_knobs.py:25-33,93-114,375-379,434-452`

## 使い方

```sh
# まず、回答に差が出る可能性のある候補も含めた計画を表示する（測定は開始しない）
strata tune auto PROFILE --allow-small-differences --plan

# 計画を確認した後、対象プロフィールの測定を実行する
strata tune auto PROFILE --allow-small-differences
```

`PROFILE` は調整対象の保存済みプロフィール名に置き換えます。`target` はモデル名、保存済みプロフィール名、または実行設定 JSON も受け付けます。`--plan` は候補計画の表示後に終了し、エンジン測定を開始しません。`terminal/strata_cli/tune_commands.py:27-28,349-353`

## 値と既定値

- `argparse` の `store_true` で定義され、引数値は不要です。指定すると `true`、省略すると `false` です。別名や独自の値検証はありません。`terminal/strata_cli/tune_commands.py:37-38`
- 同じフラグを複数回指定しても、真偽値を設定するだけで追加の効果はありません。後続の通常の候補条件検査は省略されません。`terminal/strata_cli/tune_commands.py:37-38`、`terminal/strata_control/tune_knobs.py:434-452`

## 実行時の動作

`strata tune auto` の parser が受け取った値は `autotune.Options.allow_placement` に渡され、設定・ハードウェア情報から作る候補選択 context に伝搬します。候補選択では `answer == "placement"` の候補はこの値が真の場合だけ許可されます。`exact` 候補は常に許可され、回答が実行ごとに変わり得る `nonrepeatable` 候補には別の `--allow-not-repeatable` が必要です。`quality` 分類は自動選択されません。`terminal/strata_cli/tune_commands.py:342-345`、`terminal/strata_control/autotune.py:54-63,902-932`、`terminal/strata_control/tune_knobs.py:25-33,375-379,445-448`

対象候補の例には、expert cache の再配分設定、投機実行の窓幅、PCIe 転送比率、特定モデル系統の行ブロックや prompt chunk 設定があります。候補一覧にはbackend・モデル・目的・メモリ等の適用条件があり、該当しない場合や `--mode quick` で thorough 専用候補を選ぶ場合などは除外されます。したがって、このフラグだけで全候補が必ず測定されるわけではありません。`terminal/strata_control/tune_knobs.py:93-114,434-452`

チューナーは現在設定の測定後、選ばれた候補を交互に測定・比較し、速度向上が確認された設定を選びます。通常は結果が `improved` または `default_confirmed` のとき preset を保存します。`--no-save` を付けると preset 保存を抑止できます。フラグ自体がモデル設定を即時変更するのではなく、候補探索の範囲を広げ、その結果が採用・保存された場合に後の起動へ反映される設定を変えます。`terminal/strata_control/autotune.py:397-448,541-570,590-629`、`terminal/strata_cli/tune_commands.py:408-418`

既定の `--output human` では進捗を標準エラー、結果を標準出力へ出します。`--output json` では JSON 結果を標準出力へ出し、進捗の人向け表示は抑えます。`--status-file` が指定されていれば進捗状態 JSON も更新されます。デスクトップ連携の Terminal launcher は設定 `tune_allow_small` が有効なとき、このフラグを内部の `strata tune auto` 呼び出しに追加します。`terminal/strata_cli/tune_commands.py:48-50,358-369,417-425`、`terminal/strata_cli/launch/runner.py:2395-2407`

## 適用条件と副作用

- チューニングが対象モデルをサポートし、エンジンが見つかり、候補ごとのbackend・モデル・目的・ハードウェア条件を満たす必要があります。Hy4-Flash と Inkling-2-Mini は自動チューニング対象外で、別の案内を返します。`terminal/strata_cli/tune_commands.py:324-338`、`terminal/strata_control/tune_knobs.py:434-452`
- `--plan` を付けない場合、現在の設定と候補設定で実エンジンを起動して測定します。混雑状況や空きメモリの確認、待機もあり得ます。`--work-dir` を指定しない場合は一時作業ディレクトリを使い、通常終了時に削除します。`--work-dir` 指定時はログ等を保持します。`terminal/strata_cli/tune_commands.py:371-384`、`terminal/strata_control/autotune.py:319-354`
- 実行結果の試行記録とチューニングレポートは保存されます。成功結果の preset 保存だけを止める場合は `--no-save` を併用します。`terminal/strata_cli/tune_commands.py:402-424`
- オプション固有の追加 validation、警告、ファイル操作はありません。回答への差異を許す選択であり、候補の設定内容や効果は機種・backend・条件により異なります。`terminal/strata_cli/tune_commands.py:37-38`、`terminal/strata_control/tune_knobs.py:93-114,434-452`

## 出力とエラー

このフラグ自体が拒否される値はありません。対象の読込や `--goal` の解析に失敗した場合、または Hy4 / Inkling 対象の場合は失敗経路へ進みます。human 出力では `strata: <message>` を標準エラーへ出し、JSON 出力では `ok: false` と error object を標準出力へ出します。これらの経路は通常 `2`、エンジン実行ファイルがない場合は `5` を返します。測定結果に基づく失敗・中断は結果を出力し、結果種別に応じた終了コードを返します（中断 `130`、それ以外の通常成功扱いでない結果 `6`）。`terminal/strata_cli/tune_commands.py:101-114,314-338,421-425`

## 根拠

- `terminal/strata_cli/tune_commands.py:21-50` — `strata tune auto` の parser、フラグ定義、および隣接する `--plan`、`--no-save`、`--output`、`--status-file`。
- `terminal/strata_cli/cli.py:514,1722-1723` — tune parser への登録と `auto` サブコマンドの処理委譲。
- `terminal/strata_cli/tune_commands.py:314-353,371-425` — 値を Options に渡す処理、計画モード、測定、記録・preset 保存、出力と終了コード。
- `terminal/strata_control/autotune.py:54-81,397-448,902-932` — `allow_placement` の既定値、候補探索、設定 context への伝搬。
- `terminal/strata_control/tune_knobs.py:25-33,93-114,375-379,434-452` — 回答クラスと候補の例、許可判定、および候補適用条件。
- `terminal/strata_cli/launch/runner.py:2395-2407` — Terminal launcher が設定に応じて同じフラグを内部呼び出しへ渡す処理。
