# `EXPECT_B`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`EXPECT_B` は Strata の engine や host の設定ではなく、同梱の実アプリ確認スクリプト `apps/host/scripts/agent-flow.mjs` 専用の入力です。二つの chat を同時に動かす任意の確認フローで、2つ目の chat に期待する表示テキストを指定します。Strata のアプリ本体がこの名前を読み取る参照は見つかりません。

## 値と判定

| 状態 | `EXPECT_B` の扱い |
|---|---|
| 未設定 | 期待テキストを `the other chat` にする |
| 空文字 | null 合体演算子 `??` の右辺は使わず、空文字を期待テキストとして渡す |
| その他の設定値 | 文字列のまま Playwright の `page.getByText(...).first().waitFor(...)` に渡す。数値変換、trim、真偽値 parse、独自の範囲検査はない |

この読み取りで CLI 引数や別の環境変数との優先順位はありません。確認対象の prompt は別変数 `PROMPT_B`（未設定時は `SCRIPT:echo the other chat`）で、`EXPECT_B` はその応答の表示確認に使われます。

## 有効になる条件

この値を読むのは `TWO_CHATS` が文字列として厳密に `1` の場合だけです。`TWO_CHATS` が未設定、空、または `1` 以外なら二チャット確認ブロック全体が実行されず、`EXPECT_B` も参照されません。スクリプトは実アプリを Chrome で開く QA 用の流れであり、engine の backend、モデル処理、サーバー設定を変更しません。

## 実行時の詳細

`EXPECT_B` は二チャット確認の応答待ちに達した時点で一度 `process.env` から読み取られます。値をキャッシュする helper はなく、スクリプト内でこの変数を書き換える箇所もありません。期待テキストが見つかるまで最大 60 秒待ちます。その待機が失敗すると共通 `catch` に入り、`FAIL <error.message>` を標準出力へ出し、`zz-failure.png` を保存し、最後に終了コード 1 で終了します。待機に成功した場合は次のチェックポイントへ進みます。

## 根拠

- `apps/host/scripts/agent-flow.mjs:124-147` — `TWO_CHATS === '1'` の条件、`PROMPT_B` の既定値、`EXPECT_B` の既定値と60秒待機、後続チェック。
- `apps/host/scripts/agent-flow.mjs:149-156` — 例外時の `FAIL` 表示、失敗画像の保存、終了コード。
- `apps/host/server/agent/README.md:114-118` — `agent-flow.mjs` を Tests 節で案内し、実アプリを Chrome で操作して screenshot を取るスクリプトと説明。

候補一覧 `docs/envvars/000_envvers.md` には名前がありますが、ソース全体の完全一致検索で確認できた参照はこの QA スクリプトの一箇所だけです。通常の Strata 実行時設定としての利用は確認できません。
