# `STRATA_MEMORY_LIMIT_MIB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`generate` 起動時に、このエンジンが使える RAM を見積もる際の利用者指定上限（MiB）を設定する。OS のメモリ制限を設定したり、割り当てを強制的に止めたりする変数ではない。Strata のメモリ計測結果を小さくし、会話退避・セッション保存や、同じ計測値を使う RAM 判定を保守的にする。`--memory-limit-mib N` が指定されていればそちらが優先される。読み取りと設定は `engine/src/program/generate.cpp` の起動処理にある。(`engine/src/program/generate.cpp:4724-4737`; `engine/src/core/conversation_memory.cpp:289-326`)

## 値と判定

CLI オプションの既定値は `-1`（未指定を表す）。この場合だけ `std::getenv` で環境変数を読み、値が null または空文字なら上限を `0` にする。非空値は符号付き整数への 10 進 `std::from_chars` で文字列全体を変換し、変換失敗・末尾の余分な文字・負数・`INT64_MAX / (1024 * 1024)` MiB 超過をエラーにする。上限値は `8796093022207` MiB。先頭・末尾の空白、`+` 符号、`true` などは受け付けず、`0anything` も末尾が残るため無効。`-0` は整数 0 として有効。(`engine/src/program/generate.cpp:1105-1107,4724-4737`)

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `--memory-limit-mib` なし | 上限なし（0 MiB） | `0` から `8796093022207` までの整数。`0` は上限なし、正数は上限 | 空文字は unset 相当。それ以外の非空値で、全体を整数変換できないもの、負数、上限超過 |
| `--memory-limit-mib N` あり | 環境変数を読まず、CLI 値を使用 | CLI 側も同じく 0 以上の範囲内整数。`0` は上限なし | CLI 値が範囲外・整数でない場合は起動引数エラー |

CLI の `--memory-limit-mib` は環境変数の値より優先し、CLI 値が `0` でも環境変数へ戻らない。CLI で不正な値を渡した場合はオプション解析時点で stderr に `%s needs a nonnegative integer within range` を出して終了コード 2。環境変数が不正な場合は `STRATA_MEMORY_LIMIT_MIB needs a nonnegative integer within range (got "%s")` を stderr に出し、同じく 2 で終了する。CLI が明示されていれば、不正な環境変数値も検査されない。(`engine/src/program/generate.cpp:4083-4102,4724-4735`)

## 有効になる条件

- `generate` の起動処理で設定される。該当箇所に `--serve` や GPU backend の条件分岐はなく、`--serve` なしでも正の上限を設定し、後続のメモリ見積もり経路が値を使う。(`engine/src/program/generate.cpp:4724-4738`)
- `--serve` では、会話キャッシュの自動サイズ計算、会話の退避、セッションの保存・復元など、RAM 可否判定を行う経路に適用される。会話キャッシュ自動サイズ計算は `--serve` かつ `--prompt-cache > 0` かつ `--conversation-cache-slots > 0` のときに行われる。明示的な `--conversation-cache-mib` は自動サイズ計算を置き換える。(`engine/src/program/generate.cpp:13770-13804`; `engine/src/program/generate.cpp:14282-14305,14392-14405`; `engine/src/program/generate.cpp:18556-18584,18628-18646`)
- `--serve` 以外でも、共有 `sample_host_memory()` の結果を使う処理には影響しうる。例として、PLE の自動 RAM 常駐判定は `STRATA_PLE_AUTO_RAM` で許可され、明示 `--ple-io` がない場合にこの RAM 値を参照する。プロンプト chunk の RAM 判定や resident expert の fallback budget も共有計測値を参照する。(`engine/src/program/generate.cpp:6275-6296`; `engine/src/program/generate.cpp:11189-11209`; `engine/src/program/generate.cpp:8827-8837`)
- 実際の RAM 計測は OS ごとに異なる。Windows は `GlobalMemoryStatusEx` と commit 余地、Linux は `/proc`・cgroup 計測、macOS は Mach のページ統計を使い、いずれも保存された上限を `combine` に渡す。その他の OS では計測結果は不明となる。(`engine/src/core/conversation_memory.cpp:378-408,411-440`)
- Linux で cgroup の読み取りに失敗し、正の利用者上限が設定されている場合、使用量を計算できないため計測結果は不明になる。上限が 0 なら `MemAvailable` のみで続行し、cgroup 読み取り不能の警告を一度出す。(`engine/src/core/conversation_memory.cpp:389-397`)
- 既知の build macro による当該値の別解釈は、調査した読み取り・設定・計測経路にはない。ビルド対象への収録有無自体は build を実行していないため確認していない。

