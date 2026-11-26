# `STRATA_GR_FUSED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

HIP の AMD 向け hyper-connection（HC）RDNA read で、通常の down / up 2 kernel launch を、条件が揃うと down・grid barrier・up を行う persistent fused kernel 1 回に切り替えるための opt-in です。この変数だけでは RDNA read 自体を有効にしません。`STRATA_GR_RDNA` または `STRATA_HIP_FAST_DEC` によって `rdna_gr_enabled()` が true になり、対象 read が Q8 専用経路でなく、後述のデバイス条件も満たす必要があります（`engine/src/kernels/cuda/rdna_gr.cu:501-508,520-550,555-571`; `engine/src/kernels/cuda/fused_gr.cu:4286-4302`）。

有効な場合、`rdna_gr_fused` が `down_a8_body` の後に全 grid の barrier を行い、成功すれば `up_body` を同一 kernel 内で実行します。条件が不足すると、同じ RDNA read の down / up 2 kernel 経路に戻ります。これは HC read の起動形を変える設定であり、Strata のコードから生成結果や速度の変化を断定できる測定値は確認できません（`engine/src/kernels/cuda/rdna_gr.cu:500-508,520-550`）。

## 値と判定

AMD HIP の非 gfx906 ビルドで `std::getenv("STRATA_GR_FUSED")` を呼び、値が null でないことと `v[0] == '1'` だけを判定します。数値変換や文字列全体の比較はしません。空文字は設定済みでも無効です。`1anything` のように先頭 byte が `1` なら有効で、`0`、`0anything`、`true`、`TRUE`、先頭が空白の ` 1` は無効です。大文字小文字、残りの文字、数値としての妥当性は検査されません（`engine/src/kernels/cuda/rdna_gr.cu:510-517`）。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `__HIP_PLATFORM_AMD__` が定義され、`STRATA_HIP_GFX906` が未定義 | fused persistent read を要求しない | 先頭 byte が `1`（例: `1`, `1abc`） | 空文字、`0`, `0anything`, `true`, ` 1` など先頭 byte が `1` でない値 |
| 上記以外（CUDA-only、gfx906 compat など） | 読み取りなし。stub は `rdna_gr_enabled() == false` | 該当なし | 該当なし |

## 有効になる条件

- AMD HIP の非 gfx906 実装であること。その他のビルドでは `rdna_gr_enabled()` は常に false を返し、`rdna_gr_init()` は何もしません（`engine/src/kernels/cuda/rdna_gr.cu:26,555-584,611-615`）。
- `rdna_gr_enabled()` が true であること。`STRATA_GR_RDNA` が設定されていれば先頭 byte が `1` の場合だけ true になり、その値が `0` 等なら `STRATA_HIP_FAST_DEC` は調べません。`STRATA_GR_RDNA` が未設定の場合に限り、`STRATA_HIP_FAST_DEC` の先頭 byte が `1` なら GPU 名が gfx11 または gfx12 のとき true になります（`engine/src/kernels/cuda/rdna_gr.cu:555-571`）。
- `fused_gr_read_multi` の対象が Q8 専用分岐でないこと。`q8_down` と `q8_up` が両方非 null なら、変数や RDNA 判定より先に `launch_q8` を呼んで戻るため、この fused read は使われません（`engine/src/kernels/cuda/fused_gr.cu:4286-4294`）。
- RDNA read 側で `s_down` と `s_up` が両方非 null であること。異なる場合はこの fused persistent read を選びません（`engine/src/kernels/cuda/rdna_gr.cu:520-550`）。
- fused read 用 barrier buffer の確保に成功し、選択中デバイスの index が `0..63` であること。確保できない、または初期化に失敗した場合は `m.bar == nullptr` となり 2 kernel 経路になります（`engine/src/kernels/cuda/rdna_gr.cu:575-584,593-597,525-550`）。
- profiling stamp buffer `sb` が null であること。非 null のときは fused persistent kernel の条件を満たさず 2 kernel 経路になります（`engine/src/kernels/cuda/rdna_gr.cu:520-550`）。
- `compute_safe_persistent_grid` が固定 grid の常駐可能性を認めること。必要 grid は 168 blocks で、occupancy と CU 数から安全数を計算します。Windows では helper が `can_fuse_fixed` を false にするため、値が有効でも fused launch されません（`engine/src/kernels/cuda/rdna_gr.cu:523-540`; `engine/include/strata/kernels/rdna3_wddm_guard.hpp:29-43`）。

