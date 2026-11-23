# `STRATA_CPUEXP_COLD_IO`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash の CPU expert pool が cold expert の本体を `.strata` ファイルから読むとき、`ColdStore` の I/O モードを選びます。値は cold expert の割り当てや CPU/GPU 配置を決めず、cold expert が存在して `CpuExperts::Impl::set_cold` が `ColdStore` を開く場合にだけ使われます。未設定時の基本モードは direct I/O です（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2699-2736`）。

HIP の `strata-hy4` では `--ssd-experts` がこの環境変数を `direct` に上書きします。SYCL では Linux 上で cold 領域が 12,000,000,000 bytes 未満の場合、環境変数が未設定なら `buffered` を設定します（`engine/src/hy4flash/run/hy4_main.hip.cpp:460-466`、`engine/src/hy4flash/sycl/sy_graph.h:217-227`）。

## 値と判定

`set_cold` は `std::getenv` で設定有無を調べ、値全体を `strcmp` で大文字小文字を区別して比較します。数値変換や空白除去はありません。`buffered` と `fadvise` 以外はすべて初期値の mode 0（direct）になります。空文字も未設定ではなく「設定あり」ですが、文字列が一致しないため direct です（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2726-2733`）。

| 条件 | unset | 有効になる値（例） | その他の設定値 |
|---|---|---|---|
| 共通 `CpuExperts` の読み取り | mode 0: direct | `buffered`: mode 1。`fadvise`: mode 2 | mode 0: direct。`direct`、空文字、`BUFFERED`、` buffered`、`buffered `、`0`、`true`、`garbage` はいずれも mode 0 |
| SYCL、非 Windows、cold 領域が 12,000,000,000 bytes 未満 | 共通の読み取り前に `buffered` を設定するため mode 1 | 環境変数が設定されていれば上記の共通規則 | 設定値が存在すれば、空文字や未知の値も含め自動 `buffered` 設定を抑止し、共通規則で mode 0 などに判定 |
| SYCL、非 Windows、cold 領域が 12,000,000,000 bytes 以上 | 共通規則により mode 0 | `buffered` / `fadvise` は共通規則どおり | 共通規則どおり |
| Windows | 共通規則により mode 0 | `buffered`: mode 1。`fadvise` は `ColdStore::open` で mode 0 に変換 | 共通規則どおり |

HIP の `--ssd-experts` は `hy4_setenv(..., "direct", 1)` で既存の値も上書きするため、この引数を指定した場合は起動時の `STRATA_CPUEXP_COLD_IO` より優先されます。環境変数を使わない他の CLI 引数による優先順位変更はありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:451-466`）。

## 有効になる条件

- cold expert が 1 件以上あり、`CpuExperts::Impl::set_cold` が cold store を開く必要があります。cold expert が 0 件なら同関数は環境変数を読み取らずに成功を返します（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2724-2736`）。
- HIP では expert の CPU 配置モードが選ばれ、RAM 予算を超える expert が cold tier に割り当てられた場合にこの I/O 設定が使われます。CPU 配置の選択には `HY4_CPU_EXPERTS` などが関わりますが、本変数自体はその選択を行いません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1084-1110, 1486-1501`）。
- HIP の `--ssd-experts` は `STRATA_HY4_RAM_GB` と `HY4_RAM_BUDGET_GB` も 0 に設定し、さらに本変数を `direct` にします（`engine/src/hy4flash/run/hy4_main.hip.cpp:460-466`）。
- SYCL の unified expert setup は RAM 予算を超える expert を cold mask に入れます。Linux の自動 `buffered` 設定は、その cold mask が空でなく、合計 cold bytes が 12,000,000,000 bytes 未満で、本変数が未設定の場合に限られます。Windows ではこの自動設定ブロック自体がコンパイルされません（`engine/src/hy4flash/sycl/sy_graph.h:155-200, 217-227`）。
- SYCL の CLI 実行とサーバー実行はどちらも `setup_experts_unified` を呼びます（`engine/src/hy4flash/sycl/sy_main.cpp:298-306`、`engine/src/hy4flash/sycl/sy_serve.h:280-285`）。
- HIP の `HY4_COLD_API` が有効で cold mask を処理する経路で `set_cold_experts` が呼ばれます。無効なビルドでは cold experts を処理できずエラーになります（`engine/src/hy4flash/run/hy4_gpu.h:12-15`、`engine/src/hy4flash/run/hy4_graph.hip.h:1564-1572`）。

