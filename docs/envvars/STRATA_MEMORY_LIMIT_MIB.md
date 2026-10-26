# `STRATA_MEMORY_LIMIT_MIB`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

Strata generate engine の RAM 判定に、運用者が指定するコンテナ／cgroup 全体の MiB 上限を加えます。主な用途は `--serve` の会話 parking と session save/restore の RAM admission で、利用可能量がこの上限を超えないようにします。可視 cgroup の外側に実際のコンテナ上限がある場合に、その上限を手動で補う用途です。メモリ確保量そのものやプロセス全体の OS 制限を設定する変数ではありません（`include/strata/core/conversation_memory.hpp:10-30,55-63`）。

## 値と判定

| 入力 | 動作 |
|---|---|
| 未設定 | 上限なし（0 bytes） |
| 空文字 | 未設定と同じく上限なし |
| 非負の十進整数 | MiB として読み、bytes に変換して RAM guard に設定 |
| 負数、空白付き、数字以外を含む値、範囲外 | stderr に `STRATA_MEMORY_LIMIT_MIB needs a nonnegative integer within range (got "...")` を出して起動を終了（return 2） |

環境変数は `std::from_chars` で `int64_t` 全体を parse し、文字列末尾まで消費したかを検査します。したがって `12x` や ` 12`、`12 ` は無効です。最大値は `INT64_MAX / (1024 * 1024)` MiB で、bytes への左シフトが範囲内に収まるよう制限されています。`0` は上限なしです（`src/program/generate.cpp:2930-2942`）。

`--memory-limit-mib N` が指定された場合は環境変数より優先されます。CLI 側も非負の整数を全体 parse し、同じ上限を適用します。CLI の `0` も環境変数を無視して上限なしにします（`src/program/generate.cpp:2646-2666,2930-2942`）。

## 有効になる条件

値は `strata generate` の起動時に一度解決され、`set_memory_limit_bytes()` に保存されます。後から環境を変更しても再読み込みされません。以後の `sample_host_memory()` 呼び出しが保存値を RAM 判定に使います（`src/program/generate.cpp:2929-2945`, `src/core/conversation_memory.cpp:255-256,280-291`）。

この上限は `MemAvailable` と、Strata が読み取れる cgroup の上限・使用量から得る空き容量と併せて判定され、最も小さい値が採用されます。指定上限の空き容量は、cgroup の現在使用量（読めない場合は `MemTotal - MemAvailable`）から clean inactive file cache の credit を差し引いて計算します。上限が設定されているのにその使用量を測れない場合、RAM sample は unknown となり、処理は安全側に拒否されます（`include/strata/core/conversation_memory.hpp:12-30`; `src/core/conversation_memory.cpp:223-237,258-277`）。

起動時に `--serve` または正の上限がある場合、利用可能 RAM を測れれば stderr に `strata generate: memory guard: limit ... (source: flag|cgroup|meminfo) ...` を出します。`--serve` 中の会話 parking は snapshot の追加 RAM と `--conversation-cache-min-free-mib` の床を満たさなければ parking を見送り、必要なら古い parked 会話を退避します。session save/restore も同じ RAM sample と床を使って拒否できます（`src/program/generate.cpp:2943-2958,9591-9625,12179-12207,12245-12268`）。

起動時の RAM sample が取れない場合、stderr に `strata generate: memory guard: the available RAM cannot be read; parking and session save/restore are refused` と出ます。Linux で cgroup 情報が読めず、かつ手動上限がない場合は `MemAvailable` を使う警告を一度出します。手動上限がある場合は使用量を特定できないため sample を返しません（`src/program/generate.cpp:2945-2949`; `src/core/conversation_memory.cpp:267-275`）。Windows は `GlobalMemoryStatusEx` の物理空きと commit 空きの小さい方を RAM sample に渡し、指定上限もその判定に加えます（`src/core/conversation_memory.cpp:280-286`）。

## 根拠

- `src/program/generate.cpp:744-746` — 既定状態と変数の意図。
- `src/program/generate.cpp:2646-2666` — CLI 値の完全 parse、範囲検査、CLI 設定。
- `src/program/generate.cpp:2929-2958` — CLI 優先、環境値の検証、bytes 化、初期ログ。
- `include/strata/core/conversation_memory.hpp:10-30,55-63` — RAM guard が組み合わせる容量と保存 API。
- `src/core/conversation_memory.cpp:223-237,255-291` — operator 上限の適用と Linux/Windows の sample 経路。
- `src/program/generate.cpp:9591-9625,12179-12207,12245-12268` — parking と session file の RAM admission。
- `docs/DETAILS.md:628-633` — 概要説明との照合。資料は上限を「コンテナが見えない場合」の手動 cap とし、parking/session file に適用、arena startup sizing や resident budget には適用しないと記載。コード上も `sample_host_memory()` を使う RAM 判定への適用であることを確認した。