## 実行時の詳細

`gr_fused_requested()` 内の function-local `static const bool` が、プロセス内で最初に呼ばれたときだけ環境を読み、その結果を cache します。最初の通常経路は `Verifier::init()` から呼ばれる `fused_gr_check()` が `rdna_gr_init()` を実行する時点です。Linux HIP の一部では `generate.cpp` から、モデル arena の準備前にも同じ check が呼ばれます。したがって、最初の呼び出し後にプロセス環境を変えても判定は更新されません（`engine/src/kernels/cuda/rdna_gr.cu:511-517,575-577`; `engine/src/core/verify.cpp:956-970`; `engine/src/program/generate.cpp:8507-8514`; `engine/src/kernels/cuda/fused_gr.cu:4742-4747`）。

要求が true の場合、`rdna_gr_init()` は選択中デバイスごとに 64 byte の barrier word を `cudaMalloc` し、ゼロ初期化します。これは verifier check の時点で行われ、read の stream capture 中に初回確保が起きないようにしています。`launch_gr` は要求値に加え、barrier、stamp 不在、device 範囲、固定 grid の安全性を確認して fused kernel を選びます。条件を満たさなければ down と up を別々に launch します（`engine/src/kernels/cuda/rdna_gr.cu:574-584,520-550,593-608`）。

選択後の `rdna_gr_fused` は down pass と grid barrier を実行し、barrier が期限内に完了した場合だけ up pass に進みます。期限超過時は kernel がその場で return し、2 kernel read への実行時 fallback や専用ログはありません。この timeout 経路では up pass が実行されないことをコードから確認できます（`engine/src/kernels/cuda/rdna_gr.cu:471-508`; `engine/include/strata/kernels/rdna3_wddm_guard.hpp:46-67`）。

## ログと測定値

この変数の値、barrier buffer の確保成否、または fused read の選択を知らせる専用ログはありません。`fused_gr_read_multi` が RDNA read の launch error を検出した場合は stderr に `fused_gr_read_multi rdna: %s\n` を出して `exit(1)` します。これは `cudaGetLastError()` がエラーを返した場合の処理です（`engine/src/kernels/cuda/fused_gr.cu:4295-4302`）。

`docs/SETTINGS.md` はこの名前を NVIDIA and AMD 向けの on/off 設定として掲載していますが、実際の読み取りと実装は `rdna_gr.cu` の AMD HIP・非 gfx906 guard 内だけです。実行条件の説明はソースコードに基づきます（`docs/SETTINGS.md:92`; `engine/src/kernels/cuda/rdna_gr.cu:26,510-517,611-615`）。条件付きの性能測定値は、この調査範囲で確認できませんでした。

## 根拠

- `engine/src/kernels/cuda/rdna_gr.cu:26,510-517` — コンパイル guard と値の読み取り・判定。
- `engine/src/kernels/cuda/rdna_gr.cu:520-550,555-584,586-615` — 起動条件、fallback、他変数による RDNA read 判定、barrier buffer と stub。
- `engine/src/kernels/cuda/fused_gr.cu:4286-4302,4742-4747` — Q8 優先分岐、RDNA read の呼び出しと error 経路、初期化からの呼び出し。
- `engine/src/core/verify.cpp:956-970`; `engine/src/program/generate.cpp:8507-8514` — 初期化時期。
- `engine/include/strata/kernels/rdna3_wddm_guard.hpp:29-67` — 固定 grid の安全条件と bounded spin の判定。
