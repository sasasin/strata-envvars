# `STRATA_PREFILL_MMQ`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

## 役割

この名前は二つの設定に使われています。CMake の `-DSTRATA_PREFILL_MMQ=ON` は HIP ビルドに GGML MMQ prefill 経路を組み込む build option です。プロセス環境変数 `STRATA_PREFILL_MMQ` は、CUDA/HIP の expert prefill で MMQ を使うか、SYCL の特定 expert 形式で fused int8 DPAS 経路を使うかを選びます。CMake option と実行時環境変数は別物で、実行時値だけで未ビルドの経路を追加することはありません（`CMakeLists.txt:94-95,145-146,1902-1903,2375-2438`）。

## 値と判定

| 実行経路 | 未設定・空文字 | `0` または数値変換が 0 | その他の値 |
|---|---|---|---|
| CUDA/HIP MMQ (`src/prefill/prefill.cpp`) | MMQ を要求する | MMQ を無効にする | `std::atoi` が 0 以外を返せば有効。数値の前方部分で変換されるため、例として `1x` は有効、`x1` と空文字は無効。負の非ゼロ値も有効 |
| SYCL fused int8 DPAS | 主変数が未設定または空なら `STRATA_PF_I8` を調べる。両方とも未設定・空なら Battlemage かつ対応 kernel 利用可能時だけ `auto` | 文字列先頭から読める数字の数値が 0 なら無効 | 先頭が `a` / `A` なら後続文字列に関係なく `auto`。それ以外は先頭から連続する数字を読み、数値が 0 以外なら強制 int8。数字が始まらない値（例 `true`, `-1`, 空白始まり）は 0 扱い |

CUDA/HIP は `std::atoi` による変換で、文字列全体の妥当性検査や無効値警告はありません。未設定は MMQ 有効側ですが、ビルドに MMQ がなく `mmq::built()` が false なら実際には使われません（`src/prefill/prefill.cpp:77-109,1348-1359`）。値を 0 にしたときは、対象 layer の MMQ が外れ、通常の FP16 expert 経路に回ります（同 `:1358-1375,1421-1422`）。

SYCL では `STRATA_PREFILL_MMQ` に非空値があれば alias の `STRATA_PF_I8` より優先されます。`auto` 判定は先頭文字だけで、大文字小文字は `a` / `A` のみ同様に認識します。数値判定は文字列全体ではなく連続する数字の prefix です（`sycl/src/prefill/prefill.cpp:276-288`, `sycl/include/strata/prefill/esimd_moe.hpp:39-50`）。

## 有効になる条件

- **CUDA/HIP:** MMQ コードがビルドされていることが必要です。ビルド済みでも、layer ごとに gate/up と down の形式・shape が `mmq::fits()` を満たす場合に MMQ を使います。満たさない layer は他の適用可能な経路がなければ FP16 側に残ります。plan は全 layer の形式と GPU 条件を見て作られます（`src/prefill/prefill.cpp:1348-1380`）。CUDA 側は `strata_mmq` を prefill にリンクして compile definition を設定します（`CMakeLists.txt:2151-2157,2299-2300`）。HIP 側では CMake option が既定 OFF で、HIP と native experts が必要です（同 `:94,145-146,1902-1903,2375-2438`）。
- **SYCL:** int8 経路は `STRATA_PREFILL_MMQ` を明示すれば対象形式で要求できます。対象は native expert pack、gate/up が IQ3_S / IQ3_XXS / IQ2_S、down が IQ4_NL / Q2_0、shape が 2560 x 640 で、Hadamard-folded (`had_gu` / `had_d`) でなく、MMQ を使う layer でもなく、XMX2 専用経路でなく、当該 device の int8 kernel が available であることが必要です。強制指定もこれらの条件を越えて経路を有効にはしません（`sycl/src/prefill/prefill.cpp:4251-4259`）。
- **SYCL の未設定時:** Battlemage は architecture id `bmg-g21` / `bmg-g31` で判定され、かつ kernel が利用可能な場合だけ `auto` になります。それ以外（Alchemist を含む）は FP16 です（`sycl/include/strata/prefill/esimd_moe.hpp:32-50`, `sycl/src/prefill/prefill.cpp:283-288`）。
- **SYCL の auto:** group ごとの平均 rows per expert を GPU 上で測った形式別 crossover と比較し、下回る group は int8、そうでなければ FP16 chain です。測定結果は queue・形式ごとの map に保持され、device 名・driver version・形式・shape を key に `STRATA_CACHE_DIR`（未設定なら `HOME/.cache/strata`、次に `LOCALAPPDATA/strata`）の `i8-crossover.txt` から読み書きします。測定不能時は crossover を 64 rows として扱い、その旨を stderr に出します（`sycl/src/prefill/prefill.cpp:875-920,923-936,1016-1045,4295-4305`）。

