# `EXPECT_AFTER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`EXPECT_AFTER` は Strata の推論・サーバー設定ではなく、同梱のブラウザー smoke-check `apps/host/scripts/agent-flow.mjs` が、チャットを再オープンして追加メッセージを送った後に応答テキストを検査するための任意の期待パターンです。スクリプトの説明では Chrome で実アプリを操作してスクリーンショットを取り、チェックポイントの失敗時には非ゼロ終了するとされています（`apps/host/scripts/agent-flow.mjs:1-21`）。ホストの agent README もこのスクリプトを実アプリ操作用として案内しています（`apps/host/server/agent/README.md:114-118`）。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | `process.env.EXPECT_AFTER` が falsy となり、再オープン後の応答テキスト検査を行わない。 |
| 空文字 | 同じく falsy なので検査を行わない。 |
| 非空文字列 | JavaScript の `RegExp` にそのまま渡し、再オープン後のページで一致するテキストが 1 件以上あるかを検査する。文字列の前処理や正規表現フラグの指定はない。 |
| 不正な正規表現 | `new RegExp(...)` の例外が全体の `catch` に入り、`FAIL <例外メッセージ>` を出力して失敗扱いとなる。 |

値を `1` / `true` と比較したり、真偽値へ変換したりする実装ではありません。非空文字列なら値が `0` や `false` でも検査に進みます。正規表現は文字列全体一致に固定されておらず、コードは `new RegExp(value)` を使います（`apps/host/scripts/agent-flow.mjs:116,149-152`）。

## 有効になる条件

この変数が使われるのは `apps/host/scripts/agent-flow.mjs` を実行し、先行する操作が成功してチャット再オープン後のチェックポイントまで到達した場合だけです。そこで `PROMPT_AFTER` を送信して応答待ちを終えた後に検査します。Strata の通常の実行ファイルやサーバー処理がこの値を読む箇所は確認できません（`apps/host/scripts/agent-flow.mjs:103-116`）。

## 実行時の詳細

環境から値を読む箇所は `process.env.EXPECT_AFTER` の条件判定と、同じ行の正規表現生成・失敗ラベルの組み立てだけです。起動時に別変数へ保存する処理や CLI 引数との優先順位はありません。再オープン後の応答本文にパターンが 1 件以上あれば `check` が `ok  ...` を出し、なければ `FAIL ...` を出して `failed` を立て、スクリプト末尾で終了コード 1 にします。検査を省略した場合も他のチェック結果で最終終了コードが決まります。正規表現生成等で例外が起きた場合は catch が `FAIL` と失敗スクリーンショットを記録し、最後に終了コード 1 となります（`apps/host/scripts/agent-flow.mjs:41-43,103-116,149-156`）。

## 根拠

- `apps/host/scripts/agent-flow.mjs:1-21` — 実アプリを操作する smoke-check であること、チェック失敗時の非ゼロ終了についてのスクリプト説明。
- `apps/host/scripts/agent-flow.mjs:103-116` — 再オープン後の応答を待ち、`EXPECT_AFTER` が truthy の場合に `RegExp` 検査する箇所。
- `apps/host/scripts/agent-flow.mjs:41-43,148-156` — チェック結果の表示、例外処理、終了コード。
- `apps/host/server/agent/README.md:114-118` — `agent-flow.mjs` を実アプリ操作・スクリーンショット用スクリプトとして案内する記述。
