# `STRATA_TOOL_MARKUP_RETRY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`terminal/serve/server.py` の `Service` は、この変数からサーバー内の `tool_markup_retry` を初期化します。既定では有効で、対象形式のツール要求に対し、モデルの返答末尾が実行可能な呼び出しとして読めない tool-call markup だった場合、その部分を一度だけ隠してモデルに書き直させます。無効時はこの再試行用の holdback を行わず、markup は通常の出力処理に進みます（`terminal/serve/server.py:4135-4137, 5620-5632`）。

これは `terminal/serve` の Python サーバー設定です。エンジンの生成設定や GPU backend を直接変更しません。run config の `tool_markup_retry` は追加の無効化スイッチで、環境変数が有効でも config が `false` なら無効になります（`terminal/serve/server.py:9104-9107`）。

## 値と判定

Python の `os.environ.get(..., "1")` の戻り値に `.strip().lower()` を適用し、結果が `"0"`、`"off"`、`"false"`、`"no"` のいずれかでなければ有効です。文字列全体をこの 4 値と比較し、数値 parse や真偽値 parse はしません。前後の空白は除かれ、大文字小文字は無視されます。空文字は空文字のまま比較されて該当しないため有効です（`terminal/serve/server.py:4135-4137`）。

| 条件 | 未設定 | 無効になる値 | 有効になる値の例 |
|---|---|---|---|
| サーバーの環境変数判定 | 既定文字列 `"1"` から `True` | `0`、`off`、`false`、`no`（大文字小文字を問わず、前後空白を除去した後） | 空文字、`1`、`true`、`yes`、`00`、`0anything`、その他上記 4 値と一致しない文字列 |

run config の `tool_markup_retry` は省略時 `true` です。boolean 以外（整数の `0`/`1` を含む）は `[strata] config "tool_markup_retry" must be true or false, not ...` で `SystemExit` になります。最終値は環境変数判定値と config 値の論理積なので、config の `false` は環境変数を問わず無効にし、config の `true` は環境変数による無効化を覆しません（`terminal/serve/server.py:9104-9107`）。CLI の独立した retry 引数はこのコード経路にありません。

## 有効になる条件

- 環境変数の判定結果と run config の `tool_markup_retry` がともに有効であること（`terminal/serve/server.py:9104-9107`）。
- リクエストに宣言済みツールがあること。履歴内で使われたツールも `with_history_tools` の一覧に含めて判定します（`terminal/serve/server.py:5620-5626`）。
- `self.family is None` で、parser class が `OutputParser` であること。コメント上、JSON 形式 parser や別 family は再試行対象外です（`terminal/serve/server.py:5623-5626`）。
- モデルが tool-call markup でない返答をし、通常の停止 (`finish == "stop"`) に達すること。キャンセル中、反復・loop 判定済み、reasoning 中、未解決の stop sequence がある場合はこの再試行分岐に入りません（`terminal/serve/server.py:5989-6002`）。
- retry note を追加した後も出力上限に 64 token 以上残ること。満たさない場合は再試行せず、その場で終了します（定数 `TOOL_RETRY_MIN_ROOM = 64`: `terminal/serve/server_parts/core.py:215`; 判定: `terminal/serve/server.py:6003-6008`）。

OS・GPU backend・build macro による環境変数判定の分岐はありません。この設定は Python サーバーが `Service` を作る経路で読み取られます（`terminal/serve/server.py:4135-4137, 8974-8979`）。

## 実行時の詳細

値は `Service` の生成時に読み取られ、インスタンス属性に保存されます。各リクエストで環境を読み直す処理や、この属性を更新する処理は対象コードにありません。従って、起動済みサーバーの環境変数を後から変更しても現在の `Service` には反映されず、反映にはサーバーの再生成が必要です（`terminal/serve/server.py:4135-4137, 8974-8979`）。

再試行対象のリクエストでは、行頭かつコード fence の外にある `<tool_call>` / `<function=...>` から続く text を一時保持します。返答末尾が未完了 (`cut_off`) または閉じているが呼び出しとして読めない (`unreadable`) 場合、または宣言外のツール名を含む場合 (`rejected`) に、元の末尾を捨て、宣言済みツール名と必要なら最も近い名前を示す短い note を同じ request の prompt に加えます。宣言外の名前でツールを実行することはありません。retry は一度だけで、2 回目の返答はそのまま出力されます（`terminal/serve/server_parts/core.py:226-272, 275-340`; `terminal/serve/server.py:5995-6031`）。

条件不足や 64 token の余裕がない場合はこの retry を行いません。retry 後も末尾に読めない markup が残る場合、完了情報に `unread_tool_markup`（理由と文字数）を付けます。開始済みの tool call が途中で切れた場合も、条件に応じて `reason: "cut_off"`、`chars: 0` として通知します（`terminal/serve/server.py:6234-6262`）。

## ログと測定値

再試行したときは stdout に `[strata] the reply ended in tool-call markup that is no call (...)` で始まる行を出し、分類、対象名（あれば）、最も近い宣言名（あれば）、保持した文字数を含めます。最後は `writing the reply's end again once (STRATA_TOOL_MARKUP_RETRY=0 turns this off)` です。分岐に入らない場合や retry 余地が 64 token 未満の場合、この行は出ません（`terminal/serve/server.py:6011-6019`）。

実施した retry は `/metrics` の counter `strata:tool_markup_retries_total` に加算されます。retry が起きなかった場合の増分はありません（`terminal/serve/server.py:6011-6014, 5104-5110`）。最終応答に未読 markup が残った場合は `strata_unread_tool_markup` として API 応答に渡されます（例: Responses API `terminal/serve/responses.py:862-870`; Chat completion `terminal/serve/server.py:6493-6499`）。測定値は該当しません。

## 根拠

- 読み取り、値の変換、`Service` 初期化: `terminal/serve/server.py:4135-4137, 8974-8979`
- run config の既定値・型検証・優先関係: `terminal/serve/server.py:9104-9107`
- リクエスト条件と retry 実行: `terminal/serve/server.py:5620-5632, 5989-6031`; `terminal/serve/server_parts/core.py:215, 226-272, 275-340`
- 結果 metadata と観測経路: `terminal/serve/server.py:6234-6262, 6493-6499, 5104-5110`; `terminal/serve/responses.py:862-870`
