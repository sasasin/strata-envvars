# `STRATA_IQ2S_GU_ROW_REUSE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL の native grouped expert の IQ2_S gate/up（GU）計算で、2 行を処理するときに入力 activation の展開結果を両行で共有する row-reuse カーネルを選びます。環境変数が有効でも、この経路を使えるのは Battlemage GPU、IQ2_S の型番号 22、8 lane の場合です。対象は Strata が実装するカーネル選択です。

## 値と判定

共通 helper `strata::bm_default_on()` が `std::getenv(name)` を呼び、次の規則で値を判定します。

| 環境変数の状態 | helper の判定 | Battlemage での結果 | その他 GPU での結果 |
|---|---|---|---|
| 未設定 | 既定値を使う | 有効 | 無効 |
| 空文字 | 既定値を使う | 有効 | 無効 |
| 非空で先頭文字が `0` | 明示的に無効 | 無効 | 無効 |
| 非空で先頭文字が `0` 以外 | 明示的に有効 | helper 上は有効 | helper 上は有効だが、この機能の追加条件で無効 |

文字列全体の parse は行いません。たとえば `false`、`2`、`yes` は先頭文字が `0` 以外なので helper では有効、`0`, `0anything` は無効です。空文字は「設定あり」として扱わず未設定と同じ既定判定になります。最終的なカーネル選択には後述の Battlemage 条件も必要です。

## 有効になる条件

- SYCL 実装の `native_expert_grouped` から IQ2_S gate/up 型（`L.gu_type == 22`）の grouped カーネルが選ばれること。
- `launch_gu_port` のテンプレート条件が IQ2_S（型 22）かつ `LN == 8` であること。IQ2_S の lane 選択は `STRATA_GU_LANES` に従い、4/16/32 を選ぶとこの row-reuse 分岐には入りません。未設定・不正値の lane 数はビルド時既定の 8 に戻ります。
- ビルド時に `STRATA_GRID_SLM` が 0 であること。この macro が 1 なら row-reuse 選択コード自体がコンパイル対象から外れます。未定義時はソース内で 0 にします。
- `STRATA_OLD_IQ_MMVQ` と `STRATA_EXPERT_SPLIT` が無効であること。これらは設定有無ではなく、先頭文字が空でなく `0` でもない場合に有効です。
- 対象 device が Battlemage と認識されること。環境変数を明示的に有効にしても、実行時の Battlemage 判定は省略されません。

## 実行時の詳細

row-reuse 分岐では `native_gu_row_reuse_kernel` を launch します。各処理単位で最大 4 件の expert entry をまとめ、入力 activation の `M::acts` を entry ごとに一度展開した後、2 つの GU 行それぞれについて重みを準備し dot 積を計算します。gate と up の出力先は行番号から選びます。分岐条件に合わない場合は通常の `native_gu_kernel` が使われます。

環境変数判定は `launch_gu_port<TG, LN, KM>` の関数内 `static const bool reuse` に保持されます。テンプレート実体ごとに初回呼び出し時に一度評価され、その後プロセス内で環境を書き換えても再評価されません。helper の Battlemage 既定値はその初回呼び出しの device に基づきますが、row-reuse 分岐では各呼び出し時にも現在の device が Battlemage か確認します。

row-reuse 経路を選ぶと stderr に `strata: IQ2_S raw two-row GU reuse enabled (8 lanes, SIMD16)` を出します。選択されなければこのログは出ず、通常カーネルに進みます。この分岐に対象変数由来の警告、エラー、終了処理は見つかりません。`STRATA_EXPERT_ROW_E3` は row-reuse カーネル内の 3-entry tail の処理を別途選びますが、row-reuse 経路自体を有効化する条件ではありません。

## 根拠

- `sycl/include/strata/sycl_queue.hpp:159-166` — Battlemage device 判定を使う既定 ON helper、設定値の先頭文字判定。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:452-456` — `STRATA_GRID_SLM` の既定値。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3432-3443` — `STRATA_OLD_IQ_MMVQ` と `STRATA_EXPERT_SPLIT` の読み取り規則。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:957-962,4858-4864,4917-4927` — lane 数のビルド時既定値、`STRATA_GU_LANES` の許容値と fallback、lane ごとの dispatch。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4720-4766,4768-4819` — 2 行で activation を共有し GU 結果を出力する処理。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4822-4853` — row-reuse kernel launch と有効ログ。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4870-4896` — IQ2_S / 8 lane / build macro / runtime 条件、通常 kernel fallback。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6070-6135` — grouped expert gate/up の dispatch。
- `docs/INTEL.md:518-540` — この設定が Battlemage 向け SYCL runtime control の一つとして記載されていること。性能値は本書では独自に確認していません。
