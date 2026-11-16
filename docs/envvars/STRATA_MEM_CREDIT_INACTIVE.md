# `STRATA_MEM_CREDIT_INACTIVE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Linux でメモリ空き容量を計算するとき、有限 cgroup 制限に対して再利用可能として差し引く file cache を `inactive_file` のみに戻す診断・互換用スイッチ。`1` でない場合、条件が揃えば `active_file + inactive_file` の clean page cache から Strata 自身の evictable file mapping を差し引いた量を credit する。影響するのは RAM admission と expert arena の空き容量計算で、モデル選択や生成 token の計算には使われない（`include/strata/core/conversation_memory.hpp:21-30,60-85`、`src/core/conversation_memory.cpp:67-75`、`src/core/expert_source.cpp:432-477`）。

## 値と判定

両読み取り箇所は `std::getenv` のポインタを helper に渡し、helper は値の先頭 1 byte が文字 `'1'` かだけを見る。文字列全体の parse、空白除去、大文字小文字変換、数値検証はしない（`src/core/conversation_memory.cpp:67-69`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Linux の読み取り経路 | inactive-only は false | `1`, `10`, `1anything`（先頭が `1`） | 空文字、`0`, `true`, ` 1`, `-1` |
| Windows / macOS の `sample_host_memory` | inactive-only はコード上 true 固定 | なし（この関数では環境変数を読まない） | すべて |

unset、空文字、先頭が `1` 以外の値は helper の結果が false となり、Linux では通常の cgroup 条件分岐に進む。無効値を理由にエラーや警告を出す処理はない（`src/core/conversation_memory.cpp:67-69,360-382`）。

## 有効になる条件

- **会話 memory guard:** Linux で読める有限 cgroup v1/v2 制限があり、`/proc/meminfo` の `MemTotal` があり、その制限が `MemTotal` 未満で、かつ `/proc/self/status` から Strata 自身の evictable file mapping を判定できる場合に、unset 等では active/inactive の両リストを使う。`1` なら inactive のみ。`MemTotal` 不明、制限が `MemTotal` 以上、または own mapping 不明の場合は、値にかかわらず inactive のみを使う（`src/core/conversation_memory.cpp:71-75,272-293,348-357`）。
- **expert arena RAM 判定:** Linux cgroup v2 の有限制限について、`MemTotal` があり制限がそれ未満のときだけ `1` 以外の設定で active/inactive cache credit を使う。`1`、`MemTotal` 不明、または制限が `MemTotal` 以上なら従来の `cgroup_available_bytes` 判定に戻る。cgroup v1 の arena 判定は limit から usage を引く方式で、この変数による分岐はない（`src/core/expert_source.cpp:417-432,461-477,485-501`、`src/core/conversation_memory.cpp:77-87`）。
- Windows/macOS の会話 memory sampler は inactive-only を `true` として `combine` に渡し、環境変数を参照しない。expert source の Windows/macOS 分岐にも当該変数の読み取りはない（`src/core/conversation_memory.cpp:360-384`、`src/core/expert_source.cpp:409-417,504-521`）。
- `--memory-limit-mib` / `STRATA_MEMORY_LIMIT_MIB` の明示 cap は別の制約。優先順位は CLI 引数、次に `STRATA_MEMORY_LIMIT_MIB` であり、対象変数が制御する cache credit とは別に最小空き容量へ加わる。明示 cap 自身の credit は root cgroup の inactive credit を使うため、この変数で切り替わらない（`src/program/generate.cpp:3892-3909,4433-4446`、`src/core/conversation_memory.cpp:294-307`）。

## 実行時の詳細

値は global/static cache に保存されず、Linux の各サンプル時に `getenv` される。会話 memory guard は `sample_host_memory` の呼び出しごと、expert arena は `host_available_memory` の呼び出しごとに評価するため、プロセス内で環境値が変更された場合は次のサンプルから反映される（`src/core/conversation_memory.cpp:329-368`、`src/core/expert_source.cpp:406-432,6057-6085`）。子プロセスへの転送や上書き処理はこの名前について見つからない。

会話 memory guard は `MemAvailable`、可視 cgroup の各上限、必要なら明示 cap から最小の available を作る。credit の基礎値は `inactive_file` から dirty/writeback を引いた値で、通常条件では `active_file` も足してから Strata 自身の evictable mappings を差し引く。own mapping が分からない場合は inactive のみに戻る（`src/core/conversation_memory.cpp:21-29,31-64,71-75,272-307`）。

expert arena の Linux v2 分岐は clean file-list credit に `min(credit / 2, limit / 64)` の余裕を残し、`limit - (current - credit)` を空き容量に使う。これが arena の必要 RAM に足りない場合、待機後に再判定し、`--mmap-experts` fallback、拒否、または警告へ進み得る。この変数は credit 見積もりを変えるだけで、同時割当を予約しない（`src/core/conversation_memory.cpp:77-87`、`src/core/expert_source.cpp:470-479,6010-6044,6057-6089,6137-6159`）。

## ログと測定値

この変数専用のログはない。`--serve` または正の memory limit があるときの起動 memory guard 行は、採用した `reclaimable cache credited` と `available` を表示するため、計算への影響を間接的に確認できる（`src/program/generate.cpp:4433-4463`）。cgroup 読み取りに失敗した場合、明示 cap がなければ一度だけ `[strata] memory guard: the cgroup memory files could not be read or parsed, using MemAvailable; set --memory-limit-mib to the container's limit` を stderr に出す（`src/core/conversation_memory.cpp:338-346`）。

arena の空き見積もりが変わることで、待機ログ、RAM 不足の警告、または `--mmap-experts` fallback の経路が変わり得る（`src/core/expert_source.cpp:6045-6049,6057-6073,6137-6159`）。cgroup hard limit による開始拒否は `hm.cgroup_limit` と必要量を比較し、この環境変数の credit 値では変わらない（`src/core/expert_source.cpp:6028-6043`）。この変数固有の性能測定値はコード・参照資料に見つからない。

資料との照合では、`docs/DETAILS.md:736-739` が cgroup credit を「clean inactive file cache」と説明する一方、現行実装コメントは、container（limit < MemTotal）での既定を active + inactive とし、`STRATA_MEM_CREDIT_INACTIVE=1` を inactive-only に戻す設定としている。動作の根拠は現行ソースの分岐であり、この資料説明とは差がある（`include/strata/core/conversation_memory.hpp:21-26,69-85`、`src/core/conversation_memory.cpp:71-75`）。

## 根拠

- 変数名の全コード参照: `include/strata/core/conversation_memory.hpp:25,69,83,92`、`src/core/conversation_memory.cpp:67-69,357`、`src/core/expert_source.cpp:432`。ほかの実行時読み取り箇所はない。設定登録と `docs/SETTINGS.md` の分類は `data/settings-register.json:16943-16961`、`docs/SETTINGS.md:320`。
- cache credit の parse と選択: `src/core/conversation_memory.cpp:21-75,272-307`。
- 会話 sampler の platform 分岐と評価時期: `src/core/conversation_memory.cpp:329-382`。
- expert arena の Linux 分岐・結果: `src/core/expert_source.cpp:406-503,6010-6159`。
- CLI cap と startup 観測: `src/program/generate.cpp:3892-3909,4433-4463`。
- 資料記述: `docs/DETAILS.md:736-739`。
