# `STRATA_POOL_UMWAIT`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

CPU expert pool の worker が次の仕事を待つ間の spin 方式を、条件付きで `UMONITOR` / `UMWAIT` に切り替えます。通常の worker は `epoch_` が変わるまで `_mm_pause()` を繰り返します。有効時は `epoch_` のキャッシュラインを監視し、host による publish で値が変わるか、指定した TSC cycles 分待つたびに状態を確認します。対象は expert pool worker の待機ループです。host 側の `wait_parked()` / `wait_done()` などの待機までは切り替えません。

この変数は実験的な設定です。expert pool は通常の `generate` 経路と Qwen 3.6 CUDA engine から生成されますが、実際に CPU worker が仕事を待つ区間がなければ、設定しても UMWAIT による待機の機会はありません。

## 値と判定

値は `std::atoll()` で変換され、正の値だけが UMWAIT の待ち時間として使われます。文字列全体の検査や末尾の文字の検査はありません。

| 値 | 判定・結果 |
|---|---|
| 未設定 | 0 cycles として spin |
| 空文字、数値に変換できない文字列、変換結果が 0 以下 | spin |
| 正の整数として変換される文字列 | UMWAIT を有効化し、その cycles 数を待ち時間に使う |
| 数字の後ろに文字がある文字列 | `atoll()` が読める先頭部分が正なら有効（例: `1000junk`） |

`atoll()` は先頭の空白と符号を許容するため、たとえば `  +1000` は正の値として扱われます。小数点を含む値や、変換できない接頭部は正の値になりません。値の全体 parse、上限 clamp、範囲検証はありません。

## 有効になる条件

- `src/kernels/cpu/pool.cpp` が MSVC の x64 (`_MSC_VER` と `_M_X64`) でコンパイルされ、`__clang__` が定義されていない場合だけ、UMWAIT intrinsic の分岐に入ります。clang-cl を使う Windows HIP build を含むその他の build では、この変数が正でも spin のままです。
- 対応するコンパイラ build では、実行 CPU の CPUID leaf 7, subleaf 0 の ECX bit 5（WAITPKG）が必要です。未対応なら spin に戻り、stderr に `strata: STRATA_POOL_UMWAIT: this CPU has no WAITPKG, the workers spin` と出します。
- 対応コンパイラ・CPUの両方で値が正の場合、stderr に `strata: STRATA_POOL_UMWAIT: parked workers wait with UMWAIT (<cycles> cycles)` と出します。出力値も `atoll()` で変換した値です。

したがって、Linux や GCC/Clang build で値を設定しても、このソースの UMWAIT 分岐は使われません。未対応 build では診断ログも出ません。

## 実行時の詳細

`umwait_cycles()` 内の関数 static 初期化で環境変数を読みます。最初に worker がこの関数を呼んだ時点の値と CPUID 判定がプロセス内で共有され、以降の読み直しはありません。pool 作成後に環境変数を変更しても設定は反映されません。値が 0 なら worker は従来どおり `_mm_pause()` を使い、1024 回ごとに時刻を確認して `spin_before_sleep_` を超えると condition variable の sleep に移ります。UMWAIT が有効な場合、`epoch_` の値を確認してから `_umwait(state, now + cycles)` を呼び、最大で指定 cycles ずつ待ちます。16 回ごとに時刻の確認を行い、別の待機要因があれば従来の condition variable 経路へ移ります。

待機 state は別の `STRATA_POOL_UMWAIT_C02` と `STRATA_POOL_UMWAIT_ESC` にも影響されます。`STRATA_POOL_UMWAIT_ESC` が正なら、park 開始からその cycles に達する前は state `1`、達した後は state `0` を使います。そうでなければ `STRATA_POOL_UMWAIT_C02` の先頭文字が `1` の場合 state `0`、それ以外は state `1` です。ソースコメントでは state `1` を軽い C0.1、state `0` を深い C0.2 としています。これらの変数は待機時間を有効化する `STRATA_POOL_UMWAIT` の代わりにはなりません。

## 根拠

- `src/kernels/cpu/pool.cpp:33-55`: 目的、`atoll()` による値判定、MSVC x64 / WAITPKG の条件、stderr のログ、static cache。
- `src/kernels/cpu/pool.cpp:57-65`: C0.2 選択と段階的 state 変更の関連設定。
- `src/kernels/cpu/pool.cpp:529-584`: worker の park loop、epoch 監視、UMWAIT intrinsic の使用、pause / sleep への経路。
- `src/kernels/cpu/pool.cpp:475-504`: ExpertPool 作成時に worker thread を起動する箇所。
- `src/program/generate.cpp:5050-5055`: generate 経路の ExpertPool 作成。
- `src/qwen35/q36_engine.cu:2117-2128`: Qwen 3.6 engine の ExpertPool 作成と CPU thread 数のログ。
