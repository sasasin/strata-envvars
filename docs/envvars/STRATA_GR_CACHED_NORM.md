# `STRATA_GR_CACHED_NORM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL の fused hyper-connection read で、正規化済み入力を up 計算でも再利用する経路を選ぶ opt-in 変数。条件を満たすと `GrMulti::cached_norm` を立て、up kernel は正規化積を再計算せず `m.xn` から読む。環境変数だけで常に経路が切り替わるわけではなく、Battlemage と対応 layout 等の実行条件が必要である（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3298-3314, 932-976`）。

## 値と判定

`strata::bm_default_on(..., false)` が `std::getenv` で読み、非空文字列なら先頭文字だけを見る。先頭が `'0'` なら false、それ以外なら true。文字列全体の parse、数値妥当性検査、大文字小文字変換はしない。未設定または空文字列は helper の既定値 `false` となるため、Battlemage でも既定では無効（`engine/sycl/include/strata/sycl_queue.hpp:193-200`）。

| 条件 | unset / 空文字 | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| `STRATA_GR_CACHED_NORM` の判定（既定 false） | 無効 | `1`, `true`, `yes`, ` 1` | `0`, `0anything` |

したがって `false` や不正な数値文字列も先頭が `0` でなければ有効扱いであり、空白は trim されない。値の無効化・解釈失敗を通知するログはない（同 helper、`fused_gr.dp.cpp:3301`）。

## 有効になる条件

- この参照は SYCL の `fused_gr_read_multi` にある。関数内の `static const bool reuse_norm` は初回評価時に一度決まり、その後の環境変更は反映されない。static は関数内で共有されるため、複数 device で呼ぶ場合も初回の device による判定結果が保持される（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3139-3159, 3301`; helper の device 判定は `engine/sycl/include/strata/sycl_queue.hpp:196-200`）。
- `STRATA_SYCL_GR_CACHED_NORM` が `atoi(...) == 3` となる値で選ばれる既存 cached-norm 経路が有効な場合、`!cached_norm` 条件によりこの変数による再利用フラグ設定は行わない。既存経路は `STRATA_SYCL_GR_NORM_BOUNDS` と安全性判定等も必要とする別制御である（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:76-79, 85-105, 569-572, 3298-3307`）。
- この経路を選ぶには、private GR F32 経路 `gf_enabled` が無効、`gr_norm_split()` と `gr_down_sliced()` が有効、`gr_more_groups(st)`・`gr_large_grf(st)`・`gr_up_ilp()` がいずれも false、`gr_up_cols() == UPM_COLS`（既定 16）、device が Battlemage、かつ `gr_reuse_safe(...)` が true である必要がある。どれかを満たさない場合はフラグが適用されず、通常の norm/up 経路へ進む（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:304-329, 1203-1209, 2685-2688, 3298-3314`）。
- 関連設定の既定・判定は別々である。たとえば `STRATA_GR_NORM_SPLIT` と `STRATA_GR_DOWN_SLICED` は未設定なら true、`STRATA_GR_MORE_GROUPS` は未設定時 Alchemist で true、`STRATA_GR_UP_ILP` は先頭文字が `1` の場合 true。これらの値によって上記条件を外れることがある（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:574-576, 826-837, 1203-1209`）。
- `STRATA_GR_LO_REUSE` が同時に有効なら、どちらかの reuse flag が有効な場合に共通の条件判定へ進む。norm 側が無効なら `m.cached_norm` は false のままで、low-rank SiLU 側だけが再利用される（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3301-3314`）。

## 実行時の詳細

`fused_gr_read_multi` が引数を検査して queue を取得した後、既存 `cached_norm` 経路を計算し、この変数の static 値を読み取る。条件が成立すると `m.cached_norm = reuse_norm` とし、norm kernel で書かれた正規化済み入力を `m.xn` に保持して、up kernel で再利用する。再利用時の up kernel は通常経路の `rv * wn * rsc` の代わりに `m.xn[...]` を入力として使う。条件不成立時はこのフラグによる選択をせず、下流の既存 kernel 選択に任せる（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3139-3159, 3301-3340, 932-976`）。

## ログと測定値

再利用条件を満たし、norm または low-rank SiLU のいずれかを再利用すると、プロセス内で一度 `stderr` に `strata: GR reuse enabled: normalized activation %d, low-rank SiLU %d\n` を出す。各数値は選ばれた bool の値。対象変数が有効でも条件不成立なら、この reuse ログは出ない。値の誤りに対する警告や、この変数固有の失敗・終了処理はない。関数の引数検査に失敗した場合は別途 `fused_gr_read_multi: invalid arguments` または `fused_gr_read_multi: invalid arguments for token %d` を stderr に出して `exit(1)` する（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3142-3155, 3303-3314`）。

## 根拠

- `engine/sycl/include/strata/sycl_queue.hpp:193-200` — 共通 helper の値判定と device 既定動作。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:76-105, 304-329` — 別 cached-norm 制御と reuse 安全性条件。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3139-3159, 3298-3340` — 読み取り位置、適用条件、norm kernel 選択。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:932-976, 3470-3493` — cached flag を使う up 計算と kernel 選択。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:574-576, 826-837, 1203-1209, 2685-2688` — 関連 layout / backend 制御。
