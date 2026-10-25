# `STRATA_NO_AVXVNNI`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。外部ライブラリの環境変数は対象外。

## 役割

AVX2 用にビルドされた Strata の CPU expert row kernel が、AVX-VNNI 命令を使う派生実装を選ぶかどうかを抑制します。対象は i-quant row、IQ4_NL の down row、Q2_0 row です。変数は AVX-VNNI 実装そのものをビルドから取り除かず、実行時の CPU 判定を false にして AVX2 の通常実装へ回します。AVX-512 の実装や ggml-cpu の dot を無効にする設定ではありません。

## 値と判定

`src/kernels/cpu/expert_layout.cpp` の `cpu_avxvnni_ok()` が `std::getenv()` で値を読み、`std::atoi(v) != 0` なら AVX-VNNI を使わない判定を返します。文字列全体を真偽値として比較する処理ではありません。

| 値 | 判定 |
|---|---|
| 未設定 | この変数による抑制なし。ビルドと CPU の機能条件を満たせば AVX-VNNI を使える |
| 空文字 | `atoi("")` は 0 なので抑制しない |
| 整数として 0 になる文字列（例 `0`, `0abc`, `abc`） | 抑制しない |
| 整数として 0 以外になる文字列（例 `1`, `-1`, `2`, `1abc`, ` 1`） | 抑制する |

`atoi` は先頭の空白と符号を許し、整数として読める先頭部分を変換します。したがって `true` は抑制せず、`false` も抑制しません。整数変換の範囲外入力に対する値はこのコードで定義されていないため、依存しないでください。

## 有効になる条件

変数が未設定、空、または `atoi` 結果が 0 でも、次の条件が必要です。

- コンパイラが AVX-VNNI intrinsic を利用でき、CMake が AVX-VNNI の派生 row 実装をビルドしていること。利用不可なら通常の AVX2 実装だけがビルドされます。
- CPU 機能判定が AVX2 を利用可能とし、CPUID leaf 7 subleaf 1 の EAX bit 4 が立っていること。
- `STRATA_FORCE_ISA` が ISA 上限を level 3 未満にしておらず、`STRATA_ISA_FLOOR` による旧 CPU 向け build でないこと。`STRATA_FORCE_ISA=avx2` も AVX-VNNI 判定を無効にします。
- 呼び出し側が該当する Strata CPU kernel 経路を選ぶこと。たとえば IQ4_NL down row は AVX2 対応、token 数が `STRATA_IQ_MT_MIN` 以上、かつ `STRATA_NO_IQ4NL` 未設定の場合に Strata の AVX2 kernel に入ります。i-quant row も native expert の形式対応と token 数条件を満たす必要があります。

AVX-512 対応形式は native expert の dispatch が AVX-512 row kernel を選べるため、この変数の AVX-VNNI 判定を経由しない場合があります。Q2_0 も AVX-512 が利用可能なら AVX-512 kernel が優先されます。CPU が AVX2 を使えない場合は下位 ISA または ggml-cpu の経路になり、この AVX-VNNI 切り替えは使われません。

## 実行時の詳細

実行時エンジンで環境変数を判定する箇所は `cpu_avxvnni_ok()` です。結果は関数内の `static const bool` に保存されるため、最初にこの判定が呼ばれた時点で固定されます。プロセス起動後に環境を変更しても再評価されません。別に、診断プログラム `iq_avx2_parity` が値を取得して表示しますが、その表示はエンジンの dispatch には関与しません。

- `iq_avx2.cpp` は `vnni_on()` からこの判定を使い、i-quant の gate/up と row dot、および IQ4_NL down row に AVX-VNNI variant を渡します。判定が false なら `plain` 名前空間の AVX2 実装を呼びます。
- `q2_avx2.cpp` は `q2_0_gguf_rows_multi_avx2_legacy()` から判定を使います。AVX-VNNI variant が選ばれなければ同じ処理の AVX2 row 実装に進みます。Q2_0 の bit-plane 経路が条件を満たす場合はそちらを使い、VNNI 選択は legacy row 経路内で行われます。
- ソースは、この環境変数を理由にしたログ、警告、エラーを出しません。
- `iq_avx2_parity` は値を `-`（未設定）または環境変数の文字列として標準出力に表示します (`src/kernels/cpu/iq_avx2_parity.cpp:528-534`)。

`docs/DETAILS.md` は `STRATA_NO_AVXVNNI=1` で i-quant、IQ4_NL、Q2_0 row の AVX-VNNI forms を止めると記載しています。実装では値が文字列全体の `1` 比較ではなく `atoi` の非ゼロ判定です。同資料の「AVX2 forms と同じ bits」「4–25% faster rows」という説明は資料上の主張として確認しましたが、この調査では測定を実施していません。

## 根拠

- 値の読み取り、`atoi` 判定、ISA 条件、CPUID 条件、static cache: `src/kernels/cpu/expert_layout.cpp:260-273`。
- AVX2 と AVX-VNNI の feature/build 条件と旧 CPU floor 判定の宣言: `include/strata/kernels/cpu/expert_layout.hpp:57-77`。
- AVX2 実行可否の ISA 上限、OSXSAVE/AVX 状態、CPUID 判定: `src/kernels/cpu/expert_layout.cpp:110-143`。
- AVX-VNNI intrinsic の build probe と `STRATA_AVXVNNI` 定義: `CMakeLists.txt:1227-1254,1317-1354`、SYCL build: `sycl/CMakeLists.txt:121-149,183-198`。
- i-quant / IQ4_NL の variant 選択と通常 AVX2 への fallback: `src/kernels/cpu/iq_avx2.cpp:369-383,456-500,503-520`、row 実装: `src/kernels/cpu/iq_avx2_rows.inl:1-28`。
- Q2_0 の variant 選択と通常 AVX2 への fallback: `src/kernels/cpu/q2_avx2.cpp:51-63,155-180`、row 実装: `src/kernels/cpu/q2_avx2_rows.inl:1-13`。
- native expert が i-quant AVX-512 / AVX2 経路を選ぶ条件、IQ4_NL down 経路: `src/kernels/cpu/native_expert.cpp:176-192,233-255`。
- Q2_0 の AVX-512 → AVX2 → AVX1 dispatch: `src/kernels/cpu/expert_layout.cpp:356-368`。
- 文書説明と記載測定: `docs/DETAILS.md:287-289`。
