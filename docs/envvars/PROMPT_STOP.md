# `PROMPT_STOP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの調査開始時 status は `## main...origin/main` で、未コミット変更はなかった。

## 役割

`apps/host/scripts/agent-flow-s4b.mjs` が実アプリを Chrome で操作するフローの最後に送る prompt 文を指定します。既定文は、二つの helper agent に作業させ、完了後に Stop 操作を検証する内容です。この変数を読むのは同スクリプトだけで、Strata のサーバーや通常のアプリ起動経路が読む設定ではありません。スクリプトの冒頭コメントは実アプリの S4b フローを実行しスクリーンショットを取得する用途を示しています（`apps/host/scripts/agent-flow-s4b.mjs:1-14`）。

## 値と判定

| 環境値 | 採用される値 |
|---|---|
| 未設定 | 既定 prompt（下記） |
| 空文字 | 空文字。そのまま送信され、既定値には置き換わらない |
| その他の設定値 | 文字列全体をそのまま送信 |

既定 prompt は `Start two helper agents with the subagent tool at once. Each one writes a long, detailed essay of at least 1500 words (one on the history of clocks, one on the history of bridges) and saves nothing. Tell me when they finish.` です。

実装は `process.env.PROMPT_STOP ?? <既定値>` です。Node.js の環境値が `undefined` の場合にだけ既定値を使い、空文字を含む設定値の内容検証、変換、境界判定、無効値 fallback はありません。CLI 引数や別の環境変数との上書き優先順位も実装されていません（`apps/host/scripts/agent-flow-s4b.mjs:29`）。

## 有効になる条件

- Node.js からこのスクリプトを実行し、モジュール初期化が完了すること。
- スクリプトの先行フローを通過し、4 番目の「Stop during helpers」段階に到達すること。この段階はそれ以前の UI 操作、prompt、カード処理に続いて実行されます（`apps/host/scripts/agent-flow-s4b.mjs:82-134`）。

スクリプトは通常、`STRATA_URL` が未設定なら初期化直後に `STRATA_URL is required` を標準エラーへ出して終了コード 2 で終了するため、Stop prompt は送信されません（`apps/host/scripts/agent-flow-s4b.mjs:20-21`）。また、Chrome 起動やページ操作などで例外が発生すると catch 節へ移り、`FAIL <error.message>` を出して最終的に終了コード 1 となるため、4 段階目に届かない場合があります（`apps/host/scripts/agent-flow-s4b.mjs:35-40,153-161`）。

## 実行時の詳細

値はスクリプトのモジュール初期化時に `const PROMPT_STOP` として一度読みます。この値は最後の段階で `send(PROMPT_STOP)` に渡され、`send` は最初の textarea に文字列を入力して `Send` ボタンをクリックします（`apps/host/scripts/agent-flow-s4b.mjs:29,41,134-136`）。同一プロセス中に環境値を変えて再読込する処理や子プロセスへの転送はありません。

スクリプトは送信後に streaming 開始、subagent 実行中表示を待ち、Stop ボタンをクリックして active turn と helper の停止を確認します（`apps/host/scripts/agent-flow-s4b.mjs:136-151`）。設定した文面が実際のモデル応答や helper 起動を生むこと自体は保証されず、そこはこのスクリプトによる環境変数の処理範囲ではありません。待機 timeout などの例外は catch され、失敗メッセージと終了コード 1 になります（`apps/host/scripts/agent-flow-s4b.mjs:42,137,153-161`）。

## 根拠

- 候補一覧の記載: `docs/envvars/000_envvers.md:513`。
- この名前の唯一のコード参照（用途コメント、環境値読み取り、送信）: `apps/host/scripts/agent-flow-s4b.mjs:14,29,135`。
- UI 送信方法と後続の観測・失敗経路: `apps/host/scripts/agent-flow-s4b.mjs:41-42,134-161`。
- 実アプリ操作用スクリプトであることの説明: `apps/host/scripts/agent-flow-s4b.mjs:1-14`。
