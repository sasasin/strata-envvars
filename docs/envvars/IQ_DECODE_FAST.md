# `IQ_DECODE_FAST`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

これは Strata の実行時設定ではなく、SYCL 版をビルドするときに使うシェル環境変数です。`sycl/tools/build.sh` と `packaging/build_sycl_linux.sh` が値を CMake の `STRATA_SYCL_IQ_DECODE_FAST` オプションへ渡します。CMake の既定値は ON で、ON の構成では Q2、IQ4、IQ3_S の decode helper 向けコンパイル定義を有効にします。実行中の Strata プロセスが `IQ_DECODE_FAST` を読む箇所はありません（全参照の内訳は後述）。

## 値と判定

| 環境変数 | スクリプトから渡される値 | 結果 |
|---|---|---|
| 未設定 | `ON` | CMake オプションの既定と同じく fast helper を有効化 |
| 空文字 | `ON` | `${IQ_DECODE_FAST:-ON}` の既定値を使う |
| `OFF` | `OFF` | CMake オプションを無効化し、以前の helper を使う |
| その他の非空値 | 文字列をそのまま CMake に渡す | このシェルスクリプトでは値を検査・変換しない。受理と真偽判定は CMake のオプション処理による |

`sycl/tools/build.sh` は `build.ninja` が既にあると CMake の初回 configure を省略するため、その build directory では後から指定した `IQ_DECODE_FAST` は読み直されません。同スクリプトはこの変数を使った既存 build cache の更新も行いません。対して `packaging/build_sycl_linux.sh` は毎回 CMake configure に変数を渡します。どちらもビルド時の評価であり、プロセス起動後の変更や CLI 引数との優先順位はありません。根拠: `sycl/tools/build.sh:38-45`, `packaging/build_sycl_linux.sh:39-46`。

## 有効になる条件

- 対象は `sycl/` の CMake プロジェクトを通る SYCL build です。CUDA/HIP や既にビルド済みの実行ファイルを実行するだけでは、この環境変数は参照されません（`sycl/CMakeLists.txt:21,34-39`）。
- CMake オプションが ON のとき、`STRATA_Q2_WORD_FAST`, `STRATA_IQ4NL_LUT_SWAR`, `STRATA_IQ4XS_LUT_SWAR`, `STRATA_IQ4_LUT_SWAR`, `STRATA_IQ3S_SIGN_FAST`, `STRATA_IQ3S_SIGN_APPLY_FAST` を定義します。OFF のときはこれらの定義を追加せず、各カーネルの `#ifndef` 既定値 0 により旧 helper 側になります（`sycl/CMakeLists.txt:35-39`; `sycl/src/kernels/cuda/iq_kernels.dp.cpp:105-122,169-190,416-433,488-506`; `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1894-1910`）。
- 実際に異なる helper を使うのは、それらの条件付き実装を含む SYCL カーネルです。ソースには runtime の環境変数チェックやモデル単位の追加 gate はありません。個々の量子化形式を使うかどうかはカーネル呼び出し側の処理経路によります。

## 実行時の詳細

`sycl/tools/build.sh` は環境変数を `-DSTRATA_SYCL_IQ_DECODE_FAST=...` として configure に渡し、CMake が ON のときだけコンパイル定義を追加します。Q2 decode は `q2_decode8()` の packed integer 経路、IQ3_S は sign mask/apply の整数式、IQ4_NL と IQ4_XS は SWAR lookup 経路へ切り替わります。native MMVQ の IQ4 lookup にも対応する条件分岐があります。OFF ではそれぞれ従来の実装へコンパイル時に切り替わります。根拠: `sycl/CMakeLists.txt:35-39`; `sycl/src/kernels/cuda/iq_kernels.dp.cpp:108-122,175-190,419-432,494-506`; `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1897-1910`。

Strata の SYCL 開発・配布手順では既定 ON と `IQ_DECODE_FAST=OFF` による旧 helper への切替を案内しています。`docs/INTEL.md:518-526` は2枚の Arc Pro B65、Qwen3.8-Flash-Next GSQ-RCO IQ3_S、全 expert resident、layer split、`--spec 2 --pipeline-windows 2`、int8 KV、AOT bmg-g31 の測定条件で、該当 build option を含む一連の変更について decode の差を記載しています。この測定は option 単独の効果を示すものではなく、ここでは環境変数の動作根拠として扱っていません。

この変数専用の実行時ログ、警告、失敗処理はありません。CMake configure や build 自体の出力・終了状態は各スクリプトのビルド処理によるもので、Strata 実行時にこの変数の値が出力されるコードは見つかりませんでした。

## 根拠

- `sycl/tools/build.sh:4,38-45`: 変数の案内、unset/empty 時の `ON` fallback、CMake への転送、既存 `build.ninja` 時に configure を省く条件。
- `packaging/build_sycl_linux.sh:39-46`: configure ごとの `ON` fallback と CMake への転送、続く build。
- `sycl/CMakeLists.txt:31-39`: CMake option の既定値と、ON 時に付加する6つのコンパイル定義。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:105-122,169-190,416-433,488-506`: Q2 decode、IQ3_S sign、IQ4_NL/IQ4_XS lookup の compile-time 分岐。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1894-1910`: native MMVQ の IQ4 lookup 分岐。
- `docs/INTEL.md:518-526`: build option の説明と測定条件（補足資料。実装の根拠ではない）。

`000_envvers.md` にある候補名の全参照を調べた結果、実コードでの参照は上記2つの SYCL build script に限られ、実行時の `getenv` / `os.environ` 読み取りはありませんでした。`sycl/tools/build.sh` のコメント (`:4`) と `docs/INTEL.md` (`:525`) にも記載がありますが、実際の転送は script の CMake 引数で確認しました。
