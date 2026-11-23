# `STRATA_UPDATE_PAUSE_FILE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata のアプリ内エージェント（Harness）に、更新準備中の作業停止を伝える pause marker のパスを渡す。変数の値を真偽値や更新設定として解釈するのではなく、指定されたパスが存在するかを確認する。アプリの `agent-bridge.mjs` は Harness の起動環境にこの変数を設定し、更新準備時にそのパスへ空ファイルを作成する。エンジン CLI や `terminal/serve` の環境設定ではない。`app/host/server/agent/agent-bridge.mjs:169-173,294-305,2039-2052`、`app/host/server/agent/plugins/strata-context.mjs:54-58`。

## 値と判定

プラグインの `apply()` 時に `process.env.STRATA_UPDATE_PAUSE_FILE` を一度取得する。値が空でない文字列なら marker 機能を設定し、以後の判定ではその文字列をファイルパスとして `existsSync()` に渡す。`"1"` や `"true"` を有効フラグとして解析せず、空白除去・大文字小文字変換・数値変換も行わない。空文字は falsy なので停止判定は常に false となり、未設定時と同じくツール拒否 hook も登録しない。一方、`"0"`、`"false"`、空白だけの文字列も非空パスとして扱われ、そのパスにファイルがあれば停止判定が true になる。パスが存在しなければ false。特別な境界値や無効値の検査、fallback はない。`app/host/server/agent/plugins/strata-context.mjs:54-58`。

アプリ側の Harness 起動時は `{ ...profile.env, STRATA_UPDATE_PAUSE_FILE: pauseMarker }` として後から値を設定するため、`profile.env` に同名値があっても pause marker のパスで上書きされる。通常のアプリ経路では `pauseMarker` は空でないパスである。`app/host/server/agent/agent-bridge.mjs:166-170,294-305`。

| 条件 | 未設定・空文字 | 設定値の例 | 判定 |
|---|---|---|---|
| プラグインを直接起動し、環境から値が来ない | `undefined` / `""` | — | 停止せず、ツール拒否 hook を登録しない |
| プラグインに非空値が渡る | — | `"/tmp/paused"`, `"0"`, `"false"`, `" "` | 値をパスとして使用。該当パスが存在すると停止、存在しなければ継続 |
| Strata アプリが Harness を起動 | アプリ側の元値にかかわらず `pauseMarker` を設定 | `<dataDir>/agent/update-checkpoints/<UUID>/paused` | そのファイルの有無で停止を判定 |

## 有効になる条件

- Strata アプリのエージェント経路で Harness と `strata-context` プラグインが動作すること。プロファイルは `strata-context` を常に挿入する（`app/host/server/agent/profile.mjs:59-60,451-461`）。
- Harness 起動時に渡された marker パスが非空であること。アプリ経路ではホストがパスを環境へ明示的に渡す（`app/host/server/agent/agent-bridge.mjs:294-305`）。
- 停止判定が true になるには、そのパスのファイルが存在すること。更新準備処理は checkpoint 用ディレクトリを作成した後、空の marker ファイルを作る（`app/host/server/agent/agent-bridge.mjs:2039-2052`）。
- OS、GPU backend、モデル、エンジン CLI 引数による分岐はこの変数の読み取り箇所にはない。対象は Strata アプリの Harness 経路であり、環境変数を読まない他の実行経路にはこのプラグインの制御は適用されない（`app/host/server/agent/plugins/strata-context.mjs:54-58`）。

## 実行時の詳細

プラグインの `apply()` が環境変数をローカル定数 `pauseFile` に保存するため、プロセス実行中に環境変数自体を書き換えても参照先パスは変わらない。ファイルの有無は `paused()` が呼ばれるたびに同期的に `existsSync(pauseFile)` で確認するため、同じパスの marker 作成・削除は後続の判定に反映される（`app/host/server/agent/plugins/strata-context.mjs:54-58`）。

marker がある場合、ツールの `tools/pre-execute` hook は `{ kind: 'deny', reason: 'Agent work is paused for the Strata update.' }` を返す。さらに、LLM stream の開始、モデル adapter の準備、adapter の `streamWithSnapshot`、Context Optimizer 後の要約処理でも同じ marker を再確認し、存在時は `Error('Agent work is paused for the Strata update.')` を throw する。したがって進行中の処理も、これらの次のチェック地点で停止要求を検出する。Strata ホスト自身も `prepareForUpdate()` で `updatePaused = true` にし、更新準備の checkpoint 処理を開始する（`app/host/server/agent/plugins/strata-context.mjs:54-58,107-115,125-143,194-203`、`app/host/server/agent/agent-bridge.mjs:2039-2052`）。

## ログと測定値

この変数のチェック自体はログを出さない。プラグイン側で確認できる結果は、ツール拒否の理由文字列 `Agent work is paused for the Strata update.` と、LLM 関連 hook が投げる同じ文言の Error。Strata の資料にこの変数に関する測定値はない（`app/host/server/agent/plugins/strata-context.mjs:54-58,107-115,125-143,194-203`）。

## 根拠

- 環境値の読み取り、空値を含む truthiness 判定、存在確認、ツール拒否: `app/host/server/agent/plugins/strata-context.mjs:18,54-58`。
- LLM と adapter のチェック地点および Error 文言: `app/host/server/agent/plugins/strata-context.mjs:107-115,125-143,194-203`。
- Harness profile によるプラグイン挿入: `app/host/server/agent/profile.mjs:59-60,451-461`。
- marker パスの生成、Harness 環境への設定、更新準備での marker 作成: `app/host/server/agent/agent-bridge.mjs:166-173,294-305,2039-2052`。
