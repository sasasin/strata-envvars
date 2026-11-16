# `STRATA_PF_FUSED_Q6K`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Q6_K の MoE gate/up と Q8_0 down の組を、Strata の fused prompt expert int8 kernel で処理する opt-in スイッチ。CUDA では `native_kernel<T_Q6_K, true>` と Q8_0 down kernel の両方をセットアップし、対応 layer を MMQ などの通常経路からこの組へ切り替える。HIP では gfx12 の同じ組に `native_w11_kernel` を使う。変数単独では他の Q6_K の組や Q8_0 down を有効にしない（`src/prefill/moe_fused_iq.cu:2488-2494,2924-2928,3009-3013,3212-3213,3305-3307`）。

通常の `strata` の fused prompt path は `STRATA_PF_FUSED` の全体判定も通る。`strata-q36` は起動時にこの変数を未設定なら `1` にするため、このエンジンでは値が有効な Q6_K/Q8_0 layer の候補となり、最終的な layer 選択は同エンジンの card rule に従う（`src/prefill/moe_fused_iq.cu:2891-2908`; `src/qwen35/q36_engine.cu:3950-3957,1407-1410`; `src/prefill/moe_fused_iq_q36.cu:126-139`）。

## 値と判定

CUDA と HIP の読み取り関数はいずれも `std::getenv` の戻り値が非 null で、先頭文字が `'1'` の場合だけ true とする。文字列全体の parse、数値検証、大文字小文字比較はしない（`src/prefill/moe_fused_iq.cu:2276-2278,2684-2687`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP の直接読み取り | false | `1`, `10`, `1anything`, `1 true`（先頭が `1`） | 空文字、`0`, `0anything`, `true`, `01`, ` 1` |
| `STRATA_PREFILL_FUSED` が定義され `STRATA_PREFILL_MMQ` が未定義の own-only build | 起動時に `1` を設定する | ユーザーが事前設定した値はそのまま。先頭が `1` なら有効 | 事前設定した空文字や `0...` は保持され、無効 |
| `strata-q36` | `main` のモデル読み込み前に `1` を設定する | ユーザー設定を保持し、先頭が `1` なら有効 | 空文字や `0...` は上書きせず、無効 |

own-only build の初期化は環境に名前が存在するかだけで設定済みと判断するため、空文字もユーザー設定として保持する。非 Windows は `setenv(..., "1", 0)`、Windows は未設定時だけ `_putenv_s` する。`strata-q36` も非 Windows では overwrite 無効の `setenv`、Windows では `getenv(...) == nullptr` の場合だけ `_putenv_s` する（`include/strata/prefill/own_only_switches.hpp:48-56`; `src/prefill/prefill.cpp:204-237`; `src/qwen35/q36_engine.cu:3950-3957`）。

## 有効になる条件

- 対象 executable/library に CUDA または HIP の fused prefill 実装が組み込まれていること。CUDA は `STRATA_PREFILL_FUSED` を付けて `strata_pf_own` を構成し、MMQ 有無に応じて `strata_prefill` に fused/MMQ 定義を付ける（`cmake/backends/cuda.cmake:285-307`）。HIP own-only 構成も fused prefill source を含む（`cmake/backends/hip.cmake:102-120`）。
- CUDA: compute capability 8.0 以上であること。`dev_info()` は 8 未満を返し、7.5/Turing 分岐は Q6_K をセットアップしない。さらに基本 native kernels が利用可能 (`d.ok`) で、Q6_K gate/up と Q8_0 down の `setup_one` が両方成功する必要がある。片方でも失敗すれば `d.q6k` は立たず、この pair は fused 対象にならない（`src/prefill/moe_fused_iq.cu:2428-2434,2488-2494`）。
- HIP: `dev_info()` が認識する gfx12 WMMA device (`d.w12`) で、基本 native kernels が利用可能 (`d.ok`) であること。gfx11、gfx1151、および `STRATA_HIP_GFX906` の早期 return 経路はこの Q6_K pair を選択しない（`src/prefill/moe_fused_iq.cu:2386-2414,2396-2412,2580,3010-3013`）。
- layer の gate/up が `T_Q6_K`、down が `T_Q8_0` の組であること。両 backend で `STRATA_PF_FUSED_NATIVE=0` または全体の `STRATA_PF_FUSED=0` は native pair を止める。CUDA では `STRATA_PF_FUSED_NT=256` / `STRATA_PF_FUSED_F16=1` が成功して `d.occ_nt > 0` になる場合、または `STRATA_PF_FUSED_WS=1` が成功して `d.ws` になる場合は、Q6_K pair 用 native wide kernel がないため通常の pair は選ばれない（`src/prefill/moe_fused_iq.cu:2318-2326,2329-2330,2891-2908,2924-2928`）。
- CUDA の own-only build は未設定の Q6K スイッチを既定で `1` にする。HIP own-only build も同じリストに含めるが、実際の Q6_K pair は gfx12 限定。MMQ ありの通常ビルドでは既定で Q6K は要求されない（`include/strata/prefill/own_only_switches.hpp:18-24,48-56`; `src/prefill/prefill.cpp:204-237`; `src/prefill/moe_fused_iq.cu:2274-2278,2681-2687`）。
- `strata-q36` は Q6K を含む fused switch 群を未設定時に `1` にする一方、全体の `STRATA_PF_FUSED` 判定と Qwen3.6 の device rule も適用する。よって Q6K が `1` でも layer が必ず fused になるわけではない（`src/qwen35/q36_engine.cu:3950-3972`; `src/prefill/moe_fused_iq_q36.cu:126-139`）。

