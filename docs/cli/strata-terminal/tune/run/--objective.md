# `strata tune run --objective`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--objective` |
| 別名 | なし |
| 値 | `generation`、`prefill`、`latency` のいずれか。省略時は `generation` |

## 役割

測定したベースラインと候補設定を何の指標で比較し、どの方向を改善として扱うかを選びます。`generation` は生成速度、`prefill` は prompt 処理速度、`latency` は TTFT（最初の token までの時間）を目的指標にします。これは調査対象の Terminal CLI の `strata tune run` の option です。同名 option は `strata tune plan` にもありますが、そちらは別コマンドスコープです（`strata_cli/cli.py:398-420`）。

## 使い方

```sh
strata tune run --engine /path/to/strata --backend cuda --model example-model \
  --objective prefill
```

`--engine`、`--backend`、`--model` はこのコマンドで必須です。上記のパスとモデル名は形式例であり、実在する engine や model の存在を保証しません（`strata_cli/cli.py:414-420`）。

## 値と既定値

- parser は `generation`、`prefill`、`latency` のみを受理し、省略時は `generation` を設定します。短縮 alias はありません（`strata_cli/cli.py:419-420`）。
- 未知の値は `argparse` の選択肢エラーになります。トップレベルの parser は不明な引数を `ap.error(...)` に渡すため、通常は usage とエラーを stderr に出して終了コード 2 になります（`strata_cli/cli.py:2217-2227`）。
- option 自体に対する追加の数値範囲検証はありません。

## 実行時の動作

`strata tune run` は engine の存在を確認し、workload・上限・hold 指定などとともに値を `tuning.plan_tuning` に渡します。通常の protocol 測定では `tokens_per_s` は prompt と decode の合計時間に対する生成 token 速度、`prefill_tokens_per_s` は prompt 処理速度、`ttft_ms` は prompt 処理時間と最初の decode step の時間を足した値です（`strata_cli/cli.py:1759-1768`、`strata_control/tune_engine.py:188-208`）。

目的値と改善方向の対応は次のとおりです（`strata_control/tuning.py:594-595,716-718`）。

| 値 | 比較指標 | 改善方向 |
| --- | --- | --- |
| `generation` | `tokens_per_s` | 大きい方 |
| `prefill` | `prefill_tokens_per_s` | 大きい方 |
| `latency` | `ttft_ms` | 小さい方 |

候補は測定を通過し、少なくとも `--repeats` 回の metric を持つ必要があります。コード上はベースラインの中央値より目的指標の中央値が改善した候補だけを推薦し、候補の値がベースラインの `worst` を下回る／上回る（目的による）場合は除外します。推薦が得られなければ「変更なし」となります（`strata_control/tuning.py:586-624`）。

測定結果は `tuning.Tuner` が job report に含め、`--output json` では JSON として返します。人向け出力では objective、推薦内容、推薦なしの理由などを表示します（`strata_cli/cli.py:1802-1806,1832-1846`）。

## 適用条件と副作用

- 既定の `--mode protocol` では engine 自身の serve protocol を測定します。HTTP API を通した利用者の待ち時間とは異なるため、protocol の推薦は `--mode api` で確認するよう実装が案内します（`strata_cli/cli.py:431-434,1785-1786,1840-1845`）。API mode では `--config` と `--api-expect` が必須で、不足時はエラーコード 2 を返します（`strata_cli/cli.py:1771-1779`）。API mode の TTFT は HTTP worker の最初の token までの経過時間です（`strata_control/tune_api.py:237-250`）。
- option は測定目標を変えますが、設定を自動適用しません。run は job 結果を記録し、active profile は変更せず、適用は別途 `strata tune apply <job>` を実行する設計です（`strata_cli/cli.py:1742-1756,1845-1846`）。
- 省略時の state 保存先は `--state-dir`、`STRATA_TUNE_DIR`、ユーザー state 配下の tuning directory の順で決まります。job ディレクトリに JSON state を作成し、比較可能な identity があれば履歴も記録します（`strata_cli/cli.py:1643-1650,1708-1709`、`strata_control/tuning.py:333-359,674-706`）。
- API mode の correctness expectation は回答（回答がなければ reasoning）への正規表現照合です。不一致は測定失敗になり、回答がない場合や completion token 数が得られない場合も測定されません（`strata_control/tune_api.py:215-232`）。
- 調査した比較実装には注意点があります。`Candidate.worst(metric)` は指標の種類にかかわらず測定値の**最小値**を返します（`strata_control/tuning.py:252-257`）。一方、latency は小さい方が良いとして推薦フィルターがこの値を「worst」と比較します（同 `:600-615`）。そのため latency の「最悪測定値」は最大遅延ではなく最小遅延であり、意図したリスク判定かはソースから確認できません。`--objective latency` の推薦判断ではこの実装上の制約を考慮してください。

## 出力とエラー

- `--engine` で解決された engine ファイルが存在しない場合、human 出力では stderr に `strata: no engine binary at ...`、JSON 出力では `ok: false` のエラー object を出し、終了コード 2 を返します（`strata_cli/cli.py:1759-1762,527-532`）。
- 誤った objective 値や不足した必須 option は parser が拒否します。job 中に測定できない候補は個別の失敗として report に保持され、候補推薦から除外されます。job 実行時の例外は job state `failed` として記録されます（`strata_control/tuning.py:477-482,486-523`）。
- `--objective` それ自体に固有の警告や追加出力はありません。結果の表示形式は `--output human|json` に従います（`strata_cli/cli.py:459,1805-1846`）。

## 根拠

- parser 定義、値の選択肢、既定値: `strata_cli/cli.py:414-420`
- run の option 受け渡しと mode 条件: `strata_cli/cli.py:1759-1786`
- objective 指標、改善方向、推薦条件: `strata_control/tuning.py:586-624,716-718`
- protocol 側の生成速度、prefill、TTFT の算出: `strata_control/tune_engine.py:188-208`
- latency 比較における `worst` の実装: `strata_control/tuning.py:252-257,600-615`
- API 測定値と回答検証: `strata_control/tune_api.py:215-250`
- help 出力は実行していません。parser と実行経路を同一 revision のソースで確認しました。
