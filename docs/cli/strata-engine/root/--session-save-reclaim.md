# `--session-save-reclaim`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。`--serve` の SAVE 処理で使用） |
| オプション | `--session-save-reclaim` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

`--serve` のセッション SAVE で、RAM の事前判定を通すために必要なら再構築可能な host cache を解放します。既定では無効です。SAVE が必要とする RAM の見積もりと `--conversation-cache-min-free-mib` の空き容量下限を使い、再利用 cache、parked conversation、保存対象外の checkpoint の順に解放を試みます。RESTORE には作用しません。

## 使い方

```sh
strata --serve --pack ./model --prompt-cache 1 --session-save-reclaim
```

エンジンを serve モードで起動する引数例です。実際に SAVE を行うとき、RAM 判定に余裕があれば cache 解放は発生しません。`--prompt-cache` はセッションファイルの前提条件です。

## 値と既定値

- 値を取りません。parser はこの引数を見つけると内部フラグを `true` にします。明示値を付ける形式ではありません。
- 既定値は `false` です。同じフラグを複数回指定しても、真偽値を立てる処理が繰り返されるだけです。
- オプション固有の数値 validation はありません。未知の引数は usage を表示して終了コード 2 になります。

## 実行時の動作

SAVE の開始時に、エンジンは live 状態と最深 checkpoint からピーク RAM を見積もり、`--conversation-cache-min-free-mib` の下限と合わせて host RAM の空き容量を判定します。判定前に park pool の idle memory は返却されます。このオプションが有効なら、事前判定に足りないとき `session_save_reclaim` を呼び出します。必要量を満たした時点で停止し、その後通常の SAVE 判定へ進みます。

解放順は、まず保持している再利用 cache、次に古い parked conversation、最後に SAVE で選択されない checkpoint です。parked conversation の明示 pin と、SAVE が選ぶ checkpoint は削除対象から除外されます。checkpoint の削除で cache の状態も変わるため、対象 tail checkpoint がなくなった場合は tail の記録も無効化されます。実際に何か解放した場合、stderr に解放した checkpoint 数・parked 数・host bytes と再判定の旨を出力します。

空き RAM の計測値または必要 RAM の見積もりが不明な場合、reclaim helper は解放を始めず、通常の admission 判定に進みます。解放後も不足、見積もりが不明、または SAVE の他の条件を満たさない場合は成功を保証しません。エンジンは `SERR memory` を返し、診断を stderr に出します。通常の SAVE 成功時は `SAVED` を stdout に出します。

serve 側ではこのフラグ付きの SAVE に限り、RAM 事前判定による未公開の memory refusal で、診断から必要量を読み取れ、同じ engine process が稼働し続けている場合に待機・再試行を行います。RAM 計測が不明なら再試行せず、待機上限は30秒、再試行は最大3回です。待機開始は `[strata] SAVE waiting for RAM after cache reclaim ...` として出力されます。RESTORE、公開済み失敗、その他のエラーはこの再試行経路の対象外です。

## 適用条件と副作用

- `--session-save-reclaim` は `--serve` の SAVE admission にのみ使われ、RESTORE の経路には渡されません。
- セッションファイルの処理では、空でないパス、`--prompt-cache > 0` が必要です。また `--layer-split`、複数 GPU、`--peer-device`、`--batch` は session files と併用できず、SAVE/RESTORE は拒否されます。
- オプションが有効で不足が見込まれると、明示 pin のない parked conversation や、SAVE が使わない checkpoint が失われます。これは host cache の解放であり、live device state の解放・モデルの unload・他プロセスの trim はこの処理では行いません。
- ディスク空き容量の判定は別の SAVE 書き込み処理です。このフラグはディスク容量を増やさず、RAM 解放後にもファイル書き込みや flush が失敗する場合があります。

## 出力とエラー

- reclaim が実行された場合、エンジンは解放量を stderr に記録します。
- RAM 判定に失敗した場合、エンジンは診断を stderr に出し、`SERR <kind> <published> <message>` を stdout に返します。`--session-save-reclaim` を付けても、解放不能・空き RAM 不足などの SAVE 失敗は残ります。
- serve 側の再試行中は待機メッセージが出ます。再試行条件を満たさない、RAM 情報を取得できない、プロセスが終了した、または上限に達した場合は最後の refusal を返します。

## 根拠

- `engine/src/program/generate.cpp:1123` — 内部フラグの既定値は `false`。
- `engine/src/program/generate.cpp:1312-1313` — help における serve 専用・opt-in の説明。
- `engine/src/program/generate.cpp:4071` — parser が値なしのフラグとして受理し、真に設定。
- `engine/src/program/generate.cpp:4268-4273` — 未知引数は stderr に表示し、usage の後に終了コード 2。
- `engine/src/program/generate.cpp:18613-18617` — session path、serve session の非対応構成、`--prompt-cache` の前提条件。
- `engine/src/program/generate.cpp:18662-18690` — SAVE の RAM floor、reclaim 呼び出し、解放ログ、再 admission と memory refusal。
- `engine/include/strata/core/session_save_reclaim.hpp:18-52` — 空き容量判定、解放順、pin と選択 checkpoint の保持、反復計測。
- `engine/src/core/conversation_file.cpp:1195-1212` — SAVE のピーク RAM 見積もりと、保存する checkpoint を最深の一つに絞る処理。
- `engine/src/program/generate.cpp:18583-18591, 18717-18724` — refusal の stderr/stdout プロトコルと成功時の出力。
- `terminal/serve/server.py:772, 4490-4515` — 引数からフラグを認識し、SAVE のみ専用経路に分岐。RESTORE は通常のエンジン呼び出し。
- `terminal/serve/session_save_retry.py:12-21, 35-83` — 再試行条件、30秒・最大3回の待機、計測不明時の中止。

調査対象 Strata checkout の状態は `## main...origin/main` で、未コミット変更はありませんでした。
