# `STRATA_HOST_CORE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

CPU expert pool が通常予約する最初の物理コアではなく、最後の物理コアを host thread（GPU の layer loop を進めるスレッド）用に予約します。残りのコアは pool worker に割り当てます。これは CPU thread の配置を変える設定です。ソースコメントは結果を変えないと説明しています（`include/strata/kernels/cpu/pool.hpp:83-89`）。

環境変数を読むのは通常版と SYCL 版の `strata generate` 起動処理です。どちらも `--host-core` が指定されていればそちらが優先されます（通常版: `src/program/generate.cpp:1896-1901,2196-2200`; SYCL 版: `sycl/src/program/generate.cpp:1979-1983`）。

## 値と判定

環境変数の文字列を整数や真偽値には変換せず、`last` と完全一致する場合だけ `HostCore::Last` にします。大文字小文字、前後の空白、後続文字を含む値は一致しません。

| CLI `--host-core` | 環境変数 | 起動設定 |
|---|---|---|
| `first` | 任意 | `First`（CLI が優先） |
| `last` | 任意 | `Last`（CLI が優先） |
| 未指定または空 | `last` | `Last` |
| 未指定または空 | unset、空、`first`、その他 | `First`（既定値） |

CLI に指定できる値は `first` と `last` のみで、それ以外は `strata generate: unknown --host-core value '…' (expected first or last)` を stderr に出して終了コード 2 で終了します。環境変数に不明な値を設定してもエラーにはならず、既定の `First` のままです（`src/program/generate.cpp:1896-1900,2196-2200`; `src/kernels/cpu/pool.cpp:36-40`）。

## 有効になる条件

- CPU topology の検出が `skip_first=true` で呼ばれ、host 用コアと worker 用コアの両方が見つかった場合に、予約コアの位置を入れ替えます。
- hybrid CPU では `Last` の入れ替えを行いません。検出処理は `topo.is_hybrid` が false の場合だけ切り替えます。したがって hybrid CPU では、環境変数が `last` でも host は通常の topology 検出で選ばれた先頭側のままです（`src/kernels/cpu/pool.cpp:44-54`）。
- topology が得られず host core が `-1` の場合や worker list が空の場合も切り替えません。
- 通常版と SYCL 版が共有する CPU topology 実装は Windows と Linux の分岐を持ち、同じ `detect_cpu_topology()` の切り替え処理を使います。別 OS の挙動は、このソース範囲から確認できません。

## 実行時の詳細

起動処理は pool や session が thread を pin する前に `STRATA_HOST_CORE` を一度読みます。CLI の `o.host_core` が空の場合だけ `getenv()` を呼び、取得値が厳密に `last` の場合に atomic な設定を `Last` に変更します。それ以外では初期値 `First` が保たれます。通常版と SYCL 版の両方に同じ読み取りがあります。プロセス起動後の環境変更は再読込されません（通常版: `src/program/generate.cpp:2196-2200`; SYCL 版: `sycl/src/program/generate.cpp:1979-1983`; 共通設定: `src/kernels/cpu/pool.cpp:35-40`）。

topology 検出は通常の予約コアを worker list の先頭から取り出し、`Last` が有効で非 hybrid、かつ worker list が残る場合、worker list の末尾を host core にし、元の host core を worker list の先頭へ移します（`src/kernels/cpu/pool.cpp:44-54`）。`SessionLoopScratch` は `planned_host_core()` の結果に従って host thread を pin し、core pool は検出された worker core に各 worker を pin します（`src/core/session.cpp:542-560`; `src/kernels/cpu/pool.cpp:459-465`）。

起動時の stderr topology ログには host の論理 CPU 番号と `(--host-core first|last)` が出ます。通常版と SYCL 版の両方にこのログがあります。環境変数専用の警告やエラーはありません（通常版: `src/program/generate.cpp:4761-4764`; SYCL 版: `sycl/src/program/generate.cpp:4253-4260`）。

## 文書との照合

`docs/DETAILS.md:265-267` は Windows での `STRATA_HOST_CORE=last` を説明し、Windows の GPU 割り込みを理由として挙げています。現行コードの `Last` による topology 入れ替えは Linux 側にも適用されますが、hybrid CPU では抑止されます。資料にある割り込みの説明は Windows に関するものです。

## 根拠

- 環境変数と CLI の優先順位、値の厳密比較: `src/program/generate.cpp:1896-1901,2196-2200`; `sycl/src/program/generate.cpp:1979-1983`
- 既定値と topology の切り替え条件: `src/kernels/cpu/pool.cpp:35-57`
- host thread の pin: `src/core/session.cpp:542-560`
- worker thread の pin: `src/kernels/cpu/pool.cpp:459-465`
- 起動時ログ: `src/program/generate.cpp:4757-4764`
- 設計説明: `include/strata/kernels/cpu/pool.hpp:83-89`; `docs/DETAILS.md:265-267`