## 実行時の詳細

CUDA/HIP の `mmq_plan()` は最初の呼び出し時に `STRATA_PREFILL_MMQ` を読み、static な plan としてプロセス内に保持します。呼び出し元は prefill の scratch / buffer sizing や各 layer の expert 計算でこの plan を使います。従って plan 作成後の環境変更は再評価されません。plan が一部 layer で MMQ を使えない場合、`fallback` を立てて FP16 用 buffer も確保し、未対応 layer をその経路で計算します（`src/prefill/prefill.cpp:1348-1419,1421-1422,1816-1849,4205-4223`）。

SYCL は `i8_mode()` の呼び出しごとに環境を調べ、prefill の初期化・layer/group の処理で選択します。`auto` で int8 kernel の workspace が作れない、形式を処理できない、または launch が例外になる場合は、その group が FP16 chain に切り替わります。launch 例外時は `g_i8_failed` を立て、以後この process では FP16 chain を使います（`sycl/src/prefill/prefill.cpp:281-288,1223-1227,4254-4259,4290-4305,4327-4353`）。環境変数そのものを変更した場合の運用上の動作は明示されていません。特に staging ring の容量決定は別の時点で `i8_env()` を読むため、起動後に値を変更する使い方はコード上保証されません（同 `:289-294,1223-1227`）。

ログは経路が実際に使われた場合に出ます。CUDA/HIP の `STRATA_PREFILL_MMQ` に対する専用の有効・無効ログや無効値警告は確認できません。SYCL は int8 prompt experts が有効になったとき `strata: int8 prompt experts are on (...)`、group が int8 chain に入ったとき `strata: prompt experts on the fused int8 DPAS products (...)` を stderr に出します。kernel が使えない場合や workspace が作れない場合は、FP16 fallback の理由を示す stderr ログがあります（`sycl/src/prefill/prefill.cpp:1223-1227,4308-4312,4327-4337`）。

`STRATA_EXPERT_NIBBLE` が要求された起動では、別途 `env_conflicts()` がこの変数を検査します。空値は未設定と同様に扱い、非空値で `atoi(...) == 0` なら nibble 専用機能を無効にする理由になります。その場合 Strata は warning を出して通常の GGUF expert slot で続行します。これは nibble 機能への影響であり、`STRATA_PREFILL_MMQ` 自体の一般的な不正値エラーではありません（`include/strata/core/expert_nibble.hpp:272-286`, `src/program/generate.cpp:4165-4180`）。

## 根拠

- CMake option、backend / build 条件: `CMakeLists.txt:94-95,145-146,1902-1903,2135-2157,2299-2300,2375-2438`。
- CUDA/HIP 実行時読み取り、parse、static cache、layer 条件: `src/prefill/prefill.cpp:77-109,1301-1304,1348-1419`。
- CUDA/HIP の plan 利用・fallback buffer: `src/prefill/prefill.cpp:1421-1422,1816-1849,4205-4223`。
- SYCL の alias、値 parse、default 条件: `sycl/src/prefill/prefill.cpp:270-294`; parser: `sycl/include/strata/prefill/esimd_moe.hpp:39-50`。
- SYCL の形式・shape 条件、auto、fallback とログ: `sycl/src/prefill/prefill.cpp:4251-4265,4290-4305,4327-4353`。
- nibble との相互作用: `include/strata/core/expert_nibble.hpp:272-298`, `src/program/generate.cpp:4165-4180`。
