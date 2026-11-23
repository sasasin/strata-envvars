# `STRATA_CPUEXP_SPIN_US`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CPU routed expert の thread pool で、仕事が来るまでの busy-spin と、呼び出し元が `CpuExperts::wait()` で完了を待つ busy-spin の上限時間をマイクロ秒単位で指定する。上限に達した後はそれぞれ condition variable で待つ。CPU expert の計算内容や割り当て先を選ぶ設定ではない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2132-2156,3128-3142`）。

値は `CpuExperts::Impl::start_threads()` の pool 起動時に一度読み、`Impl::spin_us` に保存する。未設定時はメンバー初期値の 300。設定値は worker thread と `wait()` の両方に使われ、起動時に stderr へ `spin <値> us` と表示される（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1521,2054-2072,2087-2094`）。

## 値と判定

`std::getenv` が null でない場合、文字列を `std::atoi` に渡し、その結果をそのまま採用する。空文字も設定済みとして `atoi("") == 0` になる。数値として読めない先頭（例 `true`）も 0、先頭の空白と符号の後にある数字は変換され、数字以降の文字列は無視される（例 `12ms` は 12）。文字列全体の妥当性検査、clamp、無効値の警告や fallback はない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2071`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `CpuExperts` の pool 起動時 | 300 µs | `1` → 1 µs、`300` → 300 µs、`12ms` → 12 µs | `0`・空文字・`true` → 0 µs、`-1` → -1 µs。無効値として拒否されず、変換結果が使用される |

しきい値は 0 より大きいかの検査ではなく、経過時間（µs）が `spin_us` より大きいかで判定する。したがって 0 または負値では、最初の 256 回単位の確認時に busy-spin を終えて待機へ移る。正値では、確認が 256 iteration ごとなので、実際の切替時刻は指定値と厳密には一致しない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2136-2152,3132-3140`）。

## 有効になる条件

- `hy4::CpuExperts` の `init()` が呼ばれ、読み込みが成功して `start_threads()` まで到達すること。値の読み取り自体に backend 固有の分岐はない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1700-1705,1863-1867,3059-3062`）。
- CUDA/HIP runner では CPU mask が空でない場合に初期化される（`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1565`）。SYCL の本番 graph も共通 `hy4_cpu_experts.cpp` をビルド対象にし、`ucx.init()` を呼ぶ（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:52-59`, `engine/src/hy4flash/sycl/sy_graph.h:204-215`）。
- 起動時の pool 初期化で読むため、pool 起動後にプロセス環境を変更しても既存 `CpuExperts` には反映されない。別の `CpuExperts` を新たに初期化すればその初期化時の値を読む（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2054-2072,3059-3062`）。
- `HY4_CPU_THREADS` は CUDA/HIP runner の thread 数を選ぶ別設定であり、この変数の値や優先順位は変更しない（`engine/src/hy4flash/run/hy4_graph.hip.h:1564-1565`）。この変数を設定する CLI 引数や別の値上書き経路は確認できなかった。

## 実行時の詳細

`start_threads()` は既定値 300 を持つ `spin_us` を環境変数があれば `atoi` の結果で置き換え、worker thread を作成する。worker は仕事がない間 `HY4_RELAX()` を実行し、256 iteration ごとに経過時間を確認する。時間がしきい値を超え、まだ仕事がなければ `cv_work.wait()` に入る。仕事完了側の `CpuExperts::wait()` も同じしきい値まで spin した後、`cv_done.wait()` する（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2071,2087-2094,2132-2156,3130-3142`）。

## ログと測定値

pool 初期化時、stderr に `[cpuexp] <thread数> pool threads... spin <値> us, sched=<値>, pf=<値> rows, l3_pf=<on|off>` の形式で出る。これは採用された数値の表示であり、しきい値の妥当性や実測待ち時間の報告ではない。parse 失敗や範囲外値に対する個別警告・エラー・終了経路はなく、Strata の資料にこの設定の測定値も見つからなかった（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2071,2092-2094`）。

## 根拠

- 候補名の実読み取り、設定値変換、関連する pool 初期化とログ: `engine/src/hy4flash/run/hy4_cpu_experts.cpp:2054-2094`
- worker の idle spin と condition-variable 待機: `engine/src/hy4flash/run/hy4_cpu_experts.cpp:2132-2156`
- 呼び出し元の完了待ち spin: `engine/src/hy4flash/run/hy4_cpu_experts.cpp:3130-3142`
- CUDA/HIP と SYCL 側の初期化条件: `engine/src/hy4flash/run/hy4_graph.hip.h:1552-1565`, `engine/src/hy4flash/sycl/sy_graph.h:204-215`
- UI 設定登録にも名前があるが、実際の値読み取り根拠は上記 C++ 実装: `terminal/data/settings-register.json:4441-4448`
