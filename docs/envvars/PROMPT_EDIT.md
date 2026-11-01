# `PROMPT_EDIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/scripts/agent-flow-s4b.mjs` の実モデル向けブラウザーフローで、2 番目の「1 件の編集」手順としてチャットに送るプロンプト文字列を指定します。通常の Strata エンジンやサーバーの設定ではなく、このフロースクリプトだけが環境から値を読みます。未設定時の既定文は `hello.py` を読み、「hello world」と出力するよう編集する指示です（`apps/host/scripts/agent-flow-s4b.mjs:1-14,26-29`）。

## 値と判定

| 環境変数の状態 | スクリプトが使う値 |
|---|---|
| 未設定 (`process.env.PROMPT_EDIT` が `undefined`) | `Read hello.py and then change it so it prints "hello world" instead of "hello". Use the edit tool.` |
| 空文字 | 空文字のまま。既定文には置き換えない |
| その他の設定値 | その文字列をそのまま使用 |

選択には JavaScript の nullish coalescing (`??`) を使い、空文字判定、trim、文字列 parse、長さや形式の検証はしません。したがって、空白だけの値や `"0"` もそのままプロンプトとして渡されます（`apps/host/scripts/agent-flow-s4b.mjs:27`）。

## 有効になる条件

- `node scripts/agent-flow-s4b.mjs` としてこのフローを実行し、ブラウザーで `/#/chat` を開いてモデルを選び、2 番目の編集手順まで処理が進むことが条件です。スクリプト冒頭の説明では `STRATA_URL` が必要で、起動時に未設定なら `STRATA_URL is required` を stderr に出して終了コード 2 で終了します（`apps/host/scripts/agent-flow-s4b.mjs:2-6,20-21,82-93`）。
- `PROMPT_EDIT` 自体に OS、GPU backend、build macro による分岐はありません。`MODEL` は選択するモデル名の既定値に使われますが、`PROMPT_EDIT` の値を上書きしません（`apps/host/scripts/agent-flow-s4b.mjs:24,89-92`）。
- 先行手順で未処理例外が起きると catch 節へ進むため、編集プロンプトは送信されません。通常の実行では、先行チェックが失敗扱いになっても `check()` はフラグを立てるだけで処理を続け、編集手順を実行します（`apps/host/scripts/agent-flow-s4b.mjs:32-33,94-120,153-160`）。

## 実行時の詳細

値はスクリプトのトップレベルで定数 `PROMPT_EDIT` に代入されます。Node.js のモジュール評価時に一度読み取られ、その後の実行中に `process.env` を変更してもこの定数は再評価されません。CLI 引数を読み取る処理や、別の設定値との優先順位処理はありません（`apps/host/scripts/agent-flow-s4b.mjs:16-30`）。

編集手順では `send(PROMPT_EDIT)` を呼びます。`send` は最初の `textarea` に値を入力し、`Send` ボタンをクリックします。続いてスクリプトは承認カードがなくなりストリーミングが終了するまで待ち、編集を求めるカードが一つ以上あったかを記録します。値を空にした場合にもこのコードは既定文へ戻したり送信をスキップしたりせず、空文字を `fill` に渡して Send をクリックします。受信側がそれをどう扱うかはこの変数を読むコードの範囲では規定されていません（`apps/host/scripts/agent-flow-s4b.mjs:41,62-80,119-127`）。

この変数固有の値を表示するログはありません。スクリプトは実行中の検査結果を `ok` / `FAIL` で出力し、未処理例外は `FAIL <error.message>` と失敗スクリーンショットを記録します。最後に `failed` が立っていれば終了コード 1 になります（`apps/host/scripts/agent-flow-s4b.mjs:32-34,119-127,153-161`）。

## 根拠

- 候補一覧には `PROMPT_EDIT` が載っています（調査文書 `docs/envvars/000_envvers.md:510`）。実読み取りは `apps/host/scripts/agent-flow-s4b.mjs:27`、プロンプト送信は同ファイル `:41,119-120` です。
- スクリプトの説明は、この処理を実モデルを使う S4b フローと位置付けています（`apps/host/scripts/agent-flow-s4b.mjs:1-14`）。`apps/host/package.json:7-27` にこの S4b スクリプトを起動する専用 npm script はなく、README の「Tests」節が説明する `scripts/agent-flow.mjs` は別スクリプトです（`apps/host/server/agent/README.md:114-119`）。
- 候補名の全参照は、スクリプト説明コメント、既定値付きの環境読み取り、および送信呼び出しです。ほかに `PROMPT_EDIT` の読み取りや動的 helper への名前渡しは見つかりませんでした。
