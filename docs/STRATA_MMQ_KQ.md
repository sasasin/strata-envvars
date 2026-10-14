# `STRATA_MMQ_KQ`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。調査開始時の作業ツリーは `main...origin/main` で変更表示なし。外部ライブラリ自身が読む環境変数の動作は対象外。

## 役割

Q4_K、Q5_K、Q5_1、Q6_K 形式の routed expert の prompt 計算を、FP16 経路ではなく MMQ（整数化した activation と量子化 weight を使う行列積）に渡すための実行時 opt-in です。MMQ のビルドだけではこの K-quant 経路は有効にならず、この変数の判定に加えてモデル形式、ビルド構成、MMQ の tile 対応などが必要です。MMQ 経路は FP16 経路と丸めが異なります。

Qwen 3.5 Q36 専用 engine は、未設定の場合この変数を `1` にしてからモデルを読み込みます。したがって同 engine では通常の既定値とは異なり、明示的に設定済みならその値を保持します。

## 値と判定

一般の MMQ 実装は文字列全体や数値を parse せず、`getenv()` の戻り値の先頭文字が `'1'` かだけを判定します。`STRATA_MMQ_KQ=1`, `10`, `1anything` は有効、`0`, `true`, 空文字、未設定は無効です。空白や大文字小文字の正規化もありません。CUDA の動的ライブラリ構成では `wanted()` が同じ先頭文字判定を行い、結果を `static const bool` に保存します。HIP などライブラリを分離しない構成では `kq_ok()` が同様に結果を static cache します。いずれも初回評価後にプロセス環境を変えても再判定しません。

| 状態 | 一般の MMQ 経路 | Qwen 3.5 Q36 専用 engine |
|---|---|---|
| 未設定 | 無効 | engine が `1` を設定する |
| 先頭文字が `1` | 有効要求 | その値を保持し、有効要求 |
| その他（空文字を含む） | 無効 | その値を保持し、無効要求 |

POSIX では `setenv("STRATA_MMQ_KQ", "1", 0)`、Windows では `getenv()` が null の場合だけ `_putenv_s()` を呼びます。明示された空文字も「設定済み」なので、Q36 engine は上書きしません。根拠: `src/prefill/moe_mmq.cu:23-36`, `src/prefill/mmq_kq_loader.cpp:108-116`, `src/qwen35/q36_engine.cu:2403-2410`。

## 有効になる条件

- ビルドに K-quant MMQ 実装が含まれる必要があります。CMake option `STRATA_MMQ_KQUANTS` は既定 ON で、OFF なら該当する `supported()` 分岐・kernel dispatch がコンパイルされません (`CMakeLists.txt:73-79,1469-1477`; `src/prefill/moe_mmq.cu:200-220,358-372`)。
- 対象 weight が Q4_K / Q5_K / Q5_1 / Q6_K である必要があります。他形式に対する `supported()` の結果はこの変数では変わりません。
- CUDA では K-quant kernel の共有ライブラリ `libstrata_kq.so` または `strata_kq.dll` が engine と同じディレクトリにあり、engine と ABI が一致し、各可視 CUDA GPU で初期化できる必要があります。要求値が有効でもライブラリがない、ABI が違う、初期化に失敗した場合は K-quant expert は FP16 prompt 経路に戻ります。診断は stderr に出ます (`src/prefill/mmq_kq_loader.cpp:58-98`)。
- MMQ の型・shape が使用 GPU の tile と共有メモリ条件を満たさない場合も、その積は非-MMQ 経路になります。`fits()` は型ごとに利用可能 tile を確認します (`src/prefill/moe_mmq.cu:224-245`)。
- Qwen 3.5 Q36 専用 engine では、この変数とは別に `STRATA_Q36_NO_MMQ` が設定されていると、その値が空文字でも MMQ 全体が無効です。また全 layer と MTP block（存在する場合）の weight が `supported()` / `fits()` を満たす必要があります。いずれかを満たさなければ専用 engine は native grouped kernels を選びます (`src/qwen35/q36_engine.cu:1168-1191`)。
- HIP の dense GGUF projection に MMQ を使う条件は別の `STRATA_DENSE_MMQ` です。この変数だけでは dense 経路を有効にしません (`src/prefill/gemm.cu:812-828`)。

## 実行時の詳細

CUDA の分離ライブラリ構成では、K-quant 形式をモデルから確認した時に `mmq::supported()` が呼ばれ、変数が有効なら共有ライブラリを開きます。ライブラリの場所は実行ファイルの隣で、環境変数による探索パス指定はありません。ABI/API を確認してから、現在の CUDA device を保存し、engine が認識する各 GPU で kernel 初期化を試み、最後に元の device に戻します。成功時は `strata: K-quant prompt kernels from ... (STRATA_MMQ_KQ=1)`、失敗時はライブラリ不在・別バージョン・GPU 初期化失敗の理由と FP16 fallback を stderr に出します (`src/prefill/mmq_kq_loader.cpp:34-47,58-98`)。

MMQ 実行時、`moe_mmq.cu` は Q4_K / Q5_K / Q6_K / Q5_1 を K-quant library に dispatch します。呼び出しが非ゼロのエラーを返した場合は `prefill mmq: the K-quant library failed on type ...` を stderr に出して終了します (`src/prefill/moe_mmq.cu:334-383`)。ライブラリを分けないビルドでは同じ形式が engine 内の template kernel に dispatch されます。

setup.py は Unsloth の UD-Q5_K_XL と UD-Q6_K_XL の run config に `STRATA_MMQ_KQ=1` を書き込みます。UD-Q4_K_XL には自動設定しません。設定作成は `unsloth_default_env()` によるもので、変数自体の一般的な起動時意味とは別です (`setup.py:2272-2287,6728-6735`)。Q36 engine の自動設定は上記の通り別の実装です。

## 根拠

- 読み取りと parse、static cache: `src/prefill/moe_mmq.cu:23-36`, `src/prefill/mmq_kq_loader.cpp:108-116`。
- 型対応・tile 条件・実行 dispatch: `src/prefill/moe_mmq.cu:200-245,334-383`。
- CUDA library の探索、ABI 照合、GPU 初期化、ログと fallback: `src/prefill/mmq_kq_loader.cpp:34-47,58-98`。
- モデル読込前の型確認: `src/program/generate.cpp:2812-2830`。
- Q36 専用 engine の値設定と MMQ 選択条件: `src/qwen35/q36_engine.cu:2403-2410,1168-1191`。
- ビルド option と Unsloth 設定生成: `CMakeLists.txt:73-79,1469-1481`; `setup.py:2272-2287,6728-6735`。
- 設計資料も、CUDA では隣接ライブラリを対象形式かつ opt-in 時だけ開き、なければ FP16 prompt 経路へ戻ること、MMQ の丸めが FP16 と異なることを説明しています (`docs/QUANTS.md:45-54`)。資料内の性能・品質値は本調査では再測定していません。
