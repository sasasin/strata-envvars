# `STRATA_VERIFY_DEBUG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-26 時点）。

## 役割

Verifier の診断出力を有効にするデバッグ用フラグです。CUDA/HIP 実装では検証ウィンドウの捕捉・起動・レイヤー処理の進行を `stderr` に出します。SYCL 実装ではそれらに加え、Verifier 初期化時のキュー情報、ウィンドウ時間、条件付きのウィンドウ状態・中間値の診断を出します。いずれも診断用で、環境変数自体が token や検証結果の選択規則を切り替えるコードはありません（`engine/src/core/verify.cpp:321, 3847-3848, 3889, 4291`、`engine/sycl/src/core/verify.cpp:136, 2398, 2449, 2689, 2717, 2994`）。

## 値と判定

両実装とも `getenv(...) != nullptr` の有無判定です。値の文字列は変換・比較されません。未設定なら無効、空文字を含む何らかの値が設定されていれば有効です。`0`、`false`、`0anything` も設定済みなので有効です。空白や大文字小文字も解釈されません。CLI 引数や別環境変数による値の上書き・優先順位はありません。

| 実装 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA/HIP (`engine/src/core/verify.cpp`) | 無効 | 空文字、`0`、`1`、`true`、その他すべての設定値 | なし（設定済みなら有効） |
| SYCL (`engine/sycl/src/core/verify.cpp`) | 無効 | 空文字、`0`、`1`、`true`、その他すべての設定値 | なし（設定済みなら有効） |

CUDA/HIP の `g_dbg` は翻訳単位のグローバル定数として初期化され、以後 `VDBG` から参照されます。SYCL も `VDBG` 用の `g_dbg` は同様ですが、初期化ログ・追加バッファ確保・ウィンドウ末尾の診断では `getenv` を直接再評価します。そのため、プロセス起動後に環境値が変更された場合、`g_dbg` による出力は変わりませんが、直接 `getenv` する SYCL 分岐は次の初期化またはウィンドウ末尾の判定時に反映されます（`engine/src/core/verify.cpp:124, 321`、`engine/sycl/src/core/verify.cpp:129, 136, 879, 991, 2758, 2843`）。

## 有効になる条件

- 実行ファイルが該当する Verifier 実装を含む必要があります。CUDA/HIP は `engine/src/core/verify.cpp`、SYCL は別実装の `engine/sycl/src/core/verify.cpp` を使用します（`engine/cmake/strata_gpu_engine.cmake:310-316`、`engine/sycl/CMakeLists.txt:34-41`）。
- CUDA/HIP では `STRATA_GPU_METAL` の Metal 経路も共通 `verify.cpp` をコンパイルしますが、Metal の `Verifier::run` は Metal 用処理の後に戻り、CUDA/HIP 用 `VDBG` の呼び出し箇所へ進みません。そのため、この変数による実効的な診断出力は確認できません（`engine/metal/CMakeLists.txt:135-140`、`engine/src/core/verify.cpp:3792-3819, 3847, 4291`）。
- SYCL の詳細な「window left behind」ダンプは、`no_host` が真で、かつ判定時にこの変数が設定済みの場合に限られます。`no_host` が偽でも初期化・時間ログや `VDBG` は別々の条件に従います（`engine/sycl/src/core/verify.cpp:2843-2863`）。
- OS、モデル、サーバーモード、CLI 引数による追加条件は、当該変数を読む箇所にはありません。

## 実行時の詳細

CUDA/HIP ではプロセス内で `g_dbg` を一度だけ初期化し、`VDBG` の各呼び出しで `stderr` に `verify dbg: ` 接頭辞付きの行を出して flush します。検証処理の捕捉後、staging 後、launch 後、各層が応答・処理された時、window 完了時などが対象です（`engine/src/core/verify.cpp:124, 321, 3847-3848, 3889, 3948, 4070, 4084, 4291`）。

SYCL では `VDBG` の進行ログに加え、Verifier 初期化時に device ID と各 queue 名を一度 `stderr` に出します（`engine/sycl/src/core/verify.cpp:879-890`）。設定ありで初期化すると、各層・token 0 の residual と mixed 値を保存するための device buffer を確保し、window graph にコピーを記録します（`engine/sycl/src/core/verify.cpp:991-994, 1856-1859`）。各 window 完了時には前回からの経過、staging、GPU の時間を出します（`engine/sycl/src/core/verify.cpp:2758-2763`）。`no_host` も真なら、host sequence、skip、layer 0 の重みと ID、residency、出力先頭値、および各種中間配列の統計値を device から読み戻して出力します（`engine/sycl/src/core/verify.cpp:2843-2899`）。

これらは診断ログ・診断用メモリとコピーを加える処理です。通常の verify 処理を選ぶ CLI 優先順位や、この変数に由来する明示的な警告・エラー・終了経路は見つかりません。SYCL の追加 device buffer 確保は戻り値を明示的に検査せず、後段の residual ladder 出力は `dbgR_` が有効な場合だけ行われます（`engine/sycl/src/core/verify.cpp:991-994, 2872-2886`）。

## ログと測定値

SYCL 初期化ログは `strata verify: init device ...`、window の進行ログは `verify dbg: captured; staging`、`verify dbg: staged; launching`、`verify dbg: launched`、`verify dbg: layer ... rang` / `served`、`verify dbg: window done` などです。window 時間ログは `verify dbg: T=%d window: since previous window ...` 形式です。no-host 状態ダンプは `verify dbg: window T=...` と各統計行を出します（`engine/sycl/src/core/verify.cpp:886-888, 136, 2398, 2449, 2610, 2689, 2717, 2758-2763, 2851-2863, 2869-2899, 2994`）。

CUDA/HIP の進行ログも `verify dbg: ` 接頭辞で、captured / staged / launched / layer rang / layer served / window done を出します（`engine/src/core/verify.cpp:321, 3847, 3889, 3948, 4070, 4084, 4291`）。これらは実行時の診断計時・状態であり、Strata 文書で条件付き測定値として裏付けられた性能測定値は確認できません。通常の window ログはこの変数が未設定なら出ません。

## 根拠

- `engine/src/core/verify.cpp:124, 321, 3847-3848, 3889, 3948, 4070, 4084, 4291` — CUDA/HIP 側の読み取り、キャッシュされたフラグと進行ログ。
- `engine/src/core/verify.cpp:3792-3819` — Metal 経路の早期 return。
- `engine/sycl/src/core/verify.cpp:129, 136, 879-890, 991-994` — SYCL 側のフラグ、初期化ログと診断用 buffer。
- `engine/sycl/src/core/verify.cpp:1856-1859, 2398, 2449, 2610, 2689, 2717, 2758-2763, 2843-2899, 2994` — SYCL の記録・進行・window 計時と条件付き状態ダンプ。
- `engine/cmake/strata_gpu_engine.cmake:310-316`、`engine/sycl/CMakeLists.txt:34-41`、`engine/metal/CMakeLists.txt:135-140` — 各 backend の source 構成。