## 実行時の詳細

値はプロセス起動時に固定されるのではなく、cold expert の設定時に `set_cold` が読みます。読み取った mode は `ColdStore::open` に渡され、開いた store の `io_mode` に保持されます。そのため、store を開いた後に環境変数を変更しても現在の store には反映されません。cold set を設定し直して `set_cold` が再実行されれば、その時点の環境値を読み直します（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2699-2736, 1387-1393`）。

非 Windows では mode 0 が `O_DIRECT` での open、mode 1 と 2 が通常の `O_RDONLY` open です。mode 0 の open が失敗した場合は警告を出して mode 2（通常読み込み後に `POSIX_FADV_DONTNEED`）へ切り替えます。mode 1 は読み込み後の fadvise を行わず、mode 2 は各読み込み後に対象範囲へ `POSIX_FADV_DONTNEED` を呼び出します（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1332-1380, 1415-1426`）。

Windows では mode 0 が `FILE_FLAG_NO_BUFFERING` と overlapped read、mode 1 が buffered overlapped read です。`fadvise` 値の mode 2 は `open` 時に mode 0 へ変換されます。no-buffering open が失敗すると警告を出して buffered overlapped read に切り替えます（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1390-1414`）。

cold store の初期化に失敗すると `set_cold` は false を返します。HIP の runner は初期化エラーとして返し、SYCL の CLI は `experts: <error>` を stderr に出して終了コード 1、SYCL server は `ERR experts: <error>` をプロトコル出力して終了します（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2735-2741`、`engine/src/hy4flash/sycl/sy_main.cpp:304-306`、`engine/src/hy4flash/sycl/sy_serve.h:283-285`）。読み込み中の失敗はジョブ結果が無効である旨を stderr に出し、統計上の cold read error に加算します（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2531-2541`）。

## ログと測定値

cold store の起動ログには実際に選ばれた I/O モードが `io=O_DIRECT`、`io=buffered`、`io=buffered+fadvise`（Windows は `NO_BUFFERING+OVERLAPPED` または `buffered+OVERLAPPED`）として出ます。非 Windows で `O_DIRECT` open に失敗すると `[cpuexp] cold: O_DIRECT open failed, using buffered reads + FADV_DONTNEED`、Windows では `[cpuexp] cold: FILE_FLAG_NO_BUFFERING open failed, using buffered overlapped reads` を stderr に出します（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1395-1399, 1416-1421, 2742-2748`）。cold read 自体の失敗時は `[cpuexp] cold: a read from the .strata file failed; results of this job are invalid` と出します（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2531-2535`）。

`docs/DETAILS.md` に本変数の値や動作を説明する記述は見つかりませんでした。測定値も同資料に確認できないため記載していません。

## 根拠

- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:2699-2748` — cold set が空の場合の早期 return、環境変数の判定、cold store の初期化、ログ。
- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1332-1380, 1387-1426` — 各 OS の読み込み方法と fallback。
- `engine/src/hy4flash/sycl/sy_graph.h:155-227` — SYCL の cold tier 分割と未設定時の Linux 自動 buffered 設定。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:451-466` — `--ssd-experts` による上書き。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1084-1110, 1486-1501`、`engine/src/hy4flash/run/hy4_graph.hip.h:1564-1572` — HIP の CPU/cold tier 選択と cold API 呼び出し。
- `engine/src/hy4flash/sycl/sy_main.cpp:298-306`、`engine/src/hy4flash/sycl/sy_serve.h:280-285` — SYCL CLI と server からの呼び出し、初期化失敗の出力。
