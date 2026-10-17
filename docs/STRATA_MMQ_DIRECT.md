# `STRATA_MMQ_DIRECT`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

CUDA の prompt 用 MoE MMQ で、常駐 expert の重みを一時的な group buffer に gather せず、expert cache slot 内のデータを直接 MMQ に渡す機能を選びます。対象は native pack のうち pointer-table MMQ が対応する形式・layer です。ストリームから届いた expert、peer GPU 上の expert、pointer-table 非対応形式などは引き続き gather されます。

## 値と判定

値は `std::atoi` で整数に変換され、結果が `1` または `2` の場合だけ候補モードになります。文字列全体の検証はしません。したがって `1tail` や先頭空白付きの ` 1` は 1、`2xyz` は 2、空文字・数値で始まらない文字列・`0`・負値は 0 として扱われます。未設定時も 0 です。判定結果は `direct_mode()` 内の `static const int` に保存されるため、最初の呼び出し後に環境を変更しても再評価されません。

| 判定値 | 動作 |
|---|---|
| 0（未設定、無効値を含む） | 従来の gather 経路。slot guard も追加しない |
| 1 | guard を確保し、条件を満たす常駐 expert を slot 内から直接読む |
| 2 | guard を確保するが、従来どおり gather する。A/B 比較用 |

有効な 1 または 2 でも pointer-table MMQ がビルドに含まれない場合は 0 に戻り、stderr に `strata: STRATA_MMQ_DIRECT=%d is ignored: this build has no pointer-table MMQ (CUDA with STRATA_MMQ_TAB only)` と出します。無効値はこの警告を出しません。

## 有効になる条件

- CUDA の pointer-table MMQ がビルドされている必要があります。CMake option `STRATA_MMQ_TAB` は既定 OFF で、CUDA のみが対象です。設定 ON でも、CMake が検査する llama.cpp `mmq.cuh` の scheduler fingerprint が対応済みでない場合は feature を OFF にして configure 時に理由を表示します（`CMakeLists.txt:1606-1645`）。
- 実際の prompt 経路で MMQ が使われる必要があります。`STRATA_PREFILL_MMQ` が無効な場合、MMQ plan が有効にならず直接読み取りは行いません。ただし `STRATA_MMQ_DIRECT` が 1/2 なら、native pack では `slot_guard_bytes()` が 256 bytes を返し、cache 作成時に guard を要求します。そのため直接読み取りがない場合も cache slot の room に影響することがあります。
- mode 1 は native expert layout のみを走査し、各 layer の gate/up と down の両方が pointer-table MMQ の形式・shape 条件を満たすこと、gate/up の over-read がないこと、down の over-read が 256-byte slot guard 内であること、blob の各 weight offset/size が MMQ matrix の配置と一致することを確認します。合わない layer は gather のままです。pointer-table は native pack の Q2_0、IQ2_XXS、IQ2_XS、IQ2_S、IQ3_XXS、IQ3_S、IQ4_NL、IQ4_XS、Q8_0 向けで、Q5_0 と K-quants は対象外です。
- slot に guard の余裕がない場合や expert blob のアラインメント条件を満たさない場合も、その expert は gather に fallback します。常駐かつ slot 内に必要な余裕があるときだけ直接読みます。
- HIP、gfx906、SYCL、および pointer-table MMQ を含まない build では有効になりません。非 CUDA 側の stub は `direct_mode()` を常に 0 にします。

## 実行時の詳細

`direct_mode()` は `src/prefill/moe_mmq.cu` から呼ばれ、mode 1/2 なら `kSlotGuard`（256 bytes）を返します。generate は native pack の cache slot を作る際にこの guard 要求を渡します。mode 1 では `mmq_plan()` が layer ごとの適用可否を一度計算し、適用できる layer 数と合計を stderr に表示します。prompt の各 MMQ group では、cache slot に blob 末尾から必要な guard bytes までの room があり、アドレスも 16-byte 条件を満たす常駐 expert の pointer を table に設定します。down product が読む可能性のある slot tail は group 処理前に zero-fill します。その他の expert は元の group buffer へ gather します。

generate の prompt 完了ログでは、直接読んだ expert があれば `prompt MMQ read ... of the ... resident experts in their slots (STRATA_MMQ_DIRECT)` と出ます。任意の `STRATA_MMQ_DIRECT_LOG` は mode 1 の場合にだけステージ別累計を追加表示します。これは別変数のため、本書ではその値の parse 詳細は扱いません。

## 文書との照合

`docs/DETAILS.md` は mode 2 を guard layout を使う gather 基準経路と説明し、mode 1 と同じ計算結果になること、4x RTX 3090 の UD-IQ4_XS 条件での prompt 時間比較を記載しています。測定条件は `--trim-stage-weights --batch 16`、全 expert 常駐、engine を直接駆動、各条件の中央値 8 回です。記載値は 170-token prompt で 331→251 ms と 369→290 ms の2系列、1,217-token prompt で 773→634 ms と 838→675 ms の2系列です。これは同資料に記録された結果であり、今回の調査で性能を再測定したものではありません。

## 根拠

- `src/prefill/moe_mmq.cu:541-556` — 環境変数の parse、対応値、build 不対応時の警告、guard サイズ。
- `include/strata/prefill/moe_mmq.hpp:139-160` — pointer-table 条件、対応形式、mode の仕様と既定値。
- `CMakeLists.txt:88-96,1606-1645` — option の既定値、fingerprint による無効化、compile definition。
- `src/prefill/prefill.cpp:1129-1174` — prompt MMQ plan、native layer の判定、適用数ログ。
- `src/prefill/prefill.cpp:4203-4279` — 常駐 expert の slot 直接読み、slot tail 条件、gather fallback と group 処理。
- `src/program/generate.cpp:3258-3262,5908-5915,6172-6175,15014-15023` — cache slot guard の受け渡しと prompt 後のログ。
- `src/core/expert_cache.cpp:570`、`include/strata/core/expert_cache.hpp:227-233` — sized slot の guard と末尾アドレス取得。
- `docs/DETAILS.md:1925-1954` — 設計説明、記録済みの測定と exactness 条件。
