# `strata --conversation-spill-persist`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--conversation-spill-persist` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

`--serve` 中に会話キャッシュの SSD tier へ退避した会話を、エンジンの正常終了や再起動後も保持し、同じモデルと実行設定で次回起動したときに再利用できるようにします。RAM 内の会話キャッシュ全体を保存する指定ではなく、SSD tier に書かれたエントリの保存期間を変えるフラグです。

## 使い方

```sh
# データディレクトリ配下の pack を使って serve を起動し、SSD tier の会話を再起動後も保持する
strata --serve --pack /srv/strata/packs/example --conversation-spill-persist
```

`--pack` が `<data>/packs/<tag>` の形式でない場合は、spill の保存先を `--conversation-spill-dir` で指定してください。SSD tier 自体を無効にする `--conversation-spill-mib 0` と併用した場合、このフラグによる保存は行われません。

## 値と既定値

値は不要です。parser は指定されると `conversation_spill_persist` を `true` にし、既定値は `false` です。複数回指定しても同じ真偽値を再設定するだけです。parser にこのフラグ固有の値検証はありません。引数解析は `engine/src/program/generate.cpp:4104` にあります。

## 実行時の動作

この指定は SSD tier を作るときだけ参照されます。通常の engine parser は `engine/src/program/generate.cpp:1110-1120` と `engine/src/program/generate.cpp:4104`、SYCL parser は `engine/sycl/src/program/generate.cpp:735-739` と `engine/sycl/src/program/generate.cpp:2081` にあります。

serve 側で会話キャッシュが有効、layer split なし、かつ `--conversation-spill-mib` が `0` でない場合に spill 初期化へ進みます。保存先は `--conversation-spill-dir` が指定されていればそのパス、なければ `--pack` が `<data>/packs/<tag>` 内にある場合の `<data>/conversation-spill` です。該当する data folder がなければ tier は開始されません（`engine/src/program/generate.cpp:13956-13987`）。ディスク空き容量と `--session-min-free-mib` の空き容量下限を考慮し、tier の上限が 64 MiB 未満なら SSD tier を無効にします。`--conversation-spill-mib` が正ならその MiB 値と利用可能容量の小さい方、未指定なら空き容量の 25%（上限 32 GiB）を基準にします（`engine/src/program/generate.cpp:13979-13987`; 既定予算の式は `engine/include/strata/core/conversation_spill.hpp:57-64`）。

有効な場合、保存場所は `<root>/fp-<model fingerprint>` です。起動時にモデルと設定の identity を計算し、両方が一致する有効な spill entry を採用します。別設定の entry、壊れた entry、途中ファイルなどは採用されず、フォルダ内の不要ファイルとして削除されます（`engine/src/program/generate.cpp:13991-14001`; `engine/include/strata/core/conversation_spill.hpp:284-301,528-594`）。モデル fingerprint のフォルダを開けない場合、同じモデルの別 engine がロックを保持している場合などはプロセス専用フォルダへフォールバックし、永続化されません（`engine/include/strata/core/conversation_spill.hpp:172-217`）。

SSD tier へ書かれるのは、RAM 側の退避・容量判定で SSD tier が必要になった会話のうち、再読込より SSD 往復が有利と見積もられたものです。RAM に収まる会話や layer split の stage image は SSD tier に入りません（`engine/src/program/generate.cpp:13956-13965,14015-14029`）。永続フォルダの entry は読み戻してもディスク上に残り、容量確保時に LRU で削除されます。同一会話のより長い spill が既存の短いものを置き換える場合もあります（`engine/include/strata/core/conversation_spill.hpp:284-287,390-419,463-467,528-594`）。

## 適用条件と副作用

- `--serve` で会話キャッシュと SSD tier が有効な場合に適用されます。`--conversation-spill-mib 0`、layer split、tier の容量不足、利用可能な保存先がない場合には永続化されません（`engine/src/program/generate.cpp:13965-13987`）。
- `--conversation-spill-dir` は root の場所を、`--conversation-spill-mib` は上限を、`--session-min-free-mib` は残す空き容量を左右します。永続化フラグ自体はこれらを上書きしません（`engine/src/program/generate.cpp:13967-13987`）。
- 永続化モードで起動すると、root 内のロックされていない別 fingerprint の永続フォルダも削除対象になります。対象は spill namespace と認識される実ディレクトリで、稼働中の engine がロックしているフォルダや通常のファイル・シンボリックリンクはこの走査で削除されません（`engine/include/strata/core/conversation_spill.hpp:238-254`）。
- 保存期限はありません。容量上限に達した場合の LRU 削除、または同一会話のより長い spill への置換で消えます。再採用時にモデル・設定 identity が異なる entry は残りません（`engine/include/strata/core/conversation_spill.hpp:284-287,528-594`）。
- 正常終了時、永続 namespace は残ります。フラグなし、または永続 namespace を取得できずプロセス専用 namespace になった場合、その namespace は終了時に削除されます（`engine/include/strata/core/conversation_spill.hpp:163-170,219-229`）。

## 出力とエラー

serve の標準エラーには SSD tier の保存先と上限が表示され、永続 namespace が使われた場合は採用した会話数も表示されます。利用できない場合は `no SSD tier: <理由>` が出ます（`engine/src/program/generate.cpp:14001-14012`）。モデル fingerprint を計算できない場合は警告を出し、プロセス専用フォルダを使います（`engine/src/program/generate.cpp:13992-13999`）。その後の会話で fingerprint を計算できなければ、SSD tier を閉じて以後の spill を停止します（`engine/src/program/generate.cpp:14031-14040`）。

## 根拠

- `engine/src/program/generate.cpp:1110-1120,4104` — 通常 engine parser の既定値とフラグ設定。
- `engine/sycl/src/program/generate.cpp:735-739,2081,8242-8262` — SYCL engine parser と同等の初期化・ログ経路。
- `engine/src/program/generate.cpp:13956-14012` — serve 適用条件、保存先・容量決定、persistent identity、初期化、出力。
- `engine/src/program/generate.cpp:14015-14043` — spill 対象判定と fingerprint 失敗時の停止。
- `engine/include/strata/core/conversation_spill.hpp:172-229,284-301,390-419,528-601` — stable namespace、ロック・終了時処理、再採用・読み戻し・削除規則。
