# `strata tune auto --allow-not-repeatable`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--allow-not-repeatable` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。指定すると有効。 |

## 役割

通常は自動選択しない「回答が実行ごとに再現しない」設定クラスを、チューナーの候補に含める許可フラグです。候補を必ず採用する指定ではなく、候補計画で条件を満たした設定が測定され、通常の比較で改善と判定された場合にのみ結果へ反映されます。

## 使い方

```sh
# IQ3_S がインストール済みの環境で、測定を始めず候補計画だけを見る
strata tune auto IQ3_S --allow-not-repeatable --plan

# 同じモデルを測定し、通常の結果判定に従って設定する
strata tune auto IQ3_S --allow-not-repeatable
```

## 値と既定値

値は不要で、未指定時は無効です。parser は `argparse` の `store_true` として登録しており、このフラグ固有の追加 validation はありません。`=true` のような値は受け付けず、余分な引数として CLI の parser エラーになります。CLI は未処理引数を `ap.error(...)` に渡します（`terminal/strata_cli/cli.py:2325-2334`）。

## 実行時の動作

CLI はこの値を `autotune.Options.allow_nonrepeatable` に渡し、実行環境から作る候補計画コンテキストへコピーします（`terminal/strata_cli/tune_commands.py:342-345`、`terminal/strata_control/autotune.py:926-932`）。候補計画は設定の回答クラスが `nonrepeatable` の場合、この許可があると候補を通します。許可がなければ「回答が実行ごとに再現しないため試さない」という理由で計画から除外します（`terminal/strata_control/tune_knobs.py:375-378,445-449`）。

現行の候補表で `nonrepeatable` と分類されている候補は、CUDA の resident-RAM 条件かつ1 GPU 以下のときの `adapt_async`（エンジン引数 `--adapt-async 1`）です（`terminal/strata_control/tune_knobs.py:83-95,216-220`）。この候補は `flash-next` 系に属し、RAM 常駐条件が候補の必要条件です。機種クラス A はその条件、またはモデルとシステム RAM の差が12 GiB未満の場合に割り当てられますが、後者だけで resident-RAM 条件を満たさない場合、この候補自体は追加されません（`terminal/strata_control/tune_knobs.py:236-249,450-453`）。現在のエンジンが引数を受け付けない場合や、既に同じ設定の場合も候補から外れます（同 `:465-475`）。

このフラグは `--allow-small-differences` とは別の許可です。後者は `placement` クラスを許可し、このフラグは `nonrepeatable` クラスを許可します。どちらも `quality` クラスを許可しません（`terminal/strata_cli/tune_commands.py:37-39`、`terminal/strata_control/tune_knobs.py:375-378`）。`--plan` と併用した場合は許可後の候補計画を表示しますが、測定を開始しません（`terminal/strata_cli/tune_commands.py:349-353`）。

## 適用条件と副作用

このオプション単体は候補の許可だけを変えます。実測時はチューナーが基準設定と候補設定をエンジンで測定します。設定が改善または既定設定と確認され、`--no-save` が指定されていない場合にプリセットが作成されます（`terminal/strata_cli/tune_commands.py:383-387,408-412`）。測定のためのエンジン起動、進捗表示、チューニング報告の保存などはコマンド実行に伴うもので、この許可フラグだけを指定した場合に発生する副作用ではありません（同 `:358-374,417-424`）。

## 出力とエラー

人間向け実行では進捗を標準エラーへ出し、結果を標準出力へ表示します。`--output json` の場合は結果 JSON を標準出力へ出します（`terminal/strata_cli/tune_commands.py:358-369,421-424`）。候補が対象外なら、通常の計画・結果にその候補を試さない理由が示され、他候補のチューニングは続行できます（`terminal/strata_control/tune_knobs.py:445-452`）。このフラグ専用の実行時エラー経路は確認できません。値を付けた場合など構文エラーでは CLI の argparse parser がエラーを処理します（`terminal/strata_cli/cli.py:2325-2334`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:21-40` — `strata tune auto` の位置引数、対象フラグの parser 定義、値を取らない `store_true` と既定値。
- `terminal/strata_cli/tune_commands.py:342-353` — フラグから tuner option への受け渡しと `--plan` の分岐。
- `terminal/strata_control/autotune.py:54-81,926-932` — tuner option の既定値と候補コンテキストへの伝播。
- `terminal/strata_control/tune_knobs.py:83-95,216-249,375-378,415-475` — `adapt_async` の分類、機種条件、許可判定、候補の追加・除外条件。
- `terminal/strata_cli/tune_commands.py:358-369,383-424` — 進捗・結果の出力、測定後のプリセット保存条件。
- `terminal/strata_cli/cli.py:2325-2334` — parser と未処理引数のエラー経路。
