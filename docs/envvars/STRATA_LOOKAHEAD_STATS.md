# `STRATA_LOOKAHEAD_STATS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

ルーター先読み予測を起動し、各層で実際に GPU キャッシュ外へ回った expert と予測を照合して、予測の再現率・適合率などを stderr に集計します。CUDA/HIP の `generate` 経路で使われます。SYCL 側にはこの変数の読み取りや統計機能の実装がありません。

「measurement only」というコメントがありますが、設定を有効にすると予測スレッドは統計計算に加えて通常の `ExpertSource::warm()` も呼びます。したがって、実行時間の計測をしたい場合はこの変数を有効にした実行を通常動作の性能測定と見なせません。予測はどの expert を計算するかを変更しません。

## 値と判定

環境変数の値を `std::atoi(v) != 0` で判定します。未設定は無効です。`atoi` は文字列全体の妥当性検査をしないため、先頭の空白と符号に続く十進整数を変換し、その後ろの文字列は無視します。数値に変換できない先頭（空文字、`true` など）は 0 となり無効です。

| 値の例 | 結果 |
|---|---|
| 未設定、`0`、`00`、`0suffix` | 無効 |
| `1`、`-1`、`2`、` 1x` | 有効 |
| 空文字、`true`、`x1` | 無効 |

整数範囲外の入力に対する `atoi` の結果は C/C++ の仕様上保証されません。値の上下限や clamp はありません。

根拠: `src/program/generate.cpp:5496-5499`。

## 有効になる条件

- `srcp` が存在する expert source を使う経路であること。
- `STRATA_LOOKAHEAD` が未設定または `atoi(value) != 0` であること。`STRATA_LOOKAHEAD=0`（および `atoi` が 0 になる値）は、統計を要求していても先読み全体を止めます。
- 各層の `ffn_gate_inp.weight` が arena 内の BF16 ルーターとして見つかり、形状が `(n_expert * n_embd)`、デバイスからホストへのコピーが成功すること。
- `RouterLookahead::start()` の検査（`src` が存在すること、`n_embd` が 8 の倍数、各ルーターの形状一致）とスレッド起動が成功すること。

通常の file source 先読み条件 `src == &src && src.warms()` が成立しない source でも、`STRATA_LOOKAHEAD_STATS` が有効なら予測器の起動を試みます。このとき `start()` に cold source の許可を渡します。起動条件を満たさない場合は統計は有効にならず、stderr に `strata generate: routing-aware prefetch off (...)` が出ます。起動できた場合は `strata generate: routing-aware prefetch on (...)` が出ます。

根拠: `src/program/generate.cpp:5491-5524`、`src/core/expert_source.cpp:2183-2199`。

## 実行時の詳細

値は `generate` の source 初期化後に一度読み、ローカルの `la_stats` に保持します。この判定は `static` キャッシュではありませんが、起動後に環境を書き換えても現在の `generate` 実行では再評価されません。

有効時は `RouterLookahead` が各 verify window の CPU expert dispatch から次層の予測を非同期に受け取ります。ルーター dot product を CPU で計算し、各 token の top `k`、`k+4`、`k+10`（expert 数で上限）を記録します。`k` は `STRATA_LOOKAHEAD_K` で、未設定時 10 です。統計用にさらに各 token の top `k` に選ばれた非 resident expert の投票順位 top 4 / 8 / 12 も数えます。予測 thread は通常の top `k` について `src_->warm()` を呼び、Foresight swap が接続されている場合は予測をそこにも渡します。

実際の dispatch では GPU キャッシュにある expert を除外した routing expert 集合を予測集合と照合します。層あたりの実際の非 resident expert 数、top `k` / `k+4` / `k+10` の recall・precision、投票 top 4 / 8 / 12 の miss と PCIe share のカバー率、および predictor thread の累積時間を計算します。最後の層の予測まで得られた window を数え、100 window ごとに `strata lookahead stats:` の行を stderr に出します。予測が間に合わない場合、その層は「without a prediction」に数えられます。

統計収集のため predictor は `k+10` まで partial sort するので CPU 負荷があります。一方、実際に `warm()` へ渡すのは top `k` の非 resident expert のみで、統計用の拡張候補や投票順位によって計算対象 expert は変わりません。ログは診断情報であり、環境変数自体が stdout の生成結果を出力するものではありません。

根拠: `src/core/expert_source.cpp:2202-2215,2217-2309,2312-2412`、`src/core/expert_source.cpp:3624-3639`。

## 文書との照合

`docs/DETAILS.md:308-312` は、任意の expert tier で予測を走らせ、次層の routing と照合して100 windowごとに統計を出す診断機能と説明しています。ソースもこの集計・出力を実装しています。ただしコード上では、予測スレッドが `warm()`（および接続時の Foresight swap への予測）を行うため、実行中に先読み処理自体も動きます。資料にある「measurement only」は計算対象を変えないという意味で読むのが適切です。資料に性能値はなく、本調査でも測定していません。
