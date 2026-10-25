# `--full-quality`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--full-quality` |
| 別名 | なし |
| 値 | 取らない真偽フラグ。指定すると有効 |

## 役割

DeepSeek-V4.1-Flash の起動で、1語あたり6 expertを使う full quality を選びます。`--speed full` と同じ設定です。parser は `strata_cli/launch/cmd.py:108-111` で `store_true` として定義しています。

## 使い方

```sh
strata launch --model ist-das-2.00bpw --family deepseek41 --full-quality --no-tui
```

モデル名は利用可能な DeepSeek モデルに置き換えてください。既存 preset と組み合わせる場合は `strata launch --preset "NAME" --full-quality` のように指定できます。

## 値と既定値

値は不要です。省略時はこのフラグから speed 設定を変更しません。preset を読み込んだ場合も、`--full-quality` を指定しなければ preset の設定が残ります。フラグを繰り返しても真偽値は有効のままです。文字列値を取る parser 定義ではなく、別名もありません（`strata_cli/launch/cmd.py:75-85,108-112,201-207`）。

## 実行時の動作

起動引数はまず preset（指定時）または新規 `LaunchSettings` に読み込まれ、その上に CLI の設定が反映されます。`--full-quality` がある場合は `s.speed = "full"` を設定します。`--speed faster` も同時に指定したときは `--full-quality` が優先し、警告を追加します。したがって、引数の記述順にかかわらず full が採用されます（`strata_cli/launch/cmd.py:201-207,240-245`）。

DeepSeek の対象モデルでは `Runner` が選択した engine の版を確認し、対応する場合に設定内の既存 `--experts` 引数を取り除いて `--experts 6` に置き換えます。対応 engine は 0.1.50 以降です（`strata_cli/launch/runner.py:422-425,475-489,2034-2039`）。起動計画と起動後の要約には speed の説明が表示され、計画には実行相当の CLI 表記も含まれます（`strata_cli/launch/runner.py:2011-2022,2041-2050`; `strata_cli/launch/cmd.py:772-783,842-849`; `strata_cli/launch/settings.py:291-318`）。

## 適用条件と副作用

- `--full-quality` は `strata launch` の parser に属します。`strata connect` のオプションではありません（`strata_cli/launch/cmd.py:75-82,108-112`）。
- DeepSeek-V4.1-Flash 以外のモデルでは、speed 設定は「DeepSeek 用で、このモデルでは使わない」という警告とともに `None` に戻されます。通常のモデルにはこの選択肢がないため、expert 数は変わりません（`strata_cli/launch/cmd.py:325-353`）。
- DeepSeek でも engine が 0.1.50 未満、未検出、または版を取得できない場合は `--experts` を渡さず、engine 側の既定動作に任せます。ソース上、この条件自体は起動失敗にせず、speed の明示値も engine に反映しません（`strata_cli/launch/runner.py:415-425,2024-2039`）。
- このフラグ単独では preset の保存を指定しません。`--save-preset` などを併用した場合の保存や、通常起動で必要となるモデル準備・server 起動は `strata launch` の動作です。`--plan` を併用した場合は計画表示後に終了し、「Nothing was changed.」と表示します（`strata_cli/launch/cmd.py:755-784,808-824`）。

## 出力とエラー

`--full-quality --speed faster` の組み合わせでは、平文実行時は警告として表示され、JSON 出力では launch 結果または計画の warnings に含まれます。full quality 自体について追加の値検証はありません（`strata_cli/launch/cmd.py:240-245,744-759,785-788,825-829`）。

本フラグに値を付ける構文は parser 定義にありません。parser が不正引数としてどう表示するか・終了コードを返すかは Python `argparse` の共通処理であり、このフラグ固有のエラー経路は確認されませんでした。

## 根拠

- `strata_cli/launch/cmd.py:75-82,108-112` — コマンド階層、フラグ定義と help。
- `strata_cli/launch/cmd.py:201-207,240-245` — preset 読み込み後の設定反映、`--speed faster` との優先順位。
- `strata_cli/launch/cmd.py:325-353` — モデル適用条件と DeepSeek 以外での警告・解除。
- `strata_cli/launch/runner.py:422-425,475-489,1390-1397,2034-2039` — engine 対応版の判定、設定済み `--experts` の置換と実行時の適用。
- `strata_cli/launch/cmd.py:755-784,808-829` — 計画表示と通常起動の分岐。