## 実行時の詳細

引数解析後の起動処理で環境変数を一度だけ読み、MiB をバイトに換算して `set_memory_limit_bytes` に渡す。値はプロセス内の atomic に保存される。以降 `sample_host_memory()` が呼ばれるたびに OS/cgroup の現在値は再計測する一方、環境変数は再読込しないため、プロセス起動後に環境を変更しても反映されない。子プロセスへの転送・上書き処理は、候補名の全参照検索では見つからなかった。(`engine/src/program/generate.cpp:4724-4737`; `engine/src/core/conversation_memory.cpp:134-135,375-376,411-447`)

計測結果は `MemAvailable` 等と、見える cgroup 制限の残量、利用者上限の残量のうち最小の空きとして合成される。利用者上限がある場合、Strata は cgroup root の `memory.current` 等、または cgroup が読めない状況では `MemTotal - MemAvailable` を使用量の基礎として、指定上限から差し引く。従ってこの変数は RAM 判定上の上限であり、上限を超えたプロセスを直接停止する機構ではない。(`engine/src/core/conversation_memory.cpp:289-326,378-408`; `engine/src/core/conversation_memory.hpp:116-126`)

会話退避は snapshot と `--conversation-cache-min-free-mib` の床を計測上の空きに収められない場合に退避を見送り、必要なら既存の退避会話を解放して再判定する。セッション保存・復元も必要 RAM と同じ床を満たさない場合は拒否経路に進む。(`engine/src/program/generate.cpp:14282-14347,14392-14405`; `engine/src/program/generate.cpp:18571-18584,18628-18646`)

## ログと測定値

`--serve` が有効、または最終上限が正数なら、起動時に計測を試みる。成功すると stderr に `strata generate: memory guard: limit %.1f GiB (source: %s), current %.1f GiB, reclaimable cache credited %.1f GiB; available %.1f GiB (MemAvailable %.1f GiB%s), floor %lld MiB` を出す。source は `flag`、`cgroup`、`meminfo` のいずれかで、正の明示上限では追加表示に `--memory-limit-mib N` が入る。計測できない場合は `strata generate: memory guard: the available RAM cannot be read; parking and session save/restore are refused` を出すが、この箇所でプロセスを終了させる処理はない。(`engine/src/program/generate.cpp:4738-4754`; `engine/src/core/conversation_memory.cpp:331-336`)

退避を RAM 床に収められない場合は `strata serve: conversation cache: skip parking (physical RAM admission; ...)` を出す。セッション保存・復元の拒否理由は `refuse` 経路へ渡される。(`engine/src/program/generate.cpp:14341-14347,18571-18585,18630-18646`)

`docs/DETAILS.md:843-846` はこの上限の適用先を「parking and session files only」と記すが、現 HEAD のソースでは共有メモリ計測値を PLE 自動 RAM 判定、プロンプト chunk 判定、resident fallback budget も参照している。一方、expert file-tier 再評価の一箇所は `sample_host_memory(..., 0)` と明示して利用者上限を渡さない。従って資料の適用範囲の説明は、現行ソース全体を網羅していない。(`engine/src/program/generate.cpp:6275-6296,8827-8837,11189-11209,12144-12163`; `engine/src/core/conversation_memory.cpp:378-408`)

測定値は記載しない。対象ソースのこの変数の契約を説明するのに必要な測定値はない。

## 根拠

- 値の既定値、CLI 解析、優先順位、検証、環境読み取り、設定、起動ログ: `engine/src/program/generate.cpp:1105-1107,4083-4102,4724-4754`
- 上限を使った空き RAM の合成: `engine/src/core/conversation_memory.cpp:289-326,375-447`; API: `engine/include/strata/core/conversation_memory.hpp:116-126`
- サーバーの自動 cache sizing、退避、保存・復元の RAM 判定: `engine/src/program/generate.cpp:13770-13804,14282-14405,18556-18584,18628-18646`
- 共有計測値を使う別経路と、明示的に上限を除く再評価: `engine/src/program/generate.cpp:6275-6296,8827-8837,11189-11209,12144-12163`
