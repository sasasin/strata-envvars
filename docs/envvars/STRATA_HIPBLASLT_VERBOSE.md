# `STRATA_HIPBLASLT_VERBOSE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP backend の prefill GEMM で hipBLASLt の tuning table を使うとき、解決した solution や一部の fallback 理由、state 破棄時の集計を stderr に出す診断用スイッチである。値は hipBLASLt のアルゴリズム選択や GEMM の計算結果を切り替えず、既存の fallback を観測可能にするだけである。実装は `engine/src/prefill/gemm.cu` の `resolve_hipblaslt_algo`、`try_hipblaslt`、`HipLtState::~HipLtState` にある（同様のコードは `engine/sycl/src/prefill/gemm.dp.cpp` にもあるが、そちらも `__HIPCC__` と `STRATA_HIPBLASLT_AVAILABLE` の両方が定義された箇所だけが有効）。CMake では HIP build かつ hipBLASLt が見つかった場合に `STRATA_HIPBLASLT_AVAILABLE` を定義する（`engine/cmake/hip_backend.cmake:81-94`、`engine/cmake/strata_gpu_engine.cmake:494-496`）。

## 値と判定

すべての読み取り箇所は `std::getenv(...) != nullptr` 相当の設定有無判定で、文字列の内容を変換・比較しない。unset は無効、空文字を含む設定済み値は有効である。したがって `0`、`false`、`0anything`、空白、大文字小文字を問わず、環境変数が存在すれば verbose 分岐に入る。数値の境界や無効文字列はない。例は HIP 実装 `engine/src/prefill/gemm.cu:221-228,412-420,505-509`。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| HIP compiler で `STRATA_HIPBLASLT_AVAILABLE` が定義された build、かつ HIPBLASLt state がある | verbose ログを抑制 | `1`、`0`、`false`、`0anything`、空文字 | なし（値の parse による無効値はない） |
| CUDA build、または hipBLASLt 非対応 build | この変数を読む有効な HIP 実装がない | なし | なし |

## 有効になる条件

- Strata が HIP backend でビルドされ、hipBLASLt が見つかって `STRATA_HIPBLASLT_AVAILABLE` が有効であること。CUDA build ではこの HIP 専用実装はコンパイルされない（`engine/cmake/strata_gpu_engine.cmake:494-496`）。
- GEMM 初期化時に `HipLtState` が作られていること。`create_hipblaslt_state` は `STRATA_HIPBLASLT_TUNING` が空でなければそのパスを使う。未設定または空なら `STRATA_HIPBLASLT_TABLE` の off/on/auto 相当の設定、GPU arch、`STRATA_GFX11_DEFAULTS`、gfx1103 の CWSR 条件とパッケージ内 table の有無により state が作られない場合がある（`engine/src/prefill/gemm.cu:284-300,344-386`）。state がない経路では、この verbose 変数によるログは出ない。
- verbose 判定は GEMM の algorithm 解決時（cache miss）と state の破棄時に行われる。モデル状態、CLI 引数、server mode による独立した判定はない。

## 実行時の詳細

HIPBLASLt state は `Gemm::init` または `Gemm::init_external` から生成され、各 BF16/FP16 GEMM は条件を満たす場合 `try_hipblaslt` を呼ぶ（`engine/src/prefill/gemm.cu:776-799,854-877,1183-1190,1322-1328`）。tuning table と GEMM の形状などから solution を解決する際、最初に per-state cache を調べ、cache miss のときにこの環境変数を読む。したがって同じ key が cache hit した呼び出しでは resolver の verbose 行は再出力されない（`engine/src/prefill/gemm.cu:402-420`）。プロセス環境を直接読むため初期化時に値を固定しない。実行中に環境が変更された場合、以降の cache miss と state 破棄時の判定に反映されるが、通常の起動後に親プロセスの環境を書き換えられるかはこの実装では扱わない。

この変数が有効でも、調整データがない、solution が利用不能、実形状をサポートしない、必要 workspace が不足するなどの理由で GEMM は従来の hipBLASEx 経路へ fallback し得る。これらの判定と fallback 自体は verbose の有無にかかわらず行われる。hipBLASLt launch が失敗した場合も既存処理に従い、beta が非ゼロで所定の prelaunch error に該当しなければ stderr に拒否理由を出して `exit(1)` する（`engine/src/prefill/gemm.cu:488-538`）。verbose はこの終了条件を変えない。

`engine/sycl/src/prefill/gemm.dp.cpp` にも同名の読み取りが3箇所ある（152、243、323行）が、SYCL の通常の `icpx` build は別 backend であり、このコードを動かす guard は `__HIPCC__ && STRATA_HIPBLASLT_AVAILABLE` である。同ファイルの通常の Intel SYCL 実装を、この環境変数の適用先とは扱わない（`engine/sycl/CMakeLists.txt:21,39-47` および同ファイル:120-121,392-429）。候補一覧の `docs/SETTINGS.md:107` は Intel Arc も対象としているが、確認した実装の build guard からは通常の Intel SYCL / Arc build でこの変数が有効になる根拠を確認できない。

## ログと測定値

verbose が有効な cache miss では、該当する場合に次の stderr 行を出す。

- `prefill gemm: Lt fallback; no calibration for dtype=... T=... N=... K=... ldy=...`
- `prefill gemm: Lt fallback; solution ... unavailable for T=... N=... K=... ldy=...`
- `prefill gemm: Lt fallback; solution ... rejects actual T=... N=... K=... ldy=... beta=...`
- `prefill gemm: Lt solution=... dtype=... T=... N=... K=... ldy=... beta=... workspace=...`
- `prefill gemm: Lt fallback; solution needs ... workspace bytes, have ...`

HIPBLASLt state の破棄時には `prefill gemm: hipBLASLt summary launches=... fallbacks=... unique_fallback_shapes=...` と fallback shape ごとの行を出す。ここでも破棄時点で変数が設定されていることが条件である（`engine/src/prefill/gemm.cu:220-228`）。launch failure の行 `prefill gemm: hipBLASLt launch failed with status ...` など一部の診断・失敗ログは verbose 判定の外にあり、unset でも出る（`engine/src/prefill/gemm.cu:524-529`）。この変数の効果に関する Strata の性能測定値は確認できない。

## 根拠

- `engine/src/prefill/gemm.cu:189-233` — HIPBLASLt state と破棄時 summary。
- `engine/src/prefill/gemm.cu:284-300,344-399` — tuning 設定、パッケージ table、state 生成条件。
- `engine/src/prefill/gemm.cu:402-475,488-538` — cache、verbose の読み取り、algorithm 判定、fallback と失敗処理。
- `engine/src/prefill/gemm.cu:776-799,854-877,1183-1190,1322-1328` — 初期化と BF16/FP16 呼び出し。
- `engine/cmake/hip_backend.cmake:81-94`、`engine/cmake/strata_gpu_engine.cmake:494-496` — HIPBLASLt build 条件。
- `engine/sycl/src/prefill/gemm.dp.cpp:120-163,196-231,233-293,306-350`、`engine/sycl/CMakeLists.txt:21,39-47` — 条件付きの重複実装と SYCL build。
