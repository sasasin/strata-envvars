# `STRATA_ADAPT_MID`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

VRAM の expert cache が routed expert 総数の 15% 以上 65% 以下を保持するとき、適応型 cache の既定値を `--adapt-every 2`、`--adapt-swaps 192`、`--adapt-decay 0.92` に切り替えるかを制御する。`STRATA_ADAPT_MID="1"` はこの範囲の設定を有効にし、`"0"` は無効にする。値がそれ以外なら build 既定に従う。ルールは `adapt_mid_coverage_enabled` / `adapt_mid_coverage_applies` にあり、generate の初期化、serve、非 serve decode の各経路から参照される（`engine/include/strata/core/adapt_coverage_rules.hpp:20-39`、`engine/src/program/generate.cpp:12145-12164`, `14943-14964`, `24558-24568`）。

`STRATA_USE_HIP` が定義された build では既定で無効、定義されない build では有効。実装の条件は HIP macro の有無であり、ソースコメントでは CUDA / HIP の既定値として説明されている（`engine/include/strata/core/adapt_coverage_rules.hpp:20-27`）。

## 値と判定

`std::getenv` の結果を文字列全体で比較する。NUL 終端を含めて厳密に 1 文字の `"1"` なら有効、厳密に `"0"` なら無効。それ以外は値を解釈せず build 既定値を使う。したがって空文字、`"01"`、`"11"`、`"1x"`、`"true"`、`"false"`、大文字、前後に空白を含む値、数値でない値はすべて既定値扱いであり、警告やエラーにはならない（`engine/include/strata/core/adapt_coverage_rules.hpp:29-34`）。

| build / 値 | 未設定 | 有効になる値 | 無効になる値 | その他の値 |
|---|---|---|---|---|
| `STRATA_USE_HIP` 定義 | 無効 | `"1"` | `"0"` | HIP 既定の無効 |
| `STRATA_USE_HIP` 未定義 | 有効 | `"1"` | `"0"` | 非 HIP 既定の有効 |

空文字は「未設定」ではなく設定済みの空文字だが、文字列比較には一致しないため既定値に戻る。設定値の数値変換や範囲 clamp はない（同 `:29-34`）。

## 有効になる条件

- routed expert の総数 `n_layers * n_expert` が正で、GPU cache の live slot 数が 0 より大きく総数未満であること。coverage は `live_slots / total_pairs` で計算し、15% と 65% の両端を含む（`engine/src/program/generate.cpp:12148-12153`, `14948-14954`, `24559-24564`、`engine/include/strata/core/adapt_coverage_rules.hpp:17-18,36-39`）。
- 適応型 tier が動作可能であること。generate 初期化と非 serve decode では `o.adapt_every > 0` かつ `o.adapt_swaps > 0` が必要。serve ではこれらに加えて全 expert が GPU 常駐でないことが条件となる（`engine/src/program/generate.cpp:12152-12153`, `14953-14954`, `24563-24564`）。
- 変数が mid-coverage の既定値を許可しても、明示した CLI 値は個別に維持される。`--adapt-every`、`--adapt-swaps`、`--adapt-decay` のうち指定されていない項目だけがそれぞれ 2、192、0.92 に変更される。たとえば `--adapt-every 0` または `--adapt-swaps 0` は tier を止める条件を満たす。明示した正の値はその項目の既定値変更を抑止するが、他の未指定項目への変更は抑止しない（`engine/src/program/generate.cpp:1047-1053,1084,4058-4059,4202,12152-12158,14953-14959,24563-24567`）。
- cache coverage が範囲外、cache が空または全 expert 常駐、あるいは適応型 tier が無効なら、この変数による既定値変更は実行されない。serve で coverage が 15% 未満の場合は別の `STRATA_TINY_CACHE` 分岐があり得るが、これは本変数の処理ではない（同 `:14953-14972`）。

## 実行時の詳細

環境値は設定構造体の静的 cache には保存されず、各適用経路が coverage を算出する時点で `std::getenv("STRATA_ADAPT_MID")` を呼び、その場で判定する。読み取り箇所は generate 初期化、serve、非 serve decode の3箇所で、いずれも `engine/src/program/generate.cpp` にある（`:12148-12158`, `14948-14959`, `24559-24567`）。これらの初期化処理後にプロセス環境を変更しても、既に `o` に反映された値は再計算されない。

mid-coverage が適用されると、未指定の interval / swap 数 / decay をそれぞれ `2 / 192 / 0.92` にし、後続の適応 tier がこの値を使用する。serve の batch loop は `o.adapt_every` ごとの窓で適応を開始し、usage が空でない場合にのみ実行する（`engine/src/program/generate.cpp:15001-15002,17245-17259`）。非 serve decode も設定適用後、適応 tier が有効なら usage 配列を初期化する（同 `:24563-24570`）。

## ログと測定値

generate 初期化と serve では、値の変更が一つ以上あれば stderr に次の形式の行を出す。3項目すべてが明示値のまま、または変更前から同じ値ならこの行は出ない。

```text
strata generate: #4870 mid-coverage expert cache (%lld of %lld slots, %.1f%%): adaptive defaults every %d -> %d, swaps %d -> %d, decay %.2f -> %.2f
strata serve: #4870 mid-coverage expert cache (%lld of %lld slots, %.1f%%): adaptive defaults every %d -> %d, swaps %d -> %d, decay %.2f -> %.2f
```

それぞれの実装文字列は `engine/src/program/generate.cpp:12159-12163` と `14960-14964` にある。非 serve decode の `24563-24568` にはこの設定変更のログ出力がない。無効値の警告や失敗経路もない。以下の測定は実装コードの保証ではなく、ソースコメントに記録された比較結果である。

実装ヘッダーの測定コメントは、旧3値を明示した同一 binary との比較として次を報告している。CUDA は RTX A4000 (sm_86)、IQ2_XS、30% coverage、3 rounds で code +5.7%、chat +6.7%、8K document +9.0%。HIP は RX 7900 XT (gfx1100)、同じ pack、18.8% coverage で chat 512 tokens -7.8%、agent -7.8%、code -2.8% / -4.2%、8K document +2.8%。32.5% では 8K document -4.8%、code -3.6%、chat / agent +0.4% / +0.3%。46.8% では chat -0.2%、code -1.5%、8K document -2.0%。コメントの方法は各 arm・各 round で engine を1回起動し、arm を交互に実行、greedy。これらはコメントが記載する測定であり、今回の調査で再測定した値ではない（`engine/include/strata/core/adapt_coverage_rules.hpp:3-10`）。

## 根拠

- `engine/include/strata/core/adapt_coverage_rules.hpp:17-39` — coverage 境界、build 既定値、厳密な文字列判定。
- `engine/src/program/generate.cpp:1047-1053,1084,4058-4059,4202` — CLI の初期値、指定フラグ、解析。
- `engine/src/program/generate.cpp:12145-12164` — generate 初期化の適用条件、CLI 優先、ログ。
- `engine/src/program/generate.cpp:14943-14972` — serve の適用条件、CLI 優先、ログ、および別の tiny-cache 分岐。
- `engine/src/program/generate.cpp:17245-17259,24558-24570` — serve loop と非 serve decode での後続使用。
