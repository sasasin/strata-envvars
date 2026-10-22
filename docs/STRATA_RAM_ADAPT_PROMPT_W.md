# `STRATA_RAM_ADAPT_PROMPT_W`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--serve` の resident RAM 適応（`STRATA_RAM_ADAPT2`）で、プロンプト中に観測した expert routing を、後続 decode window の RAM resident expert 選択にどれだけ加味するかを指定します。GPU cache や routing 自体は変更せず、RAM に先読み・保持する expert 候補の順位に影響します。

## 値と判定

値は serve の初期化時に読み取られ、`std::atof` で数値変換した後、`std::max(0.0, 値)` で負値を 0 にします。設定がなければ `0.25` です。明示的な空文字列や数値として読めない文字列は `atof` により 0 となります。数値の後ろに文字がある場合も `atof` が変換できる先頭部分が使われます。上限 clamp はありません。

| 入力 | `prompt_w` |
|---|---:|
| unset | `0.25` |
| `0`、負数、空文字、数値に変換できない文字列 | `0` |
| 非負の数値 | その数値（上限なし） |

## 有効になる条件

- `STRATA_RAM_ADAPT2` が設定され、`atoi` の結果が 0 以外であること。空文字・数値に変換できない値は有効になりません。
- `prompt_w > 0` であること。この条件を満たすときだけ prompt routing callback が登録されます。
- prompt routing の seed が RAM の置換候補選択に使われるには、別途 `STRATA_RAM_ADAPT` の `atoi` 結果が正であり、resident RAM mode、適応層の usage table、単一 GPU、非 batch 等の window 処理条件も満たす必要があります。これらを満たさない場合、プロンプトから seed を集計しても、この経路で RAM の入れ替えは行われません。

## 実行時の詳細

serve 初期化時に `prompt_w` を読みます。`STRATA_RAM_ADAPT2` が有効で `prompt_w > 0` なら、prefill に layer ごとの routing callback を設定します。prefill は各 layer の prompt routing ID（`T * K` 個）を callback に渡し、各 routed expert に `prompt_w * 20 * n_expert_used / n` を seed として加算します。`n` はその callback に渡された ID 数です。範囲外の layer、空の ID 列、無効な expert ID は無視されます。

後続の RAM 適応 window では、decode の decayed usage にこの seed を足して RAM に入れる候補を評価します。各適応 window の選択処理で seed 全体を 0.95 倍するため、プロンプト routing の寄与は window ごとに減衰します。コードコメントは既定の `0.25` を「prompt の expert 1回を decode routing 約5回相当」と説明しています。実装上は上記の式で seed に加算されます。

この変数専用のログはありません。`STRATA_RAM_ADAPT2` が有効な場合、request 終了時に resident RAM の promotion 読み取り数・install 数・skip 数を stderr に出しますが、そこから prompt weight 単独の効果は判別できません。

## 根拠

- `src/program/generate.cpp:8267-8283` — `RamAdapt2` の既定値、`STRATA_RAM_ADAPT2` と本変数の読み取り・変換。
- `src/program/generate.cpp:10831-10842` — 正の weight の場合の callback 登録、prompt routing ID から seed への加算式。
- `src/prefill/prefill.cpp:3741-3747` — layer の prompt routing ID を callback に渡す箇所。
- `src/program/generate.cpp:14801-14815,14820-14830` — `STRATA_RAM_ADAPT` などの window 条件、seed の減衰と候補 usage への加算。
- `src/program/generate.cpp:15368-15372` — `STRATA_RAM_ADAPT2` の累積結果ログ。
