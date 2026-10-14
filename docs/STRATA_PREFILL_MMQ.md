# `STRATA_PREFILL_MMQ`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。調査対象リポジトリは `main`（調査開始時点で作業ツリー clean）。

## 役割

HIP 用にビルドされた prompt prefill の expert 行列積で、GGML MMQ（量子化重みの GPU 行列積）経路を使うかを実行時に選びます。実行時に無効なら、対象 expert の計算は FP16 重み経路へ回ります。環境変数と同名の CMake オプションもあり、こちらは MMQ 実装をバイナリへ組み込むかを決めます。実行時の環境変数だけでは、未ビルドの MMQ を有効にできません。

## 値と判定

実行時は `sycl/src/prefill/prefill.cpp` の `mmq_plan()` が `getenv()` と `std::atoi()` で判定し、初回呼び出し結果を関数内 static の plan に保持します (`:863-889`)。

| 実行時環境変数 | 結果 |
|---|---|
| unset | MMQ 実装がビルド済みなら有効。未ビルドなら無効 |
| `0`、空文字、数字で始まらない文字列 | `atoi` が 0 を返すため無効 |
| `1`、`-1`、`2abc`、先頭空白の後に非ゼロ整数がある文字列 | `atoi` が非ゼロを返すため有効 |
| `0abc`、整数変換できない文字列 | `atoi` が 0 を返すため無効 |

文字列全体の妥当性検証はなく、数値変換できた先頭部分で決まります。`mmq::built()` が false の場合は、環境変数が unset または非ゼロでも有効になりません。初回の `mmq_plan()` 評価後にプロセス環境を変えても、この plan は再評価されません。

同名のビルド設定は別の判定です。CMake の `STRATA_PREFILL_MMQ` は Boolean option で既定 `OFF`、`ON` にするには HIP が必要で、`STRATA_NATIVE_EXPERTS=ON` も必要です。これらの条件を欠くと CMake configure 時にエラーになります (`CMakeLists.txt:71-89,1263-1265`)。有効な HIP build では `strata_mmq` を作成・リンクして `STRATA_PREFILL_MMQ=1` を compile definition として付与します (`:1535-1579`)。

## 有効になる条件

- 実行バイナリに MMQ が組み込まれており (`mmq::built()`)、実行時環境変数の `atoi` 結果が非ゼロであること。
- MMQ plan はレイヤーごとに重み形式と行列形状を確認し、`mmq::fits()` が false のレイヤーは MMQ 対象にせず fallback 扱いにします (`sycl/src/prefill/prefill.cpp:873-886`)。
- 環境変数が有効でも、prompt path が選択されない、またはその layer の format/shape が MMQ に適合しない場合、その計算には MMQ は使われません。実際の expert 処理では `mmq_plan().layer[l]` を `use_mmq` として分岐します (`sycl/src/prefill/prefill.cpp:3223-3232,3435-3469,4015-4045`)。
- この実行時スイッチは dense GGUF projection の MMQ を直接有効化しません。dense path は `STRATA_DENSE_MMQ` を別途読み、`1` で始まる値のみを有効とします (`sycl/src/prefill/gemm.dp.cpp:872-881`)。

## 実行時の詳細

`mmq_plan()` は `expert_layout()` の各 layer の gate/up と down の型を取り出し、両方の matrix shape が MMQ 対応 (`fits`) ならその layer を MMQ 対象にします。plan に MMQ 対象がある場合、prompt prefill の MoE 処理が layer ごとに MMQ path を選びます。MMQ を使わない layer がある場合や全体を無効にした場合は、FP16 fallback 用 scratch を確保し、その path を使用します (`sycl/src/prefill/prefill.cpp:912-928,1203-1213,3223-3232`)。

設定読み取りは初回の `mmq_plan()` 呼び出し時であり、値はプロセス内で static cache されます。Strata のコードに、この runtime 変数を子プロセスへ転送・上書きする処理は見つかりませんでした。通常の親プロセス環境からの継承の有無は Strata 固有の実装としては扱いません。

## 文書との照合

`docs/STRIX_HALO.md:54-66` は `-DSTRATA_PREFILL_MMQ=ON` を HIP build 時に指定する手順として記述し、prompt experts 用 MMQ kernel をビルドすると説明しています。`docs/AMD_HIP_PERFORMANCE.md:13-27` は同じ綴りの `STRATA_PREFILL_MMQ=ON` を build 設定、`export STRATA_PREFILL_MMQ=1` を runtime 設定として分け、runtime で MMQ が opt-in と説明しています。これは CMake option と環境変数の二つの役割に対応します。Strata 同梱 `setup.py` の AMD build も `-DSTRATA_PREFILL_MMQ=ON` を CMake に渡します (`setup.py:3001-3007`)。

## 根拠

- CMake option の既定値と HIP/native-experts 条件: `CMakeLists.txt:71-89,1263-1265`
- HIP 向け MMQ source の組み込みと compile definition: `CMakeLists.txt:1535-1579`
- runtime env parse、static plan、layer format/shape 判定: `sycl/src/prefill/prefill.cpp:863-889`
- FP16 fallback scratch と MMQ plan の利用: `sycl/src/prefill/prefill.cpp:912-928,1203-1213,3223-3232`
- dense projection は別環境変数で制御: `sycl/src/prefill/gemm.dp.cpp:872-881`
- Strata の build / runtime 設定の説明: `docs/STRIX_HALO.md:54-66`, `docs/AMD_HIP_PERFORMANCE.md:13-27`
