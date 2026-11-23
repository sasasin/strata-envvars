# `STRATA_AGENT_WORKING_MEMORY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この環境変数は Strata の Node agent host が生成する Harness profile に、Strata working-memory と edit-recovery のプラグインを加えるかを制御する。エンジンの推論設定ではなく、Harness を介した agent chat の機能である。working-memory は次の人間の依頼時に同じ chat の過去作業の短い brief を入力へ加え、edit-recovery は古い内容に基づく edit の失敗後に現ファイルの再読を促す。`app/host/server/agent/agent-bridge.mjs:250-256`、`app/host/server/agent/profile.mjs:61-62,314-317,461-465`、`app/host/server/agent/plugins/strata-working-memory.mjs:120-142`、`app/host/server/agent/plugins/strata-edit-recovery.mjs:35-50`。

## 値と判定

`createAgentBridge` が受け取る `env`（既定は `process.env`）の値を、profile を作るたびに `env.STRATA_AGENT_WORKING_MEMORY === '1'` で比較する。文字列全体の厳密な一致であり、数値変換・trim・大文字小文字の変換はない。未設定と空文字は無効。`'1'` だけが有効で、`'0'`、`'true'`、`'01'`、`' 1'`、`'1 '`、`'TRUE'` などは無効となる。既定値は無効。別の環境変数、CLI 引数、設定ファイルによる優先・上書きはこの判定にない。`app/host/server/agent/agent-bridge.mjs:160,250-256`。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Node agent host の profile 生成 | 無効 | `'1'` | 空文字、`'0'`、`'true'`、`'01'`、空白付きの値など `'1'` 以外 |

## 有効になる条件

- Strata の Node host が agent bridge を使う経路であること。通常のエンジン推論そのものを切り替える変数ではない。`app/host/server/index.mjs:21,214-240`。
- Harness profile 生成時に値が文字列 `'1'` であること。profile では `strata-working-memory` と `strata-edit-recovery` が同じ条件で追加される。`app/host/server/agent/agent-bridge.mjs:250-256`、`app/host/server/agent/profile.mjs:461-465`。
- agent の有効なモデル route が必要。route がなければ `ensureRuntime` は `model-unavailable` として Harness を開始しないため、追加プラグインも実行されない。`app/host/server/agent/agent-bridge.mjs:334-356`。
- working-memory が brief を挿入するのは、既存 session の人間による依頼、`agent/pre-step` の `enter` 判定、step 1、abort されていない場合であり、fork / subagent の session では挿入しない。該当履歴から brief が組み立てられない場合も追加メッセージはない。`app/host/server/agent/plugins/strata-working-memory.mjs:120-142`。
- OS、GPU backend、build macro、サーバー CLI オプションによる有効値の違いは、この環境変数の分岐にはない。Windows では working-memory 内のファイルパス照合を小文字化するが、有効化条件ではない。`app/host/server/agent/plugins/strata-working-memory.mjs:17-20`。

## 実行時の詳細

`createAgentBridge` の `env` 引数は既定で `process.env` への参照である。`buildProfileNow()` は `status()` および `ensureRuntime()` から呼ばれ、その都度環境値を読み直して profile を生成する。値自体の static cache はない。`app/host/server/agent/agent-bridge.mjs:160,250-256,275-280,334-340`。

有効時の profile には working-memory plugin と edit-recovery plugin の両方が入り、無効時はどちらも入りません。working-memory は過去の session log から直近の人間の依頼、todo、tool の結果などを最大 3,000 byte の brief にまとめ、同じ session の新しい依頼の前に user message として挿入します。tool の出力やファイル内容は brief に再掲せず、working brief がないときには追加しません。履歴走査には末尾 2,048 件の event を使い、一部の依頼・todo・turn end は末尾から別途探索します。`app/host/server/agent/plugins/strata-working-memory.mjs:7-10,38-117,120-142`。

注意点として、実行中に `env` オブジェクトの値を変更しても、既存 Harness は必ずしも再起動されない。`ensureRuntime()` の既存 runtime 再利用判定は tools signature と route を比較し、working-memory の有無はその比較に含めない。新たに Harness を開始する場合は、その時点で生成した profile が使われる。通常のプロセス環境変数を起動後に変える機能や、設定画面・CLI からの変更経路は確認できない。`app/host/server/agent/agent-bridge.mjs:339-356`、`app/host/server/agent/profile.mjs:484-493`。

## ログと測定値

この環境変数の値やプラグインの有効・無効を知らせる専用ログ、警告、終了コードは見つからない。Harness の一般的な起動ログはあるが、当変数の判定結果を記録するものではない（`app/host/server/agent/agent-bridge.mjs:322`）。対象機能について Strata 資料に条件付き測定値はない。

## 根拠

- `app/host/server/agent/agent-bridge.mjs:160,250-256` — env の既定値と値判定、profile 生成。
- `app/host/server/agent/agent-bridge.mjs:275-280,334-356` — profile の呼出し時期、route 要件、runtime の再利用・起動。
- `app/host/server/agent/profile.mjs:61-62,314-317,461-465,484-493` — plugin の組み立て、profile signature と runtime 比較用 tools signature。
- `app/host/server/agent/plugins/strata-working-memory.mjs:7-10,38-117,120-142` — brief の構成上限と挿入条件。
- `app/host/server/agent/plugins/strata-edit-recovery.mjs:35-50` — edit-recovery の介入条件と案内文。
- `app/host/server/index.mjs:21,214-240` — Strata server から agent bridge を構成する経路。
