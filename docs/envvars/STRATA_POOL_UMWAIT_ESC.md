# `STRATA_POOL_UMWAIT_ESC`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

CPU expert pool の worker が UMWAIT で待機するとき、待機開始から指定した TSC サイクル数が経過した後に使う wait state を切り替えます。しきい値より前は state `1`、しきい値以後は state `0` を `_umwait` に渡します。ソースコメント上の対応はそれぞれ C0.1 と C0.2 です。

この変数単独で UMWAIT を有効にはしません。`STRATA_POOL_UMWAIT` が正の値として認識され、対象ビルドで UMWAIT 分岐が実行される必要があります。

## 値と判定

値は `std::atoll` で符号付き整数として読み、その結果と `0LL` の大きい方を `uint64_t` にします。文字列全体の厳密な検証はしません。

| 設定 | `umwait_escalate()` の値 |
|---|---:|
| 未設定 | `0` |
| 空文字、数値に変換できない文字列 | `0` |
| 0 または負数 | `0` |
| 正数 | その値（TSC サイクル数） |
| 数字の後ろに文字が続く値（例: `2500xyz`） | 数字の先頭部分を変換した値 |

`atoll` の通常の変換規則により、先頭の空白と符号は許されます。たとえば `+2500` は `2500`、`-2500` は 0 になります。正のしきい値が得られた場合、worker はその park の開始時に `__rdtsc()` を記録し、以後の各 UMWAIT 前に経過サイクル数を比較します。しきい値に達するまでは state `1`、達した後は state `0` を選びます。

## 有効になる条件

- 読み取り値は `src/kernels/cpu/pool.cpp` の MSVC x64（`_MSC_VER` と `_M_X64` が定義され、`__clang__` が未定義）の worker wait loop で使われます。Linux などこの条件を満たさないビルドでは helper の呼び出しと `_umwait` 分岐がコンパイル条件から外れ、この変数は動作に影響しません。
- UMWAIT の実行には別変数 `STRATA_POOL_UMWAIT` が正値として認識される必要があります。この値が未設定・0・負数なら `um` が 0 となり、ESC の値が正でも worker は `_mm_pause()` の経路を使います。
- `STRATA_POOL_UMWAIT` が正でも、コードが CPUID leaf 7, subleaf 0 の ECX bit 5 を確認して WAITPKG がないと判断した場合は、`um` が 0 となって spin 経路に戻ります。この場合は stderr に `strata: STRATA_POOL_UMWAIT: this CPU has no WAITPKG, the workers spin` を出します。
- `STRATA_POOL_UMWAIT_ESC` が 0 の場合は別変数 `STRATA_POOL_UMWAIT_C02` の判定に進みます。ESC が正なら同変数は state 選択に使われず、ESC のしきい値に従って state が切り替わります。

## 実行時の詳細

設定値は `umwait_escalate()` 内の関数ローカル `static const` に保存されます。最初の呼び出し時に一度だけ読み取られ、プロセス実行中の環境変数変更は再評価されません。MSVC x64 では worker の park loop に入る際に helper が呼ばれますが、ESC が正でも `um == 0` なら `__rdtsc()` による計時と state 切り替えは行われません。

ESC が正で UMWAIT が有効な場合、worker は `epoch_` の値を監視しながら、各回 `_umwait(state, now + um)` を呼びます。`um` は各 UMWAIT 呼び出しの期限として使われ、ESC は C0.1 から C0.2 に切り替わる累積待機時間のしきい値として使われます。host が epoch を更新した場合は worker が park を抜けて処理へ進みます。通常の spin 待機時間を過ぎても仕事が来なければ、既存の condition variable による sleep 経路へ移ります。

ESC 自体についてのログ出力はありません。WAITPKG があり UMWAIT が開始されたときに出る `strata: STRATA_POOL_UMWAIT: parked workers wait with UMWAIT (%lld cycles)` は、基底となる `STRATA_POOL_UMWAIT` のログです。`docs/DETAILS.md` にこの ESC 変数の値や測定条件の説明は見当たらないため、性能効果は記載しません。

## 根拠

- `src/kernels/cpu/pool.cpp:61-66`: ESC の意図、`std::atoll` と非負 clamp、既定値。
- `src/kernels/cpu/pool.cpp:38-55`: `STRATA_POOL_UMWAIT` の parse、WAITPKG の CPUID 判定、stderr のログ。
- `src/kernels/cpu/pool.cpp:57-59`: ESC が 0 のときに使う `STRATA_POOL_UMWAIT_C02` の判定（先頭文字が `'1'` の場合だけ state 0）。
- `src/kernels/cpu/pool.cpp:546-572`: worker の park loop、ビルド条件、開始時刻の記録、しきい値による state 選択、UMWAIT と spin の各経路。
- `src/kernels/cpu/pool.cpp:573-579`: park 待機が続いた場合の condition variable 経路。
- `CMakeLists.txt:1213-1214`: `pool.cpp` が CPU kernels library のソースとして組み込まれる箇所。
- `src/program/generate.cpp:5050`、`sycl/src/program/generate.cpp:4368`: engine の生成経路で `ExpertPool` を構築する箇所。
