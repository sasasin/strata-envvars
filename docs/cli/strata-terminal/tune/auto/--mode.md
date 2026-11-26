# `strata tune auto --mode`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--mode` |
| 別名 | なし |
| 値 | `quick` または `thorough` |

## 役割

自動チューニングの測定予算と確認の厚さを選びます。`quick` は既定で、`thorough` は測定候補ごとのスクリーニング回数を増やし、勝った設定を5ペアで追加確認します。チューナーの結果が改善または現状維持と確認され、`--no-save` が指定されていなければ、選択した mode は保存プリセットの tuner 情報にも記録されます。

## 使い方

```sh
# 既定の短いチューニング
strata tune auto qwen/IQ3_S

# 時間をかけ、勝った設定を追加確認する
strata tune auto qwen/IQ3_S --mode thorough

# 実行せず、選択した mode での候補・所要時間の見積もりを見る
strata tune auto qwen/IQ3_S --mode thorough --plan
```

`target` はインストール済みモデル、保存済み profile 名、または run configuration JSON を指定します（`terminal/strata_cli/tune_commands.py:27`）。

## 値と既定値

- `quick` と `thorough` のみ受理されます。省略時は `quick` です（parser: `terminal/strata_cli/tune_commands.py:29-30`）。
- 不正値は `argparse` の選択肢検証で拒否され、コマンド処理に入りません（同 `:21-30`）。値の大文字小文字変換や別名は実装されていません。
- `quick` の予算は既定20分、候補スクリーニングは2ラウンド、追加確認ペアは0です。`thorough` は既定2時間、スクリーニング3ラウンド、追加確認は5ペアです（`terminal/strata_control/autotune.py:54-66,75-80`）。実行時間は候補数や各エンジン実行時間にも依存します。
- `--time MINUTES` が同時に指定され、値が truthy なら、その分数を予算秒数に変換して mode の既定予算を置き換えます（`terminal/strata_cli/tune_commands.py:41,342-344`）。`0` は未指定と同じ扱いになり、負数の拒否はこの引数処理では行われません。`--time` 自体の詳細は [同コマンドの `--time`](../auto/--time.md) を参照してください。

## 実行時の動作

`strata tune auto` は parser 値を `autotune.Options(mode=...)` に渡します（`terminal/strata_cli/tune_commands.py:342-345`）。チューナーは `Options.resolved()` で mode に応じた予算・ラウンド数・確認ペア数を確定します（`terminal/strata_control/autotune.py:75-80,201-205`）。候補数は残り予算と候補ごとの実行時間に応じて絞られ、`--plan` の場合は同じ mode の設定で開始せずに計画を表示します（`terminal/strata_control/autotune.py:437-444,856-866`）。

測定時、`thorough` はウォームアップを2回（quick は1回）行います。quick/thorough とも測定要求は5 decode、200 decode tokens です。`--use coding` と context が65536 tokens未満の組み合わせでは、thorough のみ長文測定も加わります（`terminal/strata_control/autotune.py:386-395`）。thorough で候補が勝ち、追加確認を行えるだけの予算が残っている場合、現在設定との5ペア確認を行います。確認で改善が保てなければ単独の勝者を採用するか、勝ちが一つだけなら変更なしに戻します（同 `:576-608`）。予算不足時は確認を省略します（同 `:590-594`）。

成功扱いの結果（`improved` / `default_confirmed`）は、`--no-save` がなければ preset として保存され、その `tuner.mode` に選択値が記録されます（`terminal/strata_cli/tune_commands.py:408-411`; `terminal/strata_control/presets.py:308-315`）。`--mode` は設定値自体を直接変更する指定ではなく、チューニング工程・計測・確認の条件を選びます。

## 適用条件と副作用

両 mode ともモデル設定を実測し、エンジンを複数回起動して比較します。`--plan` は計画表示のみでエンジンを開始しません（parser: `terminal/strata_cli/tune_commands.py:28`; 計画経路: 同 `:349-353`）。通常実行では結果に応じて preset が保存されるほか、試行記録とチューニングレポートも記録されます（同 `:403-420`）。`--no-save` を指定すると preset 保存は抑止されますが、試行記録・レポート保存の経路は別に実行されます。

## 出力とエラー

- `--plan` は選択 mode、推定実行回数・時間、試す候補と予算内に入らない候補を表示します（`terminal/strata_control/autotune.py:856-866`; 表示整形: `terminal/strata_cli/tune_commands.py:428-441`）。
- 通常実行の進捗は human 出力では標準エラーへ逐次出力され、結果は human 形式なら標準出力、`--output json` なら JSON として標準出力に出ます（`terminal/strata_cli/tune_commands.py:358-369,421-424`）。
- mode の不正値は parser の引数エラーです。target 解決やモデル適用可否などのエラーは human 時に `strata: ...` を標準エラーへ、JSON 時に失敗 JSON を標準出力へ出します（同 `:314-327`; `_fail` の出力分岐は同 `:109-115`）。エンジン起動失敗などチューニング結果の終了コードは個別の失敗経路に依存し、mode 固有の終了コードはありません（同 `:425`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:21-30` — `auto` parser と `--mode` の choices / 既定値。
- `terminal/strata_cli/tune_commands.py:41,314-345,349-353,358-369,408-425` — `--time` との組み合わせ、Options への受け渡し、計画・実行・保存・出力経路。
- `terminal/strata_control/autotune.py:54-80,201-205` — mode 別の既定予算、ラウンド、確認ペア。
- `terminal/strata_control/autotune.py:386-395,437-449,576-608` — mode による計測内容、候補計画と確認処理。
- `terminal/strata_control/autotune.py:856-866` — 計画表示で使う mode と予算。
- `terminal/strata_control/presets.py:308-315` — preset への mode の記録。

調査範囲はこの checkout の Strata 所有ソースです。実機での所要時間・速度向上は測定していません。
