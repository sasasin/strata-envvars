# `STRATA_POOL_UMWAIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU expert pool の worker が仕事を待つ park ループで、一定時間の `_mm_pause` による spin を x86 WAITPKG の `UMONITOR` / `UMWAIT` に切り替える TSC cycle 数を指定する実験用設定です。worker は公開 epoch の cache line を監視し、仕事の公開で起きるか、指定 cycle の deadline で戻って epoch を再確認します。pool の仕事の割当や計算内容を変える設定ではありません。実装は `strata::kernels::cpu::umwait_cycles()` と `ExpertPool::worker()` です（`engine/src/kernels/cpu/pool.cpp:40-62,1062-1113`）。

## 値と判定

`std::getenv` の値を `std::atoll` に渡し、その戻り値が正の場合だけ有効候補とします。文字列全体の妥当性確認や範囲 clamp はありません。`atoll` が読む先頭の整数部分が使われるため、例として `" 12junk"` は 12、`"1e3"` は 1、数値で始まらない文字列と空文字は 0 になり無効です。正の整数 prefix だけが有効候補で、0・負数は無効です。大文字小文字は関係ありません。整数変換の範囲外入力の結果はコードで検査されません（`engine/src/kernels/cpu/pool.cpp:45-60`）。

| ビルド・CPU 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| MSVC x64（clang-cl を除く）、CPU が CPUID leaf 7 subleaf 0 の ECX bit 5（WAITPKG）対応 | 0 cycles。従来の spin | `1`、`5000`、または `12junk` のように `atoll` が正数を返す文字列 | 空文字、`0`、`-1`、`true`、`0anything`、整数で始まらない文字列 |
| 同ビルドだが CPU が WAITPKG 非対応 | 0 cycles。従来の spin | 正数は対応確認まで進むが、機能は無効 | 上記の無効値 |
| その他のビルド（Linux、macOS、非 MSVC、clang-cl、非 x64 など） | 0 cycles。従来の spin | 値は読み取られるが、実装が 0 を返すため有効にならない | 有効にならない |

## 有効になる条件

- `ExpertPool` worker が仕事待ちの park ループに入る必要があります。pool の生成・worker 起動経路は通常の generate で `engine/src/program/generate.cpp:9001-9008`、実際の待機分岐は `engine/src/kernels/cpu/pool.cpp:1062-1113` です。
- `UMONITOR` / `UMWAIT` を実行するのは `_MSC_VER && _M_X64 && !__clang__` のビルドだけです。CPU が WAITPKG 非対応なら無効化され、対応するビルドでもそれ以外では spin のままです（`engine/src/kernels/cpu/pool.cpp:49-60,1084-1103`）。CMake では pool 実装自体は CPU kernel library に含まれますが、CMake の包含だけではこのコンパイル条件を満たしません（`engine/cmake/backends/cpu.cmake:241-247`）。
- CLI 引数による値の上書きや別名の fallback はありません。`STRATA_POOL_UMWAIT_C02` は正の cycle 数で UMWAIT が動く場合に待機状態を選び、値の有効・無効を変えません。`STRATA_POOL_UMWAIT_ESC` が正なら park 開始からその cycle 数を超えるまで C0.1、その後 C0.2 に切り替えます（`engine/src/kernels/cpu/pool.cpp:64-72,1085-1096`）。
- `STRATA_POOL_SPIN_US` は UMWAIT の有効化には関与しませんが、worker が park 後に UMWAIT / spin を続けてから condition variable sleep に移る時間を変えます。既定は 20 ms で、環境変数があれば `atoi` を 0 以上に clamp した microseconds です（`engine/include/strata/kernels/cpu/pool.hpp:297-304`; `engine/src/kernels/cpu/pool.cpp:803-810,1104-1112`）。

## 実行時の詳細

`umwait_cycles()` は worker の park ループから呼ばれ、関数内 `static` 初期化で環境変数の値、CPU の WAITPKG 対応判定、結果を一度だけ取得・保持します。したがって設定は最初の呼び出し時点で固定され、その後プロセス内で環境を変更しても反映されません。複数 worker から呼ばれても同じ cache 値を使います（`engine/src/kernels/cpu/pool.cpp:45-62,1081-1088`）。

対応ビルドで値が正の場合、待ちループは epoch の cache line を `_umonitor` で監視し、UMWAIT の直前に epoch を読み直して既に仕事が公開されていたら待たずに抜けます。それ以外は現在の TSC 値に cycle 数を加えた deadline で `_umwait` し、最大 16 回の wait ごとに通常の pool loop 条件を確認します。値が未設定・0 以下、CPU 非対応、または対象外ビルドでは `strata_cpu_pause()` による従来の spin 分岐が使われます。park の合計経過時間が `spin_before_sleep_` 以上になると condition variable sleep へ移る既存経路も残り、この時間は既定 20 ms、`STRATA_POOL_SPIN_US` 設定時はその値に従います（`engine/include/strata/kernels/cpu/pool.hpp:297-304,378-383`; `engine/src/kernels/cpu/pool.cpp:803-810,1081-1113`）。この設定による失敗・終了経路は確認できません。

## ログと測定値

対応ビルドで正数が設定され、CPU が WAITPKG 非対応の場合、stderr に `strata: STRATA_POOL_UMWAIT: this CPU has no WAITPKG, the workers spin` を出します。CPU が対応している場合は stderr に `strata: STRATA_POOL_UMWAIT: parked workers wait with UMWAIT (%lld cycles)`（`%lld` は `atoll` の値）を一度出します。値が未設定または正数でない場合、対象外ビルドではこの設定固有のログは出ません（`engine/src/kernels/cpu/pool.cpp:47-60`）。`docs/DETAILS.md` に本変数の測定値は見つかりませんでした。

## 根拠

- 値の取得、static cache、変換、build/CPU 判定、ログ: `engine/src/kernels/cpu/pool.cpp:40-62`
- 補助変数の cache: `engine/src/kernels/cpu/pool.cpp:64-72`
- pool worker の park、UMONITOR/UMWAIT と従来 spin の分岐: `engine/src/kernels/cpu/pool.cpp:1062-1113`
- pool library へのソース包含: `engine/cmake/backends/cpu.cmake:241-247`
- park から condition variable sleep に移る既定時間と `STRATA_POOL_SPIN_US` の適用: `engine/include/strata/kernels/cpu/pool.hpp:297-304,378-383`; `engine/src/kernels/cpu/pool.cpp:803-810,1104-1112`
- generate からの pool 生成と pool 情報ログ: `engine/src/program/generate.cpp:9001-9008`
