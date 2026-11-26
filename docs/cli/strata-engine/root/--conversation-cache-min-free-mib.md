# `strata --serve --conversation-cache-min-free-mib`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。サーバーモードは `--serve`） |
| オプション | `--conversation-cache-min-free-mib` |
| 別名 | なし |
| 値 | 非負の10進整数 MiB。parser が受け付ける上限は `INT64_MAX / (1024 * 1024)`。 |

## 役割

`--serve` の会話 cache に対し、park・session 保存・session 復元の後にも残す RAM の下限を指定します。通常 engine では cache 予算を自動決定するときにもこの下限を差し引きます。RAM 使用可能量の判定は `MemAvailable` だけでなく cgroup 制限と `--memory-limit-mib` の制限も反映します。明示した `--conversation-cache-mib` の予算を書き換える指定ではなく、別の admission 条件です。

## 使い方

```sh
# 通常の strata engine で serve を起動し、会話 cache 操作後に 4 GiB を残す
strata --serve --conversation-cache-min-free-mib 4096 --pack /path/to/model.strata
```

## 値と既定値

- 既定値は `2560` MiB（2.5 GiB）。通常 engine と SYCL engine の両 parser が同じ既定値を持ちます（`engine/src/program/generate.cpp:1093`、`engine/sycl/src/program/generate.cpp:728`）。
- `0` は予約する下限をなくします。ただし RAM 使用量の計測自体に失敗した場合、通常 engine の RAM admission は失敗します。
- 負数、整数でない値、数値変換エラー、または上限超過は拒否されます。値がない場合は `--conversation-cache-min-free-mib needs a value` を stderr に出して終了コード 2、無効値では `--conversation-cache-min-free-mib needs a nonnegative integer within range` を stderr に出して終了コード 2 です（`engine/src/program/generate.cpp:3844-3846,4084-4097`）。
- 同じオプションを複数回指定すると、引数列を順に解析して値を代入するため最後の有効値が残ります（`engine/src/program/generate.cpp:3842-3843,4099-4100`）。

## 実行時の動作

- 通常 engine で `--conversation-cache-mib` を省略した場合、`--serve` かつ `--prompt-cache` と `--conversation-cache-slots` が正なら、モデル読込後の利用可能 RAM からこの下限を引き、その40%を256 MiB単位に切り下げます。自動予算は最大8192 MiBで、計測不能または予算が1024 MiB未満なら cache は無効になります（`engine/include/strata/core/conversation_memory.hpp:128-139`、`engine/src/program/generate.cpp:13850-13878`）。
- `--conversation-cache-mib N` を明示したときは、その予算（`0` を含む）は自動調整されません。一方、このオプションの RAM 下限は引き続き park や session 保存・復元の条件として適用されます（`engine/src/program/generate.cpp:13850-13869,14374-14394,18662-18684,18732-18747`）。
- 通常 engine の park では、追加 snapshot の必要量と下限を合わせて RAM 判定します。足りなければ idle pool、解放可能 heap、古い parked conversation の順にメモリを返し、それでも不足すれば今回の park を見送ります。cache 自体の予算内に空きがあっても、この RAM 条件を満たすとは限りません（`engine/src/program/generate.cpp:14374-14444`）。
- session の保存・復元でも、必要な RAM にこの下限を加えて判定します。保存時に不足すれば `not enough RAM to save the session ...`、復元時に不足すれば `not enough RAM to read it ...` を理由文字列として返す経路があります（`engine/src/program/generate.cpp:18662-18684,18732-18747`）。
- RAM 計測の Linux 実装は `MemAvailable` と cgroup の空き上限の小さい方を利用し、明示上限も反映します。Windows は物理メモリ空きと commit 空き、macOS は free/purgeable 等のページを使います。計測不能時は不明値になります（`engine/src/core/conversation_memory.cpp:378-408,411-439`）。

## 適用条件と副作用

- これは `strata-engine` のルート引数です。通常 engine のほか `engine/sycl/src/program/generate.cpp:728,2065-2078` にも定義があり、SYCL 版も値を受け取ります。SYCL 版の既定 `conversation_cache_mib` は `0` のため、cache は別途有効にしない限り使われません（`engine/sycl/src/program/generate.cpp:726-728`）。
- 通常 engine では `--memory-limit-mib`（または `STRATA_MEMORY_LIMIT_MIB`）との相互作用があります。これは測定する使用可能量を制限する設定で、RAM 下限を上書きしません（help: `engine/src/program/generate.cpp:1295-1301`、計測: `engine/src/core/conversation_memory.cpp:289-320`）。
- SYCL 版では snapshot が予算条件を満たさないと `skip parking` を stderr に出し、その snapshot の park を見送ります（`engine/sycl/src/program/generate.cpp:8454-8468`）。通常 engine の eviction 手順と同一ではありません。
- 通常 engine の `--serve` 起動時、RAM 計測ができない場合は memory guard が駐車・session 保存・復元を拒否する旨を stderr に出します。通常の park が RAM admission を通らない場合は `skip parking` を stderr に記録し、要求された会話を cache に格納しません（`engine/src/program/generate.cpp:4744-4758,14433-14439`）。

## 出力とエラー

起動時に RAM 計測できた場合、memory guard のログに limit、available、MemAvailable、設定された floor が出ます。値が大きくて自動 cache が1024 MiB未満になる場合は cache を無効にした旨を stderr に出します（`engine/src/program/generate.cpp:4744-4758,13869-13876`）。通常の park 不許可は処理全体の parser error ではなく `skip parking` として扱われます（`engine/src/program/generate.cpp:14433-14439`）。

## 根拠

- `engine/src/program/generate.cpp:1093,1295-1301,4084-4100` — 通常 engine の既定値、help、型変換・範囲検証・代入。
- `engine/include/strata/core/conversation_memory.hpp:128-146` — 自動予算の計算式と、必要量に floor を加えた admission 条件。
- `engine/src/program/generate.cpp:13850-13878,14374-14444` — cache 自動予算への適用、park 判定と見送り・eviction。
- `engine/src/program/generate.cpp:18662-18684,18732-18747` — session 保存・復元時の RAM gate。
- `engine/src/core/conversation_memory.cpp:378-408,411-439` — Linux / Windows / macOS の使用可能 RAM 計測。
- `engine/sycl/src/program/generate.cpp:726-728,2065-2078,8454-8468` — SYCL 版の既定値、parser、park gate。
