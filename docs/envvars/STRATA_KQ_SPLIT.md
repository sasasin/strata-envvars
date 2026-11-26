# `STRATA_KQ_SPLIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP と SYCL の GPU expert kernel で、対応する量子化形式の重みを複数 entry に再利用する split kernel を使うか選ぶ。値が変えるのは kernel 経路であり、入力や expert の選択を変える設定ではない。コードコメントは split と per-entry の出力を同じ bit と説明しているが、この調査では GPU 実行や parity test は行っていない。CUDA/HIP では主に量子化形式 ID `12` (Q4_K)、`13` (Q5_K)、`8` (Q8_0) に適用され、SYCL では別の形式群に適用される。`iq_kernels.cu` と `iq_kernels.dp.cpp` が環境値を読み、`native_expert_grouped` や MMVQ の launch 選択に使う。CUDA/HIP の kernel TU は CUDA engine の `strata_kernels` に含まれ、SYCL の `.dp.cpp` は SYCL kernel target に含まれる（`engine/src/kernels/cuda/iq_kernels.cu:989-992,3790-3804,4541-4570,4622-4636`; `engine/cmake/strata_gpu_engine.cmake:48-99`; `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:2592-2616,5922-5937,5981-5989`; `engine/sycl/CMakeLists.txt:44`）。

## 値と判定

どちらも数値変換や文字列全体の比較ではなく、`getenv` が返す文字列の先頭 1 文字だけを見る。空白除去、大文字小文字変換、範囲検査はない。

| backend | unset | split を有効にする例 | split を無効にする例 |
|---|---|---|---|
| CUDA/HIP | 無効 | `1`, `10`, `1anything` | 空文字、`0`, `0anything`, `true`, `2`, ` 1` |
| SYCL | 有効 | 空文字、`1`, `true`, `false`, `2`, ` 0` | `0`, `0anything`, `00` |

CUDA/HIP は `v != nullptr && v[0] == '1'` のときだけ true。したがって未設定・空文字・先頭が `1` 以外の値はすべて false である。SYCL は `!(v && v[0] == '0')` なので、未設定または先頭が `0` 以外なら true、空文字も true になる（`engine/src/kernels/cuda/iq_kernels.cu:991-992`; `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5922`）。

