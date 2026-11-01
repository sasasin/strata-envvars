# `STRATA_MEMORY_LIMIT_MIB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

## 役割

Strata の RAM 判定に、運用者が指定するコンテナ／cgroup 全体の MiB 上限を加えます。主な用途は `--serve` の会話 parking と session save/restore の RAM admission です。OS が見せる利用可能 RAM がこの指定上限より大きくても、Strata は指定上限から現在の使用量を引いた残量を RAM 判定に使います。メモリ確保量そのものやプロセス全体の OS 制限を設定するものではありません。Strata 所有コードで環境から直接読む箇所は `src/program/generate.cpp` の起動処理に 1 箇所です（`src/program/generate.cpp:3531-3544`）。

## 値と判定

| 入力 | 動作 |
|---|---|
| `--memory-limit-mib` が指定済み | CLI 値を使い、環境変数を読みません。`0` も指定済みとして環境変数より優先します。 |
| CLI 未指定、環境変数 unset | 上限なし（0 bytes）。 |
| CLI 未指定、環境変数が空文字 | unset と同じく上限なし。 |
| CLI 未指定、環境変数が非負値として parse できる十進整数 | MiB として読み、bytes に変換して RAM guard に設定します（`-0` は 0 として受理）。 |
| 負数、空白付き、数字以外を含む値、範囲外 | stderr に `STRATA_MEMORY_LIMIT_MIB needs a nonnegative integer within range (got "...")` を出し、`return 2` で起動を終了します。 |

環境変数は `std::from_chars` で `int64_t` に文字列全体を parse し、末尾まで消費したことを確認します。したがって `12x`、` 12`、`12 `、`+12` は受け付けません。`-0` は parse 後の値が 0 なので受理されます。上限は `INT64_MAX / (1024 * 1024)` MiB です。`0` は指定上限なしを意味します。値を読み取るのは起動時の 1 回だけで、その結果を bytes にして `set_memory_limit_bytes()` に保存します（`src/program/generate.cpp:3531-3544`）。

CLI 引数も非負整数を全体 parse し、同じ上限で検査します。複数回指定された場合は引数ループで後に現れた値が設定され、いずれかが不正なら起動を終了します（`src/program/generate.cpp:3231-3248`）。

## 有効になる条件

環境値の読取・妥当性検査は `generate` 起動処理で行われます。RAM guard の実測は Linux と Windows の経路があり、その他の OS では `sample_host_memory()` が unknown を返します。Linux では `MemAvailable`、可視 cgroup 各階層の上限、明示上限の残量のうち最小を採用します。明示上限の使用量は、読める場合は最上位の可視 cgroup 使用量、そうでなければ `MemTotal - MemAvailable` から求め、clean inactive file cache の credit を差し引きます。明示上限があるのに使用量を測れないと sample は unknown になります（`include/strata/core/conversation_memory.hpp:10-30`; `src/core/conversation_memory.cpp:203-237,258-277`）。Windows は `GlobalMemoryStatusEx` から物理空きと commit 空きの小さい方を RAM sample に渡して、同じ明示上限を組み合わせます（`src/core/conversation_memory.cpp:280-291`）。

実際の会話 parking と session save/restore は `--serve` の機能です。parking は snapshot の追加 RAM と `--conversation-cache-min-free-mib` の床を満たさない場合に見送られ、古い parked 会話を退避して再判定する場合があります（`src/program/generate.cpp:10663-10695`）。session save は必要 RAM と同じ床を admission 判定し、restore はファイル読込中の必要 RAM を同様に検査します（`src/program/generate.cpp:13715-13743,13784-13804`）。サーバーの会話 cache 自動サイズも、モデル読込後の `available_host_bytes()` を使うためこの上限の影響を受けます（`src/program/generate.cpp:10404-10437`）。

## 実行時の詳細

起動時に `--serve` または正の上限があると、初期 RAM sample を取り、成功時は stderr に `strata generate: memory guard: limit ... (source: flag|cgroup|meminfo) ...` を出します。sample が unknown の場合は `strata generate: memory guard: the available RAM cannot be read; parking and session save/restore are refused` を出します（`src/program/generate.cpp:3544-3560`）。上限を指定した場合でも、他の可視 cgroup 制限または OS が示す空き RAM の方が小さければそちらが判定値になります。

上限 bytes はプロセス内の atomic 状態に保存され、各 `sample_host_memory()` 呼び出しはその上限を使いながら RAM 情報を再取得します。したがって上限の環境変数自体は起動後に再読込されませんが、現在の RAM 使用量は各判定時点で反映されます（`src/core/conversation_memory.cpp:28,255-256,280-298`）。parking の RAM 不足は stderr に `skip parking (physical RAM admission; ...)`、session save/restore の不足は session refusal 経路から通知されます（`src/program/generate.cpp:10686-10690,13729-13743,13787-13804`）。

## 根拠

- `src/program/generate.cpp:865-867,1021-1023` — CLI と環境変数の位置づけ、初期値、上限 `0` の意味。
- `src/program/generate.cpp:3231-3248` — CLI 引数の全体 parse、範囲検査、設定。
- `src/program/generate.cpp:3531-3560` — CLI 優先、環境値の検証、bytes 化、起動時 sample とログ。
- `include/strata/core/conversation_memory.hpp:10-30,55-65` — RAM guard が組み合わせる容量、保存 API、利用可能 RAM API。
- `src/core/conversation_memory.cpp:28,203-237,255-298` — 上限の保存、明示上限の残量計算、Linux/Windows の sample 経路。
- `src/program/generate.cpp:10404-10437,10663-10695` — `--serve` 会話 cache sizing と parking admission。
- `src/program/generate.cpp:13715-13743,13784-13804` — session save/restore RAM admission。
- `docs/DETAILS.md:704-709` — 概要資料との照合。資料は上限をコンテナが見えない場合の補助値とし、parking と session file の RAM 判定に適用、arena startup sizing・resident budget には適用しないと説明しています。
