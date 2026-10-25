# <code>--conversation-cache-min-free-mib</code>

調査対象: Strata commit <code>7dd5cf18e68c639a8773e096c5c79f971ea2a9f5</code>（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | <code>strata-engine</code> |
| コマンド | <code>strata</code>（ネイティブ推論エンジン、トップレベル） |
| オプション | <code>--conversation-cache-min-free-mib</code> |
| 別名 | なし |
| 値 | MiB 単位の非負整数。最大値は <code>INT64_MAX / (1024 * 1024)</code>（8,796,093,022,207） |

## 役割

<code>--serve</code> の会話キャッシュの自動サイズ決定と、会話の退避・セッションファイルの保存・復元で維持する RAM の下限を指定します。下限の判定には、MemAvailable、cgroup の制限、および <code>--memory-limit-mib</code> で設定された上限を反映した利用可能 RAM が使われます（<code>src/program/generate.cpp:895-899</code>、<code>src/core/conversation_memory.cpp:258-288</code>）。

## 使い方

<pre>strata --serve --conversation-cache-min-free-mib 4096 ...</pre>

値はサーバー起動時に設定します。セッション保存・復元も同じ <code>--serve</code> プロセス内で行われ、この RAM 下限が適用されます（<code>src/program/generate.cpp:12094-12099</code>）。

## 値と既定値

- 省略時は <code>2560</code> MiB です（<code>src/program/generate.cpp:731</code>）。
- parser は値全体を整数として変換し、<code>0</code> から <code>INT64_MAX / (1024 * 1024)</code> までを受理します。小数、範囲外、負数などは拒否されます（<code>src/program/generate.cpp:2641-2653</code>）。
- 値を省略すると <code>--conversation-cache-min-free-mib needs a value</code> を stderr に出し、終了コード 2 で終了します（<code>src/program/generate.cpp:2418-2420</code>）。不正値は <code>--conversation-cache-min-free-mib needs a nonnegative integer within range</code> を stderr に出し、終了コード 2 になります（同:2651-2653）。
- 同じオプションを複数回指定すると、parser のループで後から代入された値が使われます（<code>src/program/generate.cpp:2416-2420</code>、2641-2657）。

## 実行時の動作

- <code>--conversation-cache-mib</code> を省略した場合、<code>--serve</code>、<code>--prompt-cache > 0</code>、<code>--conversation-cache-slots > 0</code> の条件下で、モデル読込後の利用可能 RAM からこの下限を差し引き、その 40% を基準に自動キャッシュ容量を決めます。容量は最大 8192 MiB、256 MiB 単位に切り下げられ、1024 MiB 未満になる場合や RAM を読めない場合は 0（キャッシュ無効）です（<code>src/program/generate.cpp:9373-9389</code>、<code>include/strata/core/conversation_memory.hpp:67-78</code>）。
- <code>--conversation-cache-mib</code> に明示値を指定すると、自動容量計算は行いません。ただし、実際に会話スナップショットを退避する際の RAM 下限チェックは残ります（<code>src/program/generate.cpp:9373-9379</code>、9565-9595、9615-9621）。
- 退避時は新規スナップショットに必要な追加 RAM と下限を満たすか確認します。満たさない場合、最古の退避済み会話を順に eviction して再確認します。eviction 後も満たせなければ今回の退避を見送り、既に行った eviction は戻しません。スナップショット作成後にも下限を再確認し、割り込んで下限を割った場合は保存を見送ります（<code>src/program/generate.cpp:9567-9599</code>、9600-9626）。判定は利用可能 RAM が読めない場合も不成立になります（<code>include/strata/core/conversation_memory.hpp:82-85</code>）。
- セッション保存では、コピー前の RAM 事前確認にこの下限を渡します。<code>--session-save-reclaim</code> 併用時は、その処理がチェックポイントや退避済み会話を解放して再確認する場合があります（<code>src/program/generate.cpp:12117-12170</code>）。セッション復元でも、読み込み時の必要 RAM に対して同じ下限を保てるか確認します（同:12212-12231）。
- <code>--memory-limit-mib</code>（未指定時は <code>STRATA_MEMORY_LIMIT_MIB</code>）は RAM 判定の上限側を設定し、このオプションはその範囲内で空けておく量を設定します。フラグが環境変数より優先されます（<code>src/program/generate.cpp:2924-2937</code>）。<code>--session-min-free-mib</code> は保存先ディスクの空き容量を制御する別設定で、この RAM 下限とは別です（同:12185-12192）。

## 適用条件と副作用

主な適用先は <code>--serve</code> の会話キャッシュと、そのサーバーで実行するセッション保存・復元です。通常の非 serve 推論で会話キャッシュやセッション操作を行わない場合、この値による RAM admission 判定は使われません。起動時の RAM ガード表示は serve 時、または <code>--memory-limit-mib</code> の有効値がある場合に行われ、設定した floor も表示されます（<code>src/program/generate.cpp:2924-2953</code>）。

会話キャッシュの退避は、<code>--prompt-cache 0</code> または <code>--conversation-cache-slots 0</code> でも無効になります（<code>src/program/generate.cpp:2956-2958</code>）。セッションファイルは別途 <code>--prompt-cache > 0</code> が必要です（同:12094-12099）。

## 出力とエラー

- 会話キャッシュの自動容量が正数なら容量を stderr に表示し、容量 0 の場合は「not enough free RAM」としてキャッシュ無効を表示します（<code>src/program/generate.cpp:9380-9386</code>）。
- 退避時に容量・RAM 条件を満たせない場合は stderr に skip 理由を出します。物理 RAM 条件の不足では必要な MiB、設定した floor、RAM 判定の説明、eviction 数と残存件数を表示します（<code>src/program/generate.cpp:9560-9599</code>）。キャプチャ後に下限を満たせない場合も stderr に理由を出して退避を見送ります（同:9615-9621）。
- 起動時に利用可能 RAM を読み取れないと、stderr に memory guard の注意が出ます。セッション保存・復元は RAM を読み取れない場合も admission 不成立となり、理由を含む <code>SERR</code> を stdout に出してその操作を拒否します（<code>src/program/generate.cpp:2940-2943</code>、12157-12170、12214-12231）。

## 根拠

- 索引上の配置とスコープ: <code>docs/cli/README.md:9-12</code>、<code>docs/cli/README.md:1134-1153</code>（調査対象リポジトリ内）。
- option の既定値・help 表示・parser と validation: <code>src/program/generate.cpp:731</code>、<code>src/program/generate.cpp:893-899</code>、<code>src/program/generate.cpp:2416-2420</code>、<code>src/program/generate.cpp:2641-2661</code>。
- 自動容量決定と RAM admission helper: <code>src/program/generate.cpp:9373-9389</code>、<code>include/strata/core/conversation_memory.hpp:67-85</code>。
- 会話の退避と eviction: <code>src/program/generate.cpp:9560-9627</code>。
- セッション保存・復元の RAM 確認: <code>src/program/generate.cpp:12117-12170</code>、<code>src/program/generate.cpp:12212-12231</code>。
- RAM 上限の設定と起動時表示: <code>src/program/generate.cpp:2924-2953</code>、<code>src/core/conversation_memory.cpp:258-288</code>。

この調査ではソース checkout の実装を確認しました。安全に実行できる同一 revision の生成済み CLI help と公式 Release 配布物は確認していません。

