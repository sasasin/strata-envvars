# `--memory-limit-mib`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン） |
| オプション | `--memory-limit-mib` |
| 別名 | なし |
| 値 | 非負の10進整数。MiB 単位。最大 `INT64_MAX / 1,048,576` |

## 役割

コンテナや cgroup の実メモリ上限をエンジンから検出できない場合に、その総 RAM 上限を MiB で指定します。値は起動時に RAM ガードへ登録され、`--serve` の会話 park と session の保存・復元で、割り当て可能な空き RAM を見積もる際に使われます。プロセス全体の割り当てを強制的に制限する機能ではありません（`engine/src/program/generate.cpp:1107-1109, 4730-4743`）。

## 使い方

```sh
strata --pack ./model.strata --serve --memory-limit-mib 102400
```

例では、エンジンから見えないコンテナ上限を 100 GiB（102400 MiB）として RAM ガードに知らせます。`--memory-limit-mib` 自体は `--serve` の有無にかかわらず parser が受理されますが、主な利用先は serve の会話 park と session 操作です（`engine/src/program/generate.cpp:1299-1302, 4084-4107`）。

## 値と既定値

- 省略時は `STRATA_MEMORY_LIMIT_MIB` を読みます。環境変数も未設定または空なら、オペレーター指定上限はありません（値 `0`）。フラグに値を指定した場合は環境変数より優先されます（`engine/src/program/generate.cpp:1107-1109, 4729-4742`）。
- 明示した `0` は上限なしを意味し、環境変数の値も使いません。OS から取得する MemAvailable や cgroup の制限は引き続きガードに使われます（`engine/src/program/generate.cpp:4730-4742`; `engine/src/core/conversation_memory.cpp:311-325, 411-437`）。
- CLI 値は `std::from_chars` で10進整数として全体を解析し、負数・小数・不正な文字列・範囲超過は拒否します。`--memory-limit-mib` の後に値がなければ parser の共通処理がエラーにします。同じフラグを複数回指定した場合は、引数を順に解析して後の有効値が設定を置き換えます（`engine/src/program/generate.cpp:3842-3847, 4084-4107`）。
- 環境変数も非負の10進整数で同じ上限まで許容されます。不正値では診断を stderr に出し、終了コード 2 で起動を中止します（`engine/src/program/generate.cpp:4731-4739`）。

## 実行時の動作

起動時に MiB 値をバイトへ変換して RAM ガードのプロセス内設定に保存します。ガードが算出する使用可能量は、MemAvailable（Windows では物理メモリの利用可能量など）、可視範囲の cgroup 制限内の余裕、そしてこのオプションで指定した上限から現在使用量を引いた余裕のうち、最も小さい値です。オペレーター上限の現在使用量は、見えるトップ cgroup の値を使い、cgroup 情報が得られない場合は MemTotal と MemAvailable の差から見積もります（`engine/include/strata/core/conversation_memory.hpp:11-20`; `engine/src/core/conversation_memory.cpp:289-326, 378-408, 411-437`）。

会話の park、session の保存、session の読み込みでは、必要 RAM を上記の利用可能量から確保したうえで、`--conversation-cache-min-free-mib` の空き RAM フロアを残せるか確認します。足りない、または RAM 情報が不明なら該当の park/save/restore は拒否されます。park では条件により park pool や空き heap の回収、保存済み会話の eviction を試みます（`engine/src/program/generate.cpp:14387-14425, 18662-18690, 18734-18757`; `engine/include/strata/core/conversation_memory.hpp:143-146`）。

## 適用条件と副作用

- `--serve` の起動時は、指定値が 0 または未指定でも RAM ガードの状態を診断表示します。正の上限を指定した場合は `--serve` 以外の実行でも起動時診断を表示します。診断には推定上限・現在量・利用可能量・空きフロアなどが含まれます（`engine/src/program/generate.cpp:4742-4758`）。
- RAM 情報を読めない場合、起動時に park と session save/restore を拒否する旨を stderr に出します。これはこの箇所では起動自体を中止しません。操作時には RAM admission が失敗し、park はスキップ、session 操作は拒否されます（`engine/src/program/generate.cpp:4745-4748, 14387-14425, 18677-18690, 18734-18757`）。
- cgroup のメモリ情報が読めない場合、オペレーター上限が設定されていなければ MemAvailable へフォールバックして一度警告します。オペレーター上限があるのに使用量を判定できない場合は RAM サンプルを不明として扱います（`engine/src/core/conversation_memory.cpp:389-397`）。
- この値はメモリ予約やプロセスのハード制限ではありません。サンプル後に他プロセスが RAM を使う可能性もあり、ガードは park/save/restore の可否判定に利用可能量と空きフロアを照合します（`engine/include/strata/core/conversation_memory.hpp:31-34, 143-146`）。

## 出力とエラー

- CLI 値が欠落した場合は `<option> needs a value`、形式・負数・範囲が不正なら `--memory-limit-mib needs a nonnegative integer within range` を stderr に出して終了コード 2 になります（`engine/src/program/generate.cpp:3844-3846, 4091-4097`）。
- 環境変数が不正な場合は `STRATA_MEMORY_LIMIT_MIB needs a nonnegative integer within range` と値を stderr に出し、終了コード 2 で終了します（`engine/src/program/generate.cpp:4731-4739`）。
- serve または正の上限指定時、RAM 情報が得られれば `strata generate: memory guard: limit ...` の診断を stderr に出します。取得できない場合の警告も stderr です（`engine/src/program/generate.cpp:4743-4758`）。

## 根拠

- parser 値の既定値・CLI help 表記: `engine/src/program/generate.cpp:1107-1109, 1299-1302`。
- 値の解析・validation・代入: `engine/src/program/generate.cpp:3842-3847, 4084-4107`。
- 環境変数の優先順位・登録・起動時診断: `engine/src/program/generate.cpp:4729-4758`。
- 利用可能 RAM の定義とオペレーター上限の合成: `engine/include/strata/core/conversation_memory.hpp:11-20`; `engine/src/core/conversation_memory.cpp:289-326, 378-408, 411-437`。
- park/save/restore の admission と拒否経路: `engine/src/program/generate.cpp:14387-14425, 18662-18690, 18734-18757`; `engine/include/strata/core/conversation_memory.hpp:143-146`。

調査範囲は上記 revision の Strata ソースです。同一 revision の CLI help バイナリは実行しておらず、help 表記はソース内の usage 定義と照合しました。
