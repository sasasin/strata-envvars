# `strata tune auto --use`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--use` |
| 別名 | なし |
| 値 | `chat` または `coding` |

## 役割

自動チューニングで各設定を比較する評価軸を選びます。`chat` は主に生成速度（decode）を比較し、`coding` は生成速度に加えて長い入力の処理速度も評価します。チューニング結果を保存する場合、この値はプリセットの対象選択にも記録されます。

## 使い方

```sh
# 生成速度を主に評価する（既定値）
strata tune auto qwen/IQ3_S

# 生成と長文入力の速度を評価する
strata tune auto qwen/IQ3_S --use coding
```

`target` にはインストール済みモデル、保存済み profile、または run configuration の JSON を指定します。

## 値と既定値

- `chat` と `coding` のみを受け付けます。省略時は `chat` です。別名はありません（`terminal/strata_cli/tune_commands.py:21-35`）。
- これら以外の値は parser の `choices` により拒否されます。値の追加 validation や補正は `auto()` 内にはありません（`terminal/strata_cli/tune_commands.py:34`）。

## 実行時の動作

- `auto()` は選択値を `autotune.Options.use` に渡し、チューナーが baseline と候補設定を評価するときの `metric()` に使います（`terminal/strata_cli/tune_commands.py:342-345`; `terminal/strata_control/autotune.py:418-421,504-505`）。
- `chat` の評価値は decode tokens/sec です。`coding` は decode と prompt tokens/sec の幾何平均を使い、長文 prompt の測定値がない場合は通常の prompt 測定値にフォールバックします。ただし `--concurrency` により `load_tok_s` が記録される測定では、`coding` の幾何平均より先に同時処理全体の `load_tok_s` が評価値になります（`terminal/strata_control/autotune.py:146-162`）。
- 長文 prompt を測る条件は別に決まります。コンテキストが 65,536 token 以上ならモードにかかわらず長文 prompt を設定します。未満の場合は `coding` かつ `--mode thorough` のときに限り、最大 28,000 token（コンテキストの 80% まで）を測定します。これ以外は長文 prompt の測定を設定しません（`terminal/strata_control/autotune.py:386-395`）。
- 候補設定の適用条件にも `use` が伝わります。例えば prompt chunk 候補は長文 prompt がある場合に対象となり、`coding` ならコンテキスト長が 65,536 未満でも条件を満たし得ます（`terminal/strata_control/tune_knobs.py:88-89,232`）。
- チューニング完了後、`choices_from_config(cfg, use=a.use)` で選択値を含む対象情報を作り、結果が改善したか既定値確認となり、かつ `--no-save` がない場合にプリセットを保存します（`terminal/strata_cli/tune_commands.py:396-410`; `terminal/strata_control/presets.py:89-116`）。したがって `chat` と `coding` は別の preset slot になります。

## 適用条件と副作用

- このオプションは `strata tune auto` の測定・候補選択を変えます。モデル起動時の推論方式を coding モードに切り替える指定ではありません。
- 通常の保存プリセット照合は `presets.overlay()` の既定値 `use="chat"` で行われます。Terminal と server の起動経路はいずれも `overlay(cfg)` を呼び、`--use coding` は渡しません。そのため coding 用 slot に保存されたプリセットは通常の起動時照合（chat slot）には一致しません（`terminal/strata_control/presets.py:488-502`; `terminal/serve/server_parts/http_api.py:486-496`; `terminal/strata_cli/tune_commands.py:544-550`）。
- 値自体によるファイル・ネットワーク・GPU の直接操作はありませんが、`strata tune auto` は実際に基準設定と候補を起動して測定し、結果が保存条件を満たせばプリセットを作成します（`terminal/strata_cli/tune_commands.py:355-387,408-410`）。測定を開始せず候補計画だけを見る場合は `--plan` を併用できます（`terminal/strata_cli/tune_commands.py:349-353`）。

## 出力とエラー

- `--use` の値に対する固有のエラー処理はありません。許可外の値は parser の choices 制約で拒否されます（`terminal/strata_cli/tune_commands.py:34`）。
- チューニング結果は通常、人間向け表示または `--output json` の JSON で出力されます。`--use` は成功時の出力形式を変更しません（`terminal/strata_cli/tune_commands.py:314,421-425`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:21-50` — `strata tune auto` parser と `--use` の choices / 既定値。
- `terminal/strata_cli/tune_commands.py:309-345,396-410` — option を tuner と preset choices に渡す経路。
- `terminal/strata_control/autotune.py:146-162,386-395,418-421` — 評価式、長文 prompt 条件、評価関数の使用箇所。
- `terminal/strata_control/tune_knobs.py:88-89,232` — coding 選択による候補条件。
- `terminal/strata_control/presets.py:89-116,488-502` — preset slot の選択値と overlay の既定値。
- `terminal/serve/server_parts/http_api.py:486-496` — 起動時の保存 tuning 照合経路。
