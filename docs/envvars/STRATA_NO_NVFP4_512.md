# `STRATA_NO_NVFP4_512`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。Strata 所有ソースを対象とし、外部ライブラリ内部の動作は対象外。

## 役割

NVFP4 native expert の CPU 行計算で、Strata の AVX-512 kernel を無効化する診断・fallback 用スイッチです。対象は native expert CPU pool の gate/up 行と down 行です。無効化後は、条件を満たせば Strata の AVX2 kernel が選ばれ、それも使えなければ ggml-cpu の `vec_dot` に進みます。GPU 上の NVFP4 計算を無効にする変数ではありません。

native expert は `STRATA_NATIVE_EXPERTS` build option が有効な構成でビルドされ、CPU pool が native expert の行を処理する経路です。CMake の既定は `STRATA_NATIVE_EXPERTS=ON` です。

## 値と判定

変数の値は parse されず、`std::getenv(...) == nullptr` かどうかだけを見ます。

| 設定 | AVX-512 kernel の許可判定 |
|---|---|
| 未設定 | CPU probe が AVX-512対応と判定すれば許可 |
| `1` など任意の設定値 | 無効 |
| `0` | 無効 |
| 空文字 | 無効（環境変数が存在するため） |

文字列、数値としての妥当性、大文字小文字は判定しません。値を設定するだけで無効になるので、`STRATA_NO_NVFP4_512=0` も無効化指定と同じです。

## 有効になる条件

変数が未設定でも、次の条件が必要です。

- native expert CPU kernel がビルドに含まれる。
- 対象 projection の型が NVFP4 (`kNvfp4Type`) である。
- `cpu_avx512_ok()` が true を返す。CPU/OS の probe は AVX-512F、BW、VL、VNNI、VBMI の feature bits と OSXSAVE、XCR0 の AVX-512 state 保存を確認する。
- 行幅 `n` が64値単位の整数個のブロックで、AVX-512 kernel の上限64ブロック以下である（`n % 64 == 0` かつ `n / 64 <= 64`）。

CPU probe はさらに `STRATA_FORCE_AVX2` が先頭文字 `1` の場合、または `STRATA_FORCE_ISA` が `avx2` / `avx` / `sse` / `sse4.2` / `none` の場合、AVX-512を許可しません。`STRATA_FORCE_ISA` は文字列全体を比較し、空文字は既定の上限値にします。無効な非空値は stderr に `strata: STRATA_FORCE_ISA=%s is not avx2, avx or sse; ignored` を出して既定に戻ります。

## 実行時の詳細

`native_gu_rows()` と `native_down_rows()` はそれぞれ関数内の `static const bool` として AVX-512可否を初回評価します。プロセス実行中に環境を書き換えても、各関数で評価済みの判定は変わりません。環境変数は最初の native expert 行計算より前に設定する必要があります。CPU feature probe 自体も static cache されます。

未設定かつ CPU probe と行幅条件を満たす gate/up 行では `nvfp4_512_gu_rows()`、down 行では `nvfp4_512_rows()` を呼びます。AVX-512 kernel は64値ブロックを複数 token に適用し、gate/up では blob tail の gate/up scale、down では down scale を使います。1回の呼び出しで token 数が7を超える場合は、kernel 内で最大7 token の slice に分けます。

変数を設定するか、CPU・幅条件が合わない場合、実装は続けて `STRATA_NO_NVFP4_256` が未設定で CPU AVX2 対応かつ幅条件を満たすか確認します。該当すれば AVX2 kernel を実行します。それ以外は各 row/token について ggml-cpu の `vec_dot` を呼び、down 行ではその結果に down scale を乗じます。`STRATA_NO_NVFP4_256` も設定されている場合、AVX2への fallback は行いません。

この変数自体によるログ出力はありません。`docs/NVFP4.md` は AVX-512経路を ggml-cpu fallback と比較した測定として、cache-resident な1 expert の gate+up（2560値、1280行）で1 token時1.76倍、4 token時3.29倍、7 token時3.66倍と記載しています。これは同資料の測定条件での値で、一般的な CPU pool の速度保証ではありません。

## 根拠

- 読み取り、gate/up の dispatch、AVX2 / ggml-cpu fallback: `src/kernels/cpu/native_expert.cpp:194-229`。
- down 行の dispatch、scale適用と fallback: `src/kernels/cpu/native_expert.cpp:257-277`。
- pool が native gate/up・down 行処理を呼ぶ箇所: `src/kernels/cpu/pool.cpp:705-719`。
- NVFP4 AVX-512幅条件と複数token slice: `src/kernels/cpu/nvfp4_avx512.cpp:152-180,183-198`; 上限の説明: `include/strata/kernels/cpu/nvfp4_avx512.hpp:14-15`。
- CPU/OS feature probe と `STRATA_FORCE_ISA` / `STRATA_FORCE_AVX2` の影響: `src/kernels/cpu/expert_layout.cpp:25-38,41-73`。
- native expert option とAVX-512 sourceのビルド設定: `CMakeLists.txt:107,1270-1277,1317-1323,1337-1342,1360-1361`。
- 測定条件と fallback 説明: `docs/NVFP4.md:166-180`。
