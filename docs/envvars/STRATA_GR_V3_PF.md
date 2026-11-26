# `STRATA_GR_V3_PF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA/HIP fused hyper-connection の v3 read が選ばれた場合に、down/up カーネル内の load ordering variant をビットマスクで選ぶ。通常の v3 kernel と同じ値・演算順序を保つ load scheduling variant で、読み出しアルゴリズム自体を v3 に切り替える変数ではない。v3 の選択は別の `STRATA_GR_V3` が決める。読み取りと dispatch は `engine/src/kernels/cuda/fused_gr.cu` の `v3_pf_mask()` / `fused_gr_read_multi_slice()` にある（同ファイル:4117-4141, 4351-4397）。

## 値と判定

最初に v3 read の実行経路から `v3_pf_mask()` が呼ばれた時、関数内 `static const int` 初期化で `std::getenv` を一度だけ行い、設定されていれば `std::atoi` の結果を保存する。未設定は sentinel `-1` となり、負の数値も `env >= 0` を満たさないため自動既定値へ進む。空文字列や数値として読めない文字列は `atoi` により 0。先頭の空白・符号の後の数値接頭辞が変換され、末尾の非数字は検査されない（例: `5tail` は 5、`true` は 0）。変換後の値域検査・clamp はなく、非負値がそのまま bit mask として使われる（`engine/src/kernels/cuda/fused_gr.cu:4123-4141`）。

| ビルド・条件 | unset または負値 | 有効値の例 | 無効値・効果の例 |
|---|---|---|---|
| CUDA、v3 read が動く | compute capability 12.0 かつ `STRATA_SM120_PERF` が無効化しておらず、`STRATA_DEFAULTS` が v0.2.6 指定でなければ既定 mask `133`。それ以外は `0` | `0` は plain v3 kernels、`5` は down bit 0 と up bit 2、`128` は bit 7 | 空文字、`true`、`0tail` は `atoi` 結果 0 なので plain v3 kernels。`-1` は自動既定値 |
| HIP | `0` | 明示した非負 mask は返される | unset は常に `0`。ただし変数を設定しただけでは v3 read を選択しない |

mask の対応は bit 0=down staging load variant、bit 1=down weight prefetch、bit 2=up partial/input loads、bit 3=up weight prefetch、bits 4-5=down rows-per-warp 2/4、bit 7=down register-blocked dot（5 token 以上の window）、bit 8=同 variant の 4-row dispatch。bit 6 とそれ以外の未参照 bit は dispatch に効果がない（`engine/src/kernels/cuda/fused_gr.cu:4117-4122, 4358-4389`）。

CUDA の自動既定値は `gr_v3_pf_default()` が計算し、sm_120 のみ `133`、その他は `0`。sm_121/GB10 はこの mask の既定を有効にしない定数設定。sm_120 でも `STRATA_SM120_PERF=0` または `STRATA_DEFAULTS=026`（同義指定 `0.2.6` / `v0.2.6` を含む）が既定値を 0 にする。これらの変数は本変数が未設定または負値のときの自動既定にだけ関係し、本変数の非負値が優先する（`engine/include/strata/core/bw_dense_defaults.hpp:14-16`, `engine/include/strata/core/sm120_series.hpp:32-38, 60-81, 100-106`, `engine/include/strata/core/defaults_026.hpp:22-29`）。

## 有効になる条件

