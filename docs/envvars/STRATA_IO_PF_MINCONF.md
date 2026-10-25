# `STRATA_IO_PF_MINCONF`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Linux の file-tier I/O prefetch で、router が次の層向けに予測した expert を先読みキューへ採用するための最低 confidence を設定します。環境変数単独では作用せず、I/O prefetch とスケジューラが有効な場合に限り候補採否に使われます。通常の需要読み込みや expert の選択結果は変更しません。

## 値と判定

値は `std::atof` で `double` に変換し、`std::clamp(..., 0.0, 1.0)` で 0〜1 に制限した後、`float` に保存します。文字列全体の厳密な数値検証はありません。

| 設定 | `io_minconf_` |
|---|---:|
| 未設定 | 既定値 `0.5` のまま |
| 空文字 | `atof("")` の結果 0 により `0` |
| 数値が 0 未満 | `0` に clamp |
| 数値が 0〜1 | 変換した値 |
| 数値が 1 より大きい | `1` に clamp |
| 数値として読めない文字列 | `atof` の結果 0 |

`atof` は先頭から数値として読める部分を変換するため、たとえば `0.7tail` は `0.7` になります。値の読み取りは `FileExpertSource::set_io_prefetch()` が Linux で prefetch を開始するときに行われます。設定の実行中変更を再読するコードはありません。

## 有効になる条件

- Linux ビルドであること。非 Linux では `set_io_prefetch()` の処理本体がありません。
- `STRATA_IO_PREFETCH` が有効、または Linux の file-tier 既定条件で prefetch が開始されること。
- `FileExpertSource` に mmap base とファイル path があり、unbuffered (`direct_`) 読み込みではないこと。
- `STRATA_IO_PF_SCHED` が設定され、`atoi` の結果が 0 以外であること。未設定・空文字・数値変換できない文字列はスケジューラ OFF です。
- 予測先読み側でも、ahead 読み込みが有効で decode gate が開いていること。閉じている場合や `STRATA_IO_PF_AHEAD=0` の場合は、`warm_scored()` は通常の `warm()` に fallback します。

`STRATA_IO_PF_MINCONF` が設定されても scheduler が OFF なら confidence 閾値として使われません。Linux 以外、unbuffered 読み込み、または file mapping 条件を満たさず prefetch 自体が起動しない場合も適用されません。

## 実行時の詳細

Router lookahead は token ごとの router logits から上位 `k_` expert を予測します。0 始まりの順位 `j` に対する候補 confidence は `(k_ - j) / k_` で、1 層より先の候補では層の距離 `dj` に応じてさらに `0.5^dj` 倍します。同じ expert が複数 token から候補になった場合は最大 confidence を渡します。

スケジューラが有効な `warm_scored()` は、候補ごとに次の閾値を計算します。

`bar = io_minconf_ + (1 - io_minconf_) * min(1, io_q_bytes_ / max(1, budget))`

キューの未開始 job が予算に対して少ないときは設定値が閾値になり、キューが予算まで詰まると閾値は 1 まで上がります。候補 confidence が `bar` 未満なら採用せず、confidence が閾値以上でも、その decode window の先読み byte budget を超える候補は別途拒否されます。resident RAM copy に存在する expert、重複 job、範囲外 ID も先読み候補から除かれます。未開始 job は layer clock による deadline を持ち、期限までに始まらなければ worker が落とします。

スケジューラが有効な場合は起動時に stderr に `strata generate: io prefetch scheduling ON (STRATA_IO_PF_SCHED=1): a deadline per read, confidence admission (STRATA_IO_PF_MINCONF), a per-window byte budget (STRATA_IO_PF_BUDGET_MB / _FRAC)` と出ます。このログは設定値そのものや個々の confidence を表示しません。拒否数の内部カウンターはありますが、この環境変数専用のログは確認できません。

## 文書との照合

`docs/DETAILS.md` は Linux file-tier prefetch が router 予測 expert を I/O thread で先読みする経路や、page-cache 条件、性能測定条件を説明していますが、`STRATA_IO_PF_MINCONF` の既定値や具体的な値域は記載していません。本書の閾値・clamp の説明は対象 HEAD のソースを根拠とする静的調査です。性能効果はこの変数単独では測定していません。

## 根拠

- `include/strata/core/expert_source.hpp:280-286, 928, 1148-1150` — score 付き warm の API、score 要求条件、既定値。
- `src/core/expert_source.cpp:1045-1053, 1078-1112, 1144-1155` — budget、confidence 閾値と候補採用、環境変数の parse/clamp。
- `src/core/expert_source.cpp:3153-3182, 3216-3231, 3261-3262` — router 予測の confidence 生成と `warm_scored()` 呼び出し。
- `src/program/generate.cpp:5655-5690` — Linux file-tier prefetch の開始条件とスケジューラ有効ログ。
- `docs/DETAILS.md:300-307` — Linux file-tier I/O prefetch の概要。
