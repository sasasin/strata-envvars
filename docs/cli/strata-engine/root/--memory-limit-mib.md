# `--memory-limit-mib`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--memory-limit-mib` |
| 別名 | なし |
| 値 | MiB 単位の 0 以上の整数。最大値は `INT64_MAX / 1,048,576`（8,796,093,022,207 MiB） |

## 役割

コンテナや cgroup の実際の RAM 上限をプロセスから検出できない場合に、エンジンが RAM ガードで用いる総量上限を指定します。RAM ガードは `--serve` の会話キャッシュ退避（parking）と session の保存・復元で、処理後にも残す空き RAM の判定に使われます。モデル本体や通常の生成用メモリをこの値で予約・制限する設定ではありません。parser は `--serve` なしでも値を受け取りますが、会話キャッシュと session 操作は serve 経路です。

## 使い方

```sh
strata --serve --memory-limit-mib 102400
```

環境変数 `STRATA_MEMORY_LIMIT_MIB` でも同じ上限を指定できます。環境変数の詳細は [`STRATA_MEMORY_LIMIT_MIB`](../../../../docs/STRATA_MEMORY_LIMIT_MIB.md) を参照してください。

## 値と既定値

- 値は符号なしの十進整数として読み取られます。負数、空値、数字以外を含む値、整数変換の overflow、上限超過は拒否されます。0 は上限なしを意味します。
- CLI で省略したときは `STRATA_MEMORY_LIMIT_MIB` を読みます。環境変数も未設定または空なら上限なし（0）です。CLI の値は環境変数より優先し、CLI に `0` を渡した場合も環境変数を無効化します。
- 同じ CLI オプションを複数回指定した場合、parser のループで後から読んだ値が設定を置き換えます。
- 上限の最大値は `INT64_MAX / (1024 * 1024)` MiB で、MiB から byte への変換が符号付き整数の範囲を超えない値です。

## 実行時の動作

エンジンは起動時に上限を byte に変換して RAM サンプラーへ一度設定します。空き RAM の見積りは `MemAvailable`、認識できる cgroup の `memory.max` / `memory.high`（v2）または `memory.limit_in_bytes`（v1）の各残量、および明示した上限から計算した残量のうち最小値です。明示上限の残量は、トップ可視 cgroup の使用量（または cgroup が使えない場合は `MemTotal - MemAvailable`）から、再利用可能と判定された clean inactive file cache を差し引いて求めます。設定値は予約ではなく、サンプル後に他プロセスが RAM を使う可能性があります。

この空き RAM に対して `--conversation-cache-min-free-mib` の床を残せるか判定します（既定 2560 MiB）。会話スナップショットが床込みで収まらないとき、serve は古い退避済み会話を順に追い出して再確認し、それでも不足なら新しい parking を見送ります。session の保存・復元でも同じ RAM サンプルと床を使い、必要量を加えて不足する場合は操作を拒否します。session 保存で `--session-save-reclaim` を指定すると、RAM 再確認前に保持キャッシュ等を解放する処理があります。

## 適用条件と副作用

- `--serve` 起動時は RAM ガードの診断を stderr に出します。serve 以外では、正の上限を指定した場合に診断を出します。上限 0 かつ serve 以外では初期サンプルの診断は出ません。
- Windows は `GlobalMemoryStatusEx` から物理 RAM と page file の空きの小さい方を使い、明示上限を重ねます。Linux は `/proc/meminfo` と可視 cgroup 階層を参照します。cgroup の使用量・上限情報が読み取れず、明示上限がある場合、見積りは不明扱いとなり RAM ガードは fail-closed になります。上限なしの場合は cgroup 条件を捨てて `MemAvailable` にフォールバックし、一度 stderr に警告します。
- それ以外の OS ではこのサンプラーは値を返さない実装です。そこでの RAM ガード成功は確認できません。
- 明示上限が実環境の制限より大きい場合も、実 cgroup 制限と `MemAvailable` の方が小さければそちらが判定を支配します。逆に実上限が見えず指定値が過大なら、見積りも実際より大きくなり得るため、運用者がコンテナの上限を正しく指定する必要があります。

## 出力とエラー

- CLI の値がない場合は `--memory-limit-mib needs a value` を stderr に出し、終了コード 2 で終了します。
- CLI 値が負数・不正形式・範囲外の場合は `--memory-limit-mib needs a nonnegative integer within range` を stderr に出し、終了コード 2 で終了します。
- CLI を省略し、環境変数が不正なら `STRATA_MEMORY_LIMIT_MIB needs a nonnegative integer within range ...` を stderr に出し、終了コード 2 で終了します。ただし CLI の値がある場合は環境変数を検証せず、CLI 値が優先されます。
- serve 起動時に RAM 情報を読めないと `parking and session save/restore are refused` と stderr に表示します。個々の parking は見送りとなり、session 保存・復元は不足理由を伴って拒否されます。診断出力自体は起動時サンプルの失敗表示であり、serve プロセス全体をその場で終了させる分岐ではありません。

## 根拠

- 索引上の階層と option scope: `docs/cli/README.md:1128-1135,1201`（調査対象 checkout 側の相対位置）。
- parser 値型・既定値: `src/program/generate.cpp:741-745`。
- help の serve 適用説明: `src/program/generate.cpp:895-900`。
- 値の取得、整数形式・範囲検証、CLI 値への格納: `src/program/generate.cpp:2418-2421,2641-2661`。
- 環境変数の fallback、CLI 優先、byte 変換、初期診断と不明時メッセージ: `src/program/generate.cpp:2924-2953`。
- 空き RAM 推定、cgroup と明示上限の合成、fail-closed/fallback、Windows/Linux の取得方法: `include/strata/core/conversation_memory.hpp:10-30,55-65`、`src/core/conversation_memory.cpp:203-238,258-291`。
- 自動会話キャッシュ予算での RAM サンプル利用: `src/program/generate.cpp:9373-9389`、予算計算は `include/strata/core/conversation_memory.hpp:67-77`。
- parking の再試行、古い会話の eviction、見送り出力: `src/program/generate.cpp:9570-9599,9615-9620`。
- session 保存・復元の RAM gate とエラー理由: `src/program/generate.cpp:12122-12170,12209-12222`。
- 環境変数文書: `docs/STRATA_MEMORY_LIMIT_MIB.md`（環境変数の仕様参照用。上記の CLI 効果は parser と使用箇所から確認）。

## 調査範囲

調査対象 checkout は commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5` で、`git status --short --branch` は `## main...origin/main` でした。対象 parser、RAM sampler、parking と session の使用箇所をソースで確認しました。既存バイナリの `--help`、Release 配布物、全 OS/backend の実機動作は確認していません。
