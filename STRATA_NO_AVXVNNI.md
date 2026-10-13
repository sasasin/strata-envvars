# `STRATA_NO_AVXVNNI`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

AVX2 CPU カーネル内にコンパイルされた AVX-VNNI 版の使用を抑止する変数です。Strata が CPU の AVX-VNNI 機能を検出し、かつ対応する VNNI カーネルをビルドしている場合に、その版へ切り替えるかを制御します。設定が有効でも AVX-VNNI を強制することはありません。

対象となるのは i-quant の AVX2 gate/up・row カーネル、IQ4_NL down row カーネル、Q2_0 AVX2 row カーネルです。AVX2 の通常版は引き続き利用できます。Strata の `docs/DETAILS.md` はこれらの AVX-VNNI 形式が AVX2 形式と同じビットを出すと説明しています。

## 値と判定

`src/kernels/cpu/expert_layout.cpp` の `cpu_avxvnni_ok()` が、初回呼び出し時に `std::getenv("STRATA_NO_AVXVNNI")` を読み、設定されていれば `std::atoi(v) != 0` かを判定します。この関数の結果は関数内の `static const bool` に保存され、以後は環境変数を変更しても再評価されません。

| 値 | `atoi` の結果 | 抑止 |
|---|---:|---|
| 未設定 | 判定しない | しない。CPU・ビルド条件で自動判定 |
| 空文字、数値に変換できない文字列（例: `false`） | 0 | しない。CPU・ビルド条件で自動判定 |
| 整数部分が0の文字列（例: `0`, `0abc`, `0.5`） | 0 | しない。CPU・ビルド条件で自動判定 |
| 先頭の空白・符号の後に0以外の整数がある文字列（例: `1`, `-1`, `  +2tail`） | 0以外 | 抑止する |

これは文字列全体の比較ではありません。先頭から `atoi` が読み取れる整数部分で判断するため、`1anything` も抑止値です。大文字小文字や真偽値の語は特別扱いされません。

## 有効になる条件

環境変数が未設定または `atoi` の結果が0でも、次の条件がそろわなければ AVX-VNNI 版は選ばれません。

- ビルド時にコンパイラが必要な AVX-VNNI intrinsic を受け付け、`STRATA_AVXVNNI=1` として VNNI 版がコンパイルされていること。CMake は機能をコンパイル検査し、未対応なら `STRATA_AVXVNNI=0` とします（通常の CMake と SYCL CMake の設定）。
- `STRATA_ISA_FLOOR` を使った `avx` / `none` の旧 CPU 向けビルドではないこと。
- `STRATA_FORCE_ISA` による上限が既定（3）であること。`avx2` は上限2のため VNNI を無効にします。
- 実 CPU が AVX2 の実行条件を満たし、CPUID leaf 7 subleaf 1 の EAX bit 4（AVX-VNNI）が立っていること。AVX2 判定では CPUID の AVX2・FMA・F16C と OS の YMM 状態保存も確認します。

カーネルの上位選択条件も別に適用されます。Q2_0 は `q2_rows_any()` が AVX-512 を先に選ぶため、AVX-512 経路に入った場合、この変数はその経路を変更しません。AVX2 経路に入った場合は VNNI 版を抑止して通常の AVX2 row に進みます。i-quant と IQ4_NL も、Strata 独自 AVX2 カーネルが形式・トークン数などの選択条件を満たす場合に限って、この VNNI 判定を通ります。

## 実行時の詳細

`cpu_avxvnni_ok()` は最初に `STRATA_NO_AVXVNNI` を評価し、抑止値なら CPU 機能検査をせず `false` をキャッシュします。抑止されない場合、CPU・ISA 上限を確認して CPUID の AVX-VNNI bit を読みます。Strata はこの関数から環境変数に関するログや警告を出しません。

IQ 系では `iq_avx2.cpp` の `vnni_on()` がビルド時の `STRATA_AVXVNNI` と `cpu_avxvnni_ok()` を組み合わせます。真なら i-quant の variant に VNNI bit を含め、IQ4_NL down rows でも同じ判定で `vnni::` 実装へ進みます。偽なら `plain::` AVX2 実装が選ばれます。Q2_0 では AVX2 wrapper が同じ CPU 判定を行い、偽なら `plain::rows_nt` を実行します。

したがって、設定をプロセス起動後に追加・変更する運用は反映される保証がありません。プロセス起動前に値を設定してください。

## 根拠

- 値の読み取り、整数変換、static cache、ISA floor・CPU feature 判定: `src/kernels/cpu/expert_layout.cpp:252-264`。
- AVX2 と ISA 上限の判定: `src/kernels/cpu/expert_layout.cpp:25-38,106-137,180-188`。
- CMake の AVX-VNNI コンパイラ機能検査と定義: `CMakeLists.txt:1174-1201,1298-1303`、`sycl/CMakeLists.txt:127-147,189-191`。
- Q2_0 の AVX-512 / AVX2 / AVX1 選択と、AVX2 wrapper の VNNI / 通常版選択: `src/kernels/cpu/expert_layout.cpp:348-360`、`src/kernels/cpu/q2_avx2.cpp:155-169`。
- i-quant / IQ4_NL の VNNI variant・実装選択: `src/kernels/cpu/iq_avx2.cpp:383,456-490,503-520`。
- native expert 経路の形式・トークン数等の上位条件: `src/kernels/cpu/native_expert.cpp:136-180,199-224`。
- 文書との照合: `docs/DETAILS.md:272-274` は、AVX-VNNI 形式の対象と、AVX2 形式と同じビットであること、および「4-25% faster rows」と記しています。この範囲の測定条件は同箇所に記載されていないため、ここでは性能値を一般化しません。