- `fused_gr_read_multi_slice()` の通常経路まで到達する必要がある。Q8 down/up weights がある場合は先行する Q8 経路へ戻り、`rdna_gr_enabled()` が true の場合も RDNA 経路へ戻るため、いずれもこの mask を使わない（`engine/src/kernels/cuda/fused_gr.cu:4279-4303`）。
- さらに `STRATA_GR_V3` により v3 が選ばれ、デバイスの shared-memory 条件を満たして split が正に決まる必要がある。`STRATA_GR_V3` 未設定時の v3 自動選択は CUDA の discrete sm_120、13 GiB 超などに限られる。HIP は自動選択しないが、別変数 `STRATA_GR_V3` で明示的に選択された経路はコード上 mask 判定に進み得る（`engine/src/kernels/cuda/fused_gr.cu:4099-4113, 4304-4351`）。
- `STRATA_GR_V3=0`、または v3 split が成立せず既定 read に fallback する場合は本変数は効果を持たない。split が 2 の経路では down/up とも split-2 kernels を直接起動し、mask による variant dispatch を行わない（`engine/src/kernels/cuda/fused_gr.cu:4351-4382`）。
- 非負の環境 mask は自動既定値を置き換える。ベンチ/診断用 API `fused_gr_v3_pf(mask)` が先に `g_v3_pf_force` を非負値に設定した場合は、その強制値が環境変数より優先される。通常の CLI 引数による上書きはこのコードにない（`engine/src/kernels/cuda/fused_gr.cu:4142, 4358, 4440`; 宣言は `engine/include/strata/kernels/fused_gr.hpp:78-82`）。

## 実行時の詳細

環境値は v3 mask が初めて必要になった時に一度だけキャッシュされ、プロセス実行中に環境を変更しても再読込されない。自動既定 mask は別に device ごと（最大 64 slot）にキャッシュされる。CUDA では down/up dispatch が mask bits 0-5, 7, 8 に応じて variant を選び、該当しない token window では通常の v3 kernel に戻る。たとえば bit 7 は `n_tok >= 5` のとき先に試され、bit 8 はその後に試される。既定 mask 133 (`128 + 4 + 1`) は bit 7 と down bit 0 / up bit 2 を指定する（`engine/src/kernels/cuda/fused_gr.cu:4123-4141, 4358-4391`）。

`fused_gr_read_multi_slice()` は 1..8 token window を処理し、より広い window は複数 slice に分割して同関数へ渡す。single-read `fused_gr_read()` ではなく multi-read path が対象であり、engine verifier / MTP などから `fused_gr_read_multi()` が呼ばれる（入口は `engine/src/kernels/cuda/fused_gr.cu:4470-4484`; 代表的呼び出しは `engine/src/core/verify.cpp:1817`, `engine/src/core/mtp.cpp:1243`）。ビルドでは CUDA GPU engine のソース一覧に `src/kernels/cuda/fused_gr.cu` が含まれる（`engine/cmake/strata_gpu_engine.cmake:88-100`）。

## ログと測定値

環境値の受理・mask 選択を知らせる専用ログや無効値警告はない。v3 kernel launch 後の CUDA error は `fused_gr_read_multi v3: %s` を stderr に出して `exit(1)` する（`engine/src/kernels/cuda/fused_gr.cu:4392-4397`）。

ソースコメントは RTX PRO 5000、cold weights、16 sets、down+up read で mask 5 が T=1..8 に 4–8% 高速（T=4 で 26.45→24.90 µs）、weight-prefetch mask 2 は T=4 で 17% 遅く、2/4 rows-per-warp も遅かったとして、それらを既定では使わないと記録する。このコメント上の測定条件を超えて一般化しない（`engine/src/kernels/cuda/fused_gr.cu:4117-4122`）。`docs/DGX_SPARK_LINUX.md` は GB10 で本変数が level または slower だったとして既定 off と記す（`docs/DGX_SPARK_LINUX.md:124-126`）。

## 根拠

- `engine/src/kernels/cuda/fused_gr.cu:4117-4141` — mask の意味、環境値変換、既定値分岐。
- `engine/src/kernels/cuda/fused_gr.cu:4279-4309, 4351-4397` — 適用前の Q8/RDNA 分岐、v3 条件、kernel dispatch とエラー経路。
- `engine/include/strata/core/bw_dense_defaults.hpp:14-16`, `engine/include/strata/core/sm120_series.hpp:32-38, 60-81, 100-106`, `engine/include/strata/core/defaults_026.hpp:22-29` — 自動既定値と関連変数。
- `engine/include/strata/kernels/fused_gr.hpp:78-82`, `engine/src/kernels/cuda/fused_gr.cu:4142, 4440` — bench API による強制上書き。
- `engine/cmake/strata_gpu_engine.cmake:88-100`, `engine/src/core/verify.cpp:1817`, `engine/src/core/mtp.cpp:1243` — build inclusion と multi-read caller の例。