値の指定を CLI 引数や設定ファイルで上書きする読み取り箇所は見つからなかった。SYCL 実装には `native_expert_set_kq_split(bool)` による実行中の上書き口があり、SYCL parity プログラムが false/true を切り替えて比較する。通常の環境変数は初期化時に一度読まれ、後から環境を変えても再読込されないが、この setter を呼ぶコードでは状態が変更される（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5922,6124-6128`; `engine/sycl/src/kernels/native_grouped_parity.cpp:470-480`）。

## 有効になる条件

- **CUDA/HIP:** `Split<TY>` が存在する形式でも、`kq_type<TY>` に含まれる `12`, `13`, `8` だけがこの変数の on/off 対象。Q5_1 (`TY=7`) は split trait を持つが `kq_type` から除外されている。type ID の対応は `engine/include/strata/quant/types.hpp:12-18`。`STRATA_OLD_IQ_MMVQ` が未設定・空でなく、先頭文字が `0` 以外なら `env_on` が true になり、旧 per-column/per-entry kernel が選ばれる（`engine/src/kernels/cuda/iq_kernels.cu:3689-3695,987-992,3790-3804,4541-4549,4622-4628`）。
- **SYCL:** lane kernel が KqSplit を使う量子化形式でだけ分岐に関与する。対応 trait は IQ4_XS (`23`)、Q4_K/Q5_K/Q6_K (`12`/`13`/`14`)、Q5_1/Q5_0/Q4_0/Q4_1/Q8_0 (`7`/`6`/`2`/`3`/`8`)、NVFP4 (`40`)、TQ2_T/TQK6/TQK7 (`144`-`146`)（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:2592-2616`; ID 対応: `engine/include/strata/quant/types.hpp:12-18`）。
- **SYCL 経路:** `STRATA_EXPERT_SPLIT` が未設定・空でなく、先頭文字が `0` 以外で `STRATA_OLD_IQ_MMVQ` が無効なら、QK split 形式の gate/up と down は別の multi kernel へ進み、この変数による lane kernel 内の切替は通らない。`STRATA_OLD_IQ_MMVQ` が有効（同じ `env_on` 判定）なら lane 経路になるが、KQ split の値にかかわらず旧 kernel 側を選ぶ。SYCL の fused gate/up 経路も `g_kq_split` が true で、かつ `exp_mode()==8`, `!g_old_kernels`, `!g_split_multi`, `gu_lanes()==8`, phase 条件などを満たす場合に限られる（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3928-3938,6053-6067,6115-6120,7797-7817`）。
- CUDA/HIP の grouped expert では `native_expert_grouped` の形式・入力形状により別 kernel 経路が先に選ばれることがある。`STRATA_EXPERT_V2=1` の専用経路、または `STRATA_EXPERT_V2K` が先頭 `1` で有効になった専用経路（HIP の一部では未指定時に GPU に応じて既定有効）が条件成立時に先行 return するため、その呼び出しでは通常 launcher の split 判定に到達しない（`engine/src/kernels/cuda/iq_kernels.cu:7121-7132,7138-7158,7161-7182`）。

## 実行時の詳細

CUDA/HIP のフラグは翻訳単位の `g_kq_split` として初期化される。MMVQ では旧 `mmvq_kernel` と multi-column kernel の選択、grouped expert の gate/up と down では per-entry kernel と multi kernel の選択に使われる。false の場合は `split_off<TY>()` が true になり、対応形式で旧 kernel に分岐する（`engine/src/kernels/cuda/iq_kernels.cu:991-992,3790-3804,4541-4570,4622-4636`）。

SYCL も `g_kq_split` をグローバル初期化時に一度環境から設定する。lane 経路の gate/up (`gu_port_km`) と down (`down_port_km`) で false の場合は `KM=false` を指定して per-entry kernel を起動し、true なら `KM=true` の multi-entry split を起動する。setter による更新は別途可能だが、通常の環境変数はリクエストごとに読み直されない（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5922-5937,5981-5989,6124-6128`）。

CUDA/HIP の通常 launcher は false で従来の dot-per-entry kernel、true で weight 側を split して複数 column/entry に使う multi kernel を選ぶ。コメント上は算術順序と結果 bit を保つ意図であり、変数自体に値域エラーや fallback log はない（`engine/src/kernels/cuda/iq_kernels.cu:975-992,1681-1700,3790-3804,4541-4570`）。

## ログと測定値

CUDA/HIP には `STRATA_KQ_SPLIT` の有効・無効を通知する専用ログや値エラー処理はない。SYCL では lane 経路で IQ4_XS (`TG==23`) の split が有効なとき、初回に stderr へ `strata: IQ4_XS exact multi-entry decode reuse enabled` を出す。無効時の対応ログはない（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5927-5937`）。

この環境変数について条件付きの性能測定値を載せた `docs/DETAILS.md` の記述は見つからなかった。ソースの parity 用 CMake 設定は一部テストに `STRATA_KQ_SPLIT=1` を与えるが、テストは実行していない（`engine/cmake/strata_gpu_engine.cmake:844-864`）。

## 根拠

- `engine/src/kernels/cuda/iq_kernels.cu:983-992` — CUDA/HIP split trait、対象 type、値の読み取り。
- `engine/src/kernels/cuda/iq_kernels.cu:3790-3804,4541-4570,4622-4636` — MMVQ と grouped expert の kernel 選択。
- `engine/src/kernels/cuda/iq_kernels.cu:7121-7132,7159-7182` — grouped expert の先行経路。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:2592-2616,5922-5937,5981-5989,6124-6128` — SYCL の対応形式、読み取り、lane launcher、setter。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3931-3938,6053-6067,6115-6120,7797-7817` — SYCL の別 launcher と適用条件。
- `engine/sycl/src/kernels/native_grouped_parity.cpp:470-480` — parity 用 setter 呼び出し。
- `engine/cmake/strata_gpu_engine.cmake:844-864` — テスト向け環境設定。
