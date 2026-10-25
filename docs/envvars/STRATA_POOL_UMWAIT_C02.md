# `STRATA_POOL_UMWAIT_C02`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

CPU expert pool の worker が `UMWAIT` で待つときに、待機状態の選択を既定の C0.1 から C0.2 に切り替えます。この変数単独では `UMWAIT` を有効にしません。待機方式を有効にする `STRATA_POOL_UMWAIT` が正のサイクル数として解釈され、かつ対応するビルドと CPU 条件を満たした場合にだけ関係します。

## 値と判定

値全体や数値としての妥当性は検査しません。`std::getenv()` が返した文字列の先頭文字だけを比較します。

| 環境変数の状態 | `umwait_state()` の値 | 状態 |
|---|---:|---|
| 未設定 | 1 | C0.1（既定） |
| 空文字 | 1 | C0.1 |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | 0 | C0.2 |
| その他（例: `0`, `true`, ` 1`） | 1 | C0.1 |

大文字小文字の変換、空白除去、数値変換はありません。`umwait_state()` の結果は関数内の `static const unsigned` に保存され、初回評価後にプロセス内で環境変数を変更しても再評価されません。

## 有効になる条件

- `_MSC_VER`、`_M_X64` が定義され、`__clang__` が未定義のビルド（コードコメント上の MSVC proper x64）であること。UMWAIT 命令の分岐自体がこの条件でコンパイルされます。Linux、clang-cl を含むその他のビルドでは worker は `_mm_pause()` の spin 経路を使い、この設定は作用しません。
- `STRATA_POOL_UMWAIT` が設定され、その `std::atoll()` による変換結果が正であること。未設定または変換結果が 0 以下なら `umwait_cycles()` は 0 を返し、worker は spin 経路を使います。この場合 `umwait_state()` は呼ばれず、本変数も読み取られません。
- CPU の CPUID leaf 7 ECX bit 5（WAITPKG）が立っていること。対応ビルドで `STRATA_POOL_UMWAIT` が正でも bit が立っていなければ UMWAIT は無効のままです。
- `STRATA_POOL_UMWAIT_ESC` の変換結果が 0 であること。worker はこれが非 0 なら経過 TSC cycles によって C0.1 から C0.2 へ切り替える分岐を使い、`umwait_state()` を参照しません。従って、その場合は本変数の指定値による状態選択は行われません。

## 実行時の詳細

`generate` は CPU expert pool を生成し、その pool は CPU 上で expert job を処理する worker thread を起動します（`src/program/generate.cpp` と `src/kernels/cpu/pool.cpp`）。Q36 engine にも同じ `ExpertPool` 実装の利用箇所があります。

各 worker は仕事の epoch が変わるのを待つループで、まず `STRATA_POOL_UMWAIT` の値と WAITPKG 対応を `umwait_cycles()` から確認します。値が正であれば、epoch のメモリを `_umonitor()` で監視し、epoch がまだ変わっていなければ `_umwait(st, now + um)` を呼びます。`STRATA_POOL_UMWAIT_ESC` が 0 のとき `st` は `umwait_state()` の戻り値です。従って本変数は仕事の計算内容ではなく、worker の待機命令に渡す状態番号だけを変えます。epoch が変わるかサイクル期限に達すると待機ループが再確認されます。

環境変数の直接読み取り箇所は `pool.cpp` の `umwait_state()` 内の1箇所です。C++ の関数内 static 初期化により値を一度保存します。特別なログ出力はありません。`STRATA_POOL_UMWAIT` が正でも CPU が WAITPKG に対応しなければ stderr に `strata: STRATA_POOL_UMWAIT: this CPU has no WAITPKG, the workers spin` を出します。対応して有効になった場合のログは `STRATA_POOL_UMWAIT` 側が出すもので、C02 の値を表示するログではありません。

## 根拠

- `src/kernels/cpu/pool.cpp:33-37` — UMWAIT と C0.1/C0.2 の目的、ビルド条件に関する実装コメント。
- `src/kernels/cpu/pool.cpp:38-60` — `STRATA_POOL_UMWAIT` の値・WAITPKG 判定、C02 の先頭文字判定と状態番号。
- `src/kernels/cpu/pool.cpp:61-65` — `STRATA_POOL_UMWAIT_ESC` の値取得。
- `src/kernels/cpu/pool.cpp:475-504` — `ExpertPool` の生成と worker thread の起動。
- `src/kernels/cpu/pool.cpp:529-579` — worker の park loop、UMONITOR/UMWAIT と spin/sleep の経路。
- `src/program/generate.cpp:5050-5055` — generate 経路での CPU expert pool の生成。
- `src/qwen35/q36_engine.cu:2117-2126` — Q36 engine の CPU expert pool 利用。
- `docs/DETAILS.md:314-320` — CPU expert pool を decode timing で観測する説明。本変数固有の条件や測定値の説明は見当たりません。
