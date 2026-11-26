# `IQ_DECODE_FAST`

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（2026-11-26 時点、`git status --short --branch` は `## main...origin/main` で未コミット変更なし）。

## 役割

SYCL エンジンをビルドするときに、混成 IQ3 デコード用のカーネルヘルパを「パック整数演算版（fast）」と「従来版」のどちらでコンパイルするかを選ぶ**ビルド時変数**。値を読むのは 2 本のビルドスクリプトだけで、どちらも CMake キャッシュ変数 `STRATA_SYCL_IQ_DECODE_FAST` にそのまま渡す（`engine/sycl/tools/build.sh:41`、`tools/packaging/build_sycl_linux.sh:51`）。コンパイル済みの `strata` バイナリはこの名前を読まない（リポジトリ全体で `getenv` による参照なし）。したがって実行時に設定しても挙動は変わらない。

CMake 側では `option(STRATA_SYCL_IQ_DECODE_FAST ... ON)` が ON のとき 6 個のコンパイル定義を付ける（`engine/sycl/CMakeLists.txt:55-59`）: `STRATA_Q2_WORD_FAST`、`STRATA_IQ4NL_LUT_SWAR`、`STRATA_IQ4XS_LUT_SWAR`、`STRATA_IQ4_LUT_SWAR`、`STRATA_IQ3S_SIGN_FAST`、`STRATA_IQ3S_SIGN_APPLY_FAST`。各定義はソース内の `#if` でヘルパ実装を切り替える（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:135-152`、同 `:199-220`、同 `:448-465`、同 `:520-538`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1785-1802`）。両実装が同時に走るのではなく、片方だけがコンパイルされる。

## 値と判定

読み取りはシェル（bash / sh）のパラメータ展開 `"${IQ_DECODE_FAST:-ON}"` であり、Strata 自身は文字列を parse しない。未設定と空文字はどちらも `ON` になり、前後の空白除去も値の検証もない。渡された文字列は CMake の `option()` にそのまま入り、on/off の最終判定は CMake の真偽規則に委ねられる。このオプションには検証エラーがない（`STRATA_SYCL_I8_ESIMD` の `FATAL_ERROR` に相当するものが無い。`engine/sycl/CMakeLists.txt:86-88` と比較）。

| 条件 | unset / 空文字 | OFF になる値 | ON になる値（例） |
|---|---|---|---|
| `engine/sycl/tools/build.sh` | `ON`（`:-` が補う） | `OFF`、`0`、`NO`、`FALSE`、`N`、`IGNORE`、`NOTFOUND`（CMake の偽定数、大小文字を問わない） | `ON`、`1`、`TRUE`、`yes`、`2`、`OFFF`、`off `（空白付き）など偽定数以外すべて |
| `tools/packaging/build_sycl_linux.sh` | `ON` | 同上 | 同上。ただし値は引用符なしで展開されるため空白入りの値は語分割される |

境界の要点: 空文字は「OFF」ではなく **ON**。`0` は OFF。CMake の偽定数に一致しない文字列（`0x0`、`disable`、`OFF` に余分な空白を付けたもの）は ON 扱い。既定値は両スクリプトとも ON で、CMake オプション自体の既定も ON（`engine/sycl/CMakeLists.txt:54-55`）。

## 有効になる条件

- SYCL エンジンのビルドであること。CUDA / HIP / CPU エンジンはこの CMake オプションを読まない（`engine/sycl/CMakeLists.txt` 配下のみ）。
- 対象は `engine/sycl/tools/build.sh` と `tools/packaging/build_sycl_linux.sh` の 2 経路だけ。手動の `cmake -S engine/sycl ...`（`docs/INTEL_ARC.md:103`）や CI の構成（`.github/workflows/backends.yml:157` は `=ON` 固定）では、この変数を経由せず CMake 既定またはリテラル値が使われる。
- 既存ビルドディレクトリでは反映されないことがある。`build.sh` は `$b/build.ninja` が無いときだけ configure するため（`engine/sycl/tools/build.sh:40-41`）、2 回目以降の実行で `IQ_DECODE_FAST` を変えても CMake には渡らない（再構成されるのは `I8_ESIMD` だけ。同 `:43`）。`build_sycl_linux.sh` は毎回 `cmake -S` を実行するので同じビルドディレクトリでも次の実行で反映される（`tools/packaging/build_sycl_linux.sh:50-51`）。
- AOT / JIT のどちらでも効く。GPU 機種やモデル、実行時 CLI、他の環境変数による分岐はない（`engine/sycl/CMakeLists.txt:56-59` は無条件）。

## 実行時の詳細

読み取りは configure 時の 1 回だけで、cache は CMake キャッシュ（`CMakeCache.txt` の `STRATA_SYCL_IQ_DECODE_FAST:BOOL`）に残る。プロセス起動後に環境変数を変えても、既存バイナリの挙動は変わらない（ランタイム参照が存在しない）。生成 token や選択結果は両実装で同一とされ（後述の資料）、変わるのはデコード用ヘルパの命令列だけである。

`build.sh` は値に引用符を付けて渡し、`build_sycl_linux.sh` は付けない（`engine/sycl/tools/build.sh:41`、`tools/packaging/build_sycl_linux.sh:51`）。後者で空白入りの値を渡すと余分な引数が CMake に渡る。両スクリプトとも `set -u` だが `:-` があるため未設定でも中断しない。

## ログと測定値

このオプションについて CMake の `message(STATUS)` は無く、on/off を示すログはビルド時に出ない（`STRATA_SYCL_I8_ESIMD` は出す。`engine/sycl/CMakeLists.txt:97`）。確認は `CMakeCache.txt` の値か、生成されたビルド規則の `-DSTRATA_Q2_WORD_FAST=1` 等の有無で行う。

`docs/INTEL.md:584-590` の記載（資料側の主張であり再測定はしていない）: 2 台の Arc Pro B65、Qwen3.8-Flash-Next GSQ-RCO IQ3_S、全 expert resident、layer split、`--spec 2 --pipeline-windows 2`、int8 KV、AOT bmg-g31 の条件で、4K prompt のデコード +9.7%、自由文応答 +11.1%、このオプション単独で +5.9%。生成 token と logprob（小数 6 桁）は同一、prompt 速度は不変。同資料は `IQ_DECODE_FAST` を「`engine/sycl/tools/build.sh` と `tools/packaging/build_sycl_linux.sh` 向け」と明記しており、コードと一致する。

`000_envvers.md:527` は `IQ_DECODE_FAST` を候補として挙げるが、実体はランタイム設定ではなく上記 2 スクリプトが環境から受け取るビルド用変数である（外部ライブラリが読む名前ではない）。

## 根拠

- `engine/sycl/tools/build.sh:4`（用途コメント）、`:40-41`（初回 configure のみ）、`:43`（再構成は I8_ESIMD のみ）
- `tools/packaging/build_sycl_linux.sh:50-51`（毎回 configure、引用符なし展開）
- `engine/sycl/CMakeLists.txt:52-59`（option 既定 ON と 6 個の compile definition）、`:86-88`、`:97`（検証と STATUS ログの有無の比較）
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:135-152`、`:199-220`、`:448-465`、`:520-538`
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1785-1802`
- `docs/INTEL.md:584-590`（測定条件と数値）、`docs/INTEL_ARC.md:103`（手動 configure 例）
- `.github/workflows/backends.yml:157`（CI は `=ON` 固定）
