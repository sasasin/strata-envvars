# `STRATA_ISA_FLOOR`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。

## 役割

`setup.py` がエンジンをビルドするとき、CPU の最低 ISA（命令セット）に合わせて ggml-cpu を構成するための環境変数。`avx` は AVX（AVX2/FMA/F16C なし）、`none` は SSE4.2 + POPCNT の古い CPU 向けビルドを選ぶ。主な用途は通常の AVX2 対応ビルドが動かない CPU 向けの実験的ビルドと、新しい CPU 上でその構成を試すこと。

エンジン本体はこの名前を実行時に `getenv` していない。環境値を読むのは `setup.py` で、そこから CMake の `STRATA_ISA_FLOOR` キャッシュ変数へ渡す。手動 CMake ビルドでは環境変数ではなく `-DSTRATA_ISA_FLOOR=avx` または `none` を指定する。

## 値と判定

`setup.py` の `cpu_floor()` は値を `strip().lower()` してから判定する。

| 環境値 | setup の扱い |
|---|---|
| 未設定、空文字、空白だけ | CPU 機能を自動判定 |
| `avx`（大文字小文字不問、前後空白可） | CPU 自動判定を上書きし `avx` を選択 |
| `none`（大文字小文字不問、前後空白可） | CPU 自動判定を上書きし `none` を選択 |
| その他（例: `bogus`、`unsupported`） | エラーにはせず、その値を無視して CPU 自動判定へ進む |

自動判定では、AVX2 対応 CPU は通常構成（空文字）になる。AVX2 がない場合、Windows では CPUID/XCR0 を確認し、Linux などでは `/proc/cpuinfo` の `flags` を調べる。AVX があれば `avx`、なければ SSE4.2 と POPCNT の両方があれば `none`、どちらもなければ `unsupported` を返す。AVX2 の有無は `cpu_floor()` の引数として渡されるため、この変数の処理は setup の CPU 機能確認時に行われる。

## 有効になる条件

- 通常の CUDA または HIP エンジンを `setup.py` がビルドするときに `cpu_floor()` の結果を CMake 引数へ渡す。既存エンジンのビルド記録にある ISA floor と今回の値も比較し、異なる場合は既存エンジンを再利用しない。
- 明示値 `avx` / `none` は CPU 機能の自動判定結果より優先されるため、AVX2 対応 CPU 上でも古い floor のビルドを試せる。setup は CPU が AVX2 非対応の場合に古い CPU 向けの警告を出してソースビルドへ進む。AMD GPU の HIP エンジンは Windows 上の古い CPU 向け経路ではビルドできず、setup が案内付きで停止する。
- CMake は `STRATA_NATIVE_EXPERTS` が有効な構成で floor を適用する。空値は通常構成、`avx` / `none` 以外の CMake 値は configure 時の fatal error。floor と `STRATA_PORTABLE` の同時指定も fatal error。
- 古い floor ビルドは ggml-cpu を AVX または SSE4.2 に固定し、AVX2、FMA、F16C、BMI2、AVX-VNNI、AVX-512 などを ggml-cpu では無効にする。Strata 自身の AVX2 / AVX-512 カーネルはバイナリに残るが、実 CPU の機能検査を通る場合に限り選ばれる。実 CPU に AVX2 がない場合、ネイティブ expert の処理は ggml-cpu 側へ回る。モデル形式などによる制約は別途残る。
- `sycl/setup_intel.py` は `cpu_floor()` / `isa_floor_defs()` を通らないため、この setup 経路では同変数による floor 選択は確認できない。

## 実行時の詳細

setup 起動時に CPU 情報と AVX2 対応を確認し、`cpu_floor()` で選んだ値をエンジンビルド引数に加える。通常の CUDA / HIP エンジンではビルド記録にも非空 floor を保存し、次回 setup のビルド再利用判定に使う。エンジン実行後はコンパイル時定義 `STRATA_ISA_FLOOR_AVX` / `STRATA_ISA_FLOOR_NONE` からビルド種別を識別するため、実行時に環境変数を変更してもビルド構成は切り替わらない。

`src/program/generate.cpp` と `sycl/src/program/generate.cpp` の起動時検査は同じである。通常ビルドを AVX2 非対応 CPU で起動するとエラー終了する。一方 floor ビルドでは、実 CPU が選択された AVX または SSE4.2 + POPCNT を持つかを確認し、不足すればエラー終了する。条件を満たして AVX2 を持たない CPU なら、実験的ビルドで CPU expert を ggml-cpu が処理する旨を stderr に出す。AVX2 対応 CPU で floor ビルドを使うと、通常ビルドの方が速い旨のメッセージを出す。

文書 `docs/INSTALL.md` の「Older CPUs」節も、setup が古い CPU 向けにエンジンをビルドすること、CPU expert が ggml-cpu に移ること、手動 CMake 指定を説明しており、コードの現状と整合する。同節の速度値は Ryzen 5 7600 + RTX 5070、expert cache 1500 slots、Coder / IQ3_XXS、各10 prompts・1 run という資料記載の条件付き値であるため、本調査では一般的な性能値として扱わない。

## 根拠

- `setup.py:911-929` — 環境値の正規化、明示値判定、自動検出の規則。Windows 側検出の補助処理は `setup.py:880-909`。
- `setup.py:2977-3007`, `setup.py:3939-3961` — HIP / CUDA エンジンの再利用判定と CMake 引数への引き渡し。
- `setup.py:3868-3873` — floor が変わった場合の CMake cache の削除と `-DSTRATA_ISA_FLOOR=...` の生成。
- `setup.py:6073-6087` — setup 時の unsupported 判定、古い CPU 向け警告、AMD GPU + Windows の制約。
- `CMakeLists.txt:35-45`, `CMakeLists.txt:1270-1299`, `CMakeLists.txt:1355-1361` — CMake 値の許容範囲、portable との排他、ggml-cpu の ISA 固定と compile definition。
- `include/strata/kernels/cpu/expert_layout.hpp:49-61`, `src/kernels/cpu/expert_layout.cpp:145-195` — CPU 機能判定とコンパイル済み floor の識別。
- `src/program/generate.cpp:2761-2795`, `sycl/src/program/generate.cpp:2512-2540` — 両実装で共通する実行時の CPU 要件検査、エラーおよび診断ログ。
- `docs/INSTALL.md:145-172` — 利用者向け説明と測定条件。
