# `STRATA_POOL_UMWAIT_ESC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU expert pool の worker が仕事を待つ際に、UMWAIT の待機状態を段階的に切り替える閾値（TSC cycles）です。UMWAIT を使う場合、park 開始からこの閾値までは軽い C0.1、閾値を過ぎると C0.2 を指定します。worker の仕事の割り当てや計算自体を変える設定ではありません。実装は `umwait_escalate()` と `ExpertPool::worker()` にあります（`engine/src/kernels/cpu/pool.cpp:68-73, 1081-1097`）。

## 値と判定

`std::getenv` で値の有無を調べ、設定されていれば `std::atoll` で変換し、`std::max(0LL, ...)` で負値を 0 にします。関数内 `static const` に変換結果を保存します。未設定は 0 です。空文字や数値として始まらない文字列も `atoll` の結果が 0 となるため無効です。先頭の空白と符号は `atoll` の変換規則に従い、数値の後ろにある文字は検査されません（例: `100cycles` は 100、`0anything` は 0）。`true` は数値として始まらないため 0 です。明示的な上限検査はありません。`atoll` が表現範囲外の文字列を受けた場合の結果は、このコードでは検査・規定されていません（`engine/src/kernels/cpu/pool.cpp:70-72`）。

| ビルド・実行条件 | unset / 0 相当 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| MSVC x64（clang-cl を除く）、CPU が WAITPKG 対応、かつ `STRATA_POOL_UMWAIT` が正値 | 閾値 0。段階切替なし | 正の整数（例: `1`, `100000`）。その TSC cycles 経過後に C0.2 へ切替 | 空文字、`0`, `0anything`, `true`, 負値。変換後 0 |
| 上記以外（他のビルド、WAITPKG 非対応、または `STRATA_POOL_UMWAIT` が正値でない） | 切替なし | なし。この変数単独では UMWAIT を有効化しない | すべて。ESC の値は待機処理に使われない |

## 有効になる条件

- `ExpertPool` worker が待機ループに入り、`_MSC_VER && _M_X64 && !__clang__` のコードがビルドされている必要があります。Linux 等の他ビルドでは ESC を取得する呼び出し自体がプリプロセッサ条件の外です（`engine/src/kernels/cpu/pool.cpp:1083-1101`）。
- `STRATA_POOL_UMWAIT` が正値で、CPU の CPUID leaf 7 ECX bit 5 が立ち、`umwait_cycles()` が非ゼロを返す必要があります。未設定・0 以下なら worker は `strata_cpu_pause()` の経路を使います。WAITPKG 非対応の場合も同じ経路になり、親設定側が警告します（`engine/src/kernels/cpu/pool.cpp:45-60, 1090-1102`）。
- ESC が 0 の場合、待機状態は `STRATA_POOL_UMWAIT_C02` の初期値で決まります。同変数が設定され、先頭文字が `'1'` なら C0.2、それ以外（未設定・空文字を含む）なら C0.1 です。ESC が正値の場合は閾値前後で状態を決めるため、`STRATA_POOL_UMWAIT_C02` は参照されません（`engine/src/kernels/cpu/pool.cpp:64-66, 1094-1096`）。
- generate 経路では `ExpertPool` を生成して worker を起動します。`--no-pool` は pool callback を無効にして pool を「UNUSED」と表示しますが、pool オブジェクト自体の生成より後で判定されるため、worker の待機ループは存在します（`engine/src/program/generate.cpp:9001-9008, 10479-10487`）。この環境変数に対応する CLI 引数や優先上書きはありません。

## 実行時の詳細

各 worker は仕事の epoch が変わるまで park します。UMWAIT 経路では epoch のアドレスを monitor し、epoch が変わっていないことを再確認した後、現在の `__rdtsc()` と park 開始時に記録した TSC 値との差で状態を選び、`_umwait(state, now + um)` を呼びます。`um`（`STRATA_POOL_UMWAIT` の周期）ごとに待ち直し、publish による epoch 更新を確認します。ESC は UMWAIT の期限ではなく、C0.1 から C0.2 へ切り替える経過周期です（`engine/src/kernels/cpu/pool.cpp:1081-1104`）。

`umwait_escalate()` の値は関数内 `static` に保存され、最初に MSVC worker が待機ループで呼んだ時点でプロセス内に一度だけ読み取られます。`umwait_cycles()` と `umwait_state()` もそれぞれ関数内 `static` で初回評価結果を保持します。したがって、初回評価後に同一プロセス内で環境を変更しても反映されません（`engine/src/kernels/cpu/pool.cpp:45-73, 1083-1086`）。

## ログと測定値

ESC 自体の有効化・閾値を示すログはありません。UMWAIT 親設定が有効な MSVC x64 経路では、`STRATA_POOL_UMWAIT` の初回評価時に `strata: STRATA_POOL_UMWAIT: parked workers wait with UMWAIT (%lld cycles)` を出します。CPU が WAITPKG 非対応の場合は `strata: STRATA_POOL_UMWAIT: this CPU has no WAITPKG, the workers spin` を出し、ESC の切替には入りません（`engine/src/kernels/cpu/pool.cpp:45-59`）。ESC の閾値による性能測定値は現行ソースと参照した `docs/DETAILS.md` では確認できません。

## 根拠

- `engine/src/kernels/cpu/pool.cpp:45-73` — UMWAIT 親設定・状態設定・ESC の値読み取りとキャッシュ。
- `engine/src/kernels/cpu/pool.cpp:1081-1104` — worker の park loop、TSC 閾値判定、UMWAIT と spin の分岐。
- `engine/src/program/generate.cpp:9001-9008, 10479-10487` — generate 経路の pool 生成と `--no-pool` 時の扱い。