## 実行時の詳細

CUDA の `q6k_cuda_requested()` と HIP の `q6k_hip_requested()` は関数内 `static const bool` に結果を保存する。CUDA は device ごとの `dev_info()` 初期化時にフラグを評価し、Q6_K gate/up と Q8_0 down の setup 成功時だけ `d.q6k` と別 occupancy を記録する。HIP は pair の coverage 判定でフラグを使い、Q8_0 down も Q6_K gate/up の後続として coverage する（`src/prefill/moe_fused_iq.cu:2276-2278,2379-2385,2488-2494,2684-2687,2691-2703`）。

値は各 reader の最初の呼び出しでキャッシュされ、後からプロセス環境を変えても反映されない。own-only build の既定設定は static 初期化で `main` より前、`strata-q36` の既定設定はモデル load より前に行われる（`src/prefill/prefill.cpp:204-237`; `src/qwen35/q36_engine.cu:3940-3957`）。

CUDA では `native_supported` が Q6_K/Q8_0 pair を許可し、`experts_native` が gate/up を `T_Q6_K`、down を Q8_0 の native kernel に dispatch する。HIP では gfx12 の同じ pair を `native_w11_kernel` に dispatch する。対象 format が合わない、全体スイッチで止まる、GPU/setup 条件を満たさない場合はこの fused pair に入りません。後続の選択先は MMQ の有無など別経路の条件に依存する（`src/prefill/moe_fused_iq.cu:2565-2581,2924-2928,3009-3013,3212-3213,3293-3308`; `src/qwen35/q36_engine.cu:1412-1441`）。

## ログと測定値

Q6K の値が無効、device が非対応、または CUDA の Q6K 専用 setup が失敗した場合に、この変数専用の警告・理由ログは見つからない。fused launch 後の `cudaGetLastError()` が失敗した場合は stderr に `prefill fused experts (native): experts_native: <CUDA error text>` を出して終了コード 1 で終了する（`src/prefill/moe_fused_iq.cu:60-65,2490-2494,3242,3339`）。

Strata の資料には、このスイッチの性能値を記載しない（対象値について測定条件を満たす一次資料を確認できなかった）。CUDA/HIP の CTest は `STRATA_PF_FUSED_Q6K=1` と `STRATA_MMQ_KQ=1` を併記し、当該 pair を参照経路等と比較する設定だが、テスト設定自体を性能・正確性の実測根拠にはしていない（`cmake/backends/cuda.cmake:413-416`; `cmake/backends/hip.cmake:180-182`）。

## 根拠

- 候補名と直接参照の全件確認: `src/prefill/moe_fused_iq.cu:2276-2278,2488-2494,2681-2687,2693,2700,2571,2580,2924-2928,3009-3013,3212-3213,3305-3307`; `src/qwen35/q36_engine.cu:3950-3957`。
- own-only 起動時既定値と backend 別の名前一覧: `include/strata/prefill/own_only_switches.hpp:18-24,48-56`; `src/prefill/prefill.cpp:204-237`。
- Qwen3.6 の値設定・layer 選択: `src/qwen35/q36_engine.cu:3950-3972,1407-1410`; `src/prefill/moe_fused_iq_q36.cu:115-139`。
- CUDA/HIP の compile/backend 構成: `cmake/backends/cuda.cmake:285-307`; `cmake/backends/hip.cmake:102-120`。
- CTest による候補値の使用（本番挙動の根拠ではない）: `cmake/backends/cuda.cmake:413-416`; `cmake/backends/hip.cmake:180-182`。
