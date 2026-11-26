# `STRATA_SPLIT_NEAR_TIE_PCT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--layer-split auto` の探索で採用済みの分割に近い、別の分割候補を「NEAR TIE」として案内する許容率（百分率）です。候補の絞り込みと案内ログだけに使われ、最良候補の選択、実際に使う分割、生成結果はこの値では変わりません。採用分割 `best` を `split_at` に設定した後に別候補を調べる処理です（`engine/src/program/generate.cpp:7510-7518,7525-7545`）。

この参照は `multi_gpu && split_auto` の自動探索ブロック内にあります。手動 `--layer-split K,...` ではこの探索に入らず、この設定による案内もありません（`engine/src/program/generate.cpp:6959`）。同名の実行コード参照はこの箇所だけです。設定登録データにも候補名がありますが、実行時の挙動の根拠にはしていません。

## 値と判定

コードは `getenv` が null かどうかで未設定を判定し、設定されていれば `std::atof` で `double` に変換します。変換後の値を `near_pct > 0` で判定し、正の値だけが別候補の閾値計算に進みます。文字列全体の検証、範囲制限、clamp、警告はありません（`engine/src/program/generate.cpp:7525-7526`）。

| 条件 | 判定値 | この設定による動作 |
| --- | ---: | --- |
| 未設定 | `4.0` | 別候補が最良候補の予測時間の 4% 以内なら案内対象になり得る |
| 空文字 | `atof("")` → `0` | 案内を無効化 |
| 数値文字列が正の値 | 変換された値 | その百分率以内の別候補を探す。例: `1`, `4`, `10`, `0.5` |
| `0` または負の値 | 0 以下 | 案内を無効化 |
| 数値として読めない文字列 | `atof` の変換結果は `0` | 案内を無効化。無効値としてのエラーや fallback ログはない |
| 数値の後ろに文字がある文字列 | `atof` が読めた先頭部分の値 | 先頭部分が正ならその値で判定。例: `4anything` は `4` として扱われる |

`atof` の結果に全体 parse の成否確認はありません。したがって `true` のような数値で始まらない文字列や、空白だけの文字列は 0 となります。比較は大小文字を調べる文字列比較ではありません（`engine/src/program/generate.cpp:7525-7526`）。

## 有効になる条件

- 複数 GPU の `--layer-split auto` の探索が実行され、探索で有効な最良候補が得られること（`engine/src/program/generate.cpp:6959,7501-7515`）。
- 各段の予測レイヤー時間またはリンクのミスコスト倍率に 10% を超える差があること（`hi > lo * 1.10 || lhi > llo * 1.10`）。差がなければこの設定値にかかわらず案内探索をしません（`engine/src/program/generate.cpp:7520-7526`）。
- 変換値が正、GPU 段数 `ns` が 3 以下、最良候補の予測時間が正で、価格付け済み候補が存在すること（同上）。したがってこの案内探索は最大 3 GPU（2 または 3 段）に限られます。
- 別候補は最良候補の `best_ms * (1 + near_pct / 100)` 以下の予測時間でなければなりません。境界と等しい候補は閾値内です。さらに、既に見つかった別候補より時間が小さく、分割境界の最大距離が 3 層以上であり、開始可能性ゲートが有効ならその候補も開始可能である必要があります（`engine/src/program/generate.cpp:7529-7537`）。
- `STRATA_SPLIT_NEAR_TIE_PCT` を上書きする CLI 引数や別環境変数は、この設定の直接参照箇所にはありません。`--layer-split` は探索経路を選びますが、この百分率を指定する引数ではありません（`engine/src/program/generate.cpp:4805-4854,7525`）。

## 実行時の詳細

自動 split の探索で候補を価格付けし、最良候補を決めて `split_at = best` に設定した後、近い候補のログを出すために読みます。最良候補はそれ以前に探索内で選択済みであり、この値は `consider()` の比較処理では参照されません（`engine/src/program/generate.cpp:7253-7269,7510-7526`）。

関数内 `static` への保存はなく、設定値はこの案内ブロックを通るたびに取得されます。起動後にプロセスの環境を外部から変更して反映させる処理や、子プロセスへの転送処理はこの変数の参照箇所にはありません（`engine/src/program/generate.cpp:7525`）。

条件を満たす別候補が見つかった場合に限り、stderr に次の形式で案内します。候補がない、値が 0 以下、段数が 3 を超える、または段・リンクの差が 10% 以下などの場合、この NEAR TIE 行は出ません。値の parse 失敗自体も別のログや終了コードを発生させません（`engine/src/program/generate.cpp:7526-7547`）。

```text
strata generate: layer split auto: NEAR TIE - K=... is predicted ... ms per decode window, within ...% of K=... (... ms); the cards differ, so the prediction may not rank them (it prices decode, not the prompt). To try the other: --layer-split ...
```

案内対象がなくても自動 split の開始処理はこの設定を理由に失敗しません。この設定による終了・timeout・警告経路はありません。

## 根拠

- `engine/src/program/generate.cpp:6959` — 複数 GPU かつ自動 split の探索ブロック。
- `engine/src/program/generate.cpp:7253-7269` — 価格付け候補と最良分割の選択。
- `engine/src/program/generate.cpp:7510-7547` — 最良候補決定後の環境変数読み取り、候補条件、stderr 案内。
- `engine/src/program/generate.cpp:4805-4854` — `--layer-split auto` の分岐と手動 split の区別。
