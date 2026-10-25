# `STRATA_MEMORY_LIMIT_MIB`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

エンジンが RAM admission 判定に使う、コンテナ / cgroup の追加の総メモリ上限を MiB で指定します。主に server の会話 parking と session の保存・復元を行う前に、必要な RAM と残す空き RAM を確保できるか判断します。OS が報告する MemAvailable や cgroup の上限を置き換える予約ではなく、最小の余裕量を選ぶ判定に加わります。

## 値と判定

- `--memory-limit-mib` が指定されていれば CLI 値を採用し、この環境変数を読みません。CLI の `0` も環境変数に優先し、「追加上限なし」です。
- CLI 未指定時、環境変数が未設定または空文字なら追加上限なし（0）。
- それ以外は `std::from_chars` で `int64_t` に文字列全体を parse します。非負整数のみ受理し、負値、符号 `+`、空白、末尾の文字、範囲外は `STRATA_MEMORY_LIMIT_MIB needs a nonnegative integer within range (got "...")` を stderr に出して終了コード 2 で起動を拒否します。
- 最大値は `INT64_MAX / (1024 * 1024)` MiB です。値は MiB から byte に変換して保存されます。`0` は cap 無効です。

## 有効になる条件

設定値の採用はエンジン起動時に一度です。値は `set_memory_limit_bytes()` の atomic state に格納され、その後の各 RAM sample が参照します。値の変更を起動後に環境へ反映しても再読込されません。

追加上限のある Linux sample は、MemAvailable、検出できた cgroup v1/v2 上限、およびこの cap の余裕量の最小を使います。cap の使用量は、見える最上位 cgroup の `memory.current`（clean inactive file cache の控除あり）です。cgroup scan 自体は成功したが root 使用量が得られない場合に限り `MemTotal - MemAvailable` を代用します。cap 有効時に cgroup files の scan / parse が失敗すると sample は unknown となり、RAM admission は失敗扱いです。Windows では `GlobalMemoryStatusEx` の物理空きと commit 空きの小さい方を OS 側の sample として、この cap と組み合わせます。他の OS では sample が unknown です。

環境変数だけでは `--serve` を有効にしません。`--serve` が有効、または cap が正数のとき起動時に RAM guard の sample を表示します。`--serve` の会話 cache が実際に使われるには、別途 cache 関連設定と prompt cache が有効である必要があります。

## 実行時の詳細

起動時に値を検証・byte 化して保存し、会話 parking の snapshot admission 前後、session save の checkpoint / capture 判定、session restore の読込前に `sample_host_memory()` が再計測されます。sample は予約ではなく、別プロセスが後から RAM を使う可能性があります。判定不能または不足の場合は parking や session 操作を拒否・skip する側へ進み、server 全体をこの環境変数だけで終了させる処理ではありません。

起動時の有効 sample は `strata generate: memory guard: ...`、読めない sample は `strata generate: memory guard: the available RAM cannot be read; parking and session save/restore are refused` を stderr に出します。Linux で cgroup 情報が読めず、cap が未設定なら `MemAvailable` のみで続行し、cgroup 警告はプロセス当たり一度です。cap があるのに cgroup 情報が読めない場合は使用量推定の fallback を含めて sample を決められるか判定し、必要な情報がなければ unknown です。

`docs/DETAILS.md` はフラグと同環境変数の優先順位、`0` の意味、cap と他の memory terms の最小値採用を記載しています。実装の選択規則および `include/strata/core/conversation_memory.hpp` の説明と一致します。

## 根拠

- `src/program/generate.cpp:623-625` — CLI option の初期値と cap の意味。
- `src/program/generate.cpp:2012-2029` — CLI parse と受理範囲。
- `src/program/generate.cpp:2214-2244` — CLI 優先、環境 parse、終了条件、byte 設定、起動時 sample とログ。
- `include/strata/core/conversation_memory.hpp:10-30,55-65` — RAM terms、cap 使用量、API。
- `src/core/conversation_memory.cpp:203-238,255-291` — 最小余裕量、atomic cap、Linux / Windows の sample。
- `src/program/generate.cpp:7902-7955,9867-9881,9924-9943` — parking / session save / restore の admission 使用箇所。
- `docs/DETAILS.md:997-1020` — memory guard の文書説明。
