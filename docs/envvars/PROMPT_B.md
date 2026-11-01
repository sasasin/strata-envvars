# `PROMPT_B`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata の作業ツリーは `git status --short --branch` で `## main...origin/main` と表示され、未コミット変更はありません。

## 役割

`PROMPT_B` は Strata アプリの設定ではなく、`apps/host/scripts/agent-flow.mjs` が二つのチャットを並行して動かす確認シナリオで、2番目のチャットに送る文面を指定する環境変数です。このファイルは Chrome で実アプリを操作してチェックポイントとスクリーンショットを記録するスクリプトで、サーバーや生成エンジンの動作を直接設定しません（`apps/host/scripts/agent-flow.mjs:1-10`, `apps/host/server/agent/README.md:114-118`）。

スクリプト内で `PROMPT_B` を読む箇所は一つです。リポジトリ全体の完全一致検索では、それ以外に環境から同名の値を読む実装は見つかりません。`strata_control/vram_fit.py` の `PROMPT_BASE_MIB` は別の定数名です。

## 値と判定

| 状態 | `send()` に渡す値 |
|---|---|
| 未設定 | `SCRIPT:echo the other chat` |
| 設定あり（空文字を含む） | 環境変数の文字列をそのまま渡す |

判定は `process.env.PROMPT_B ?? 'SCRIPT:echo the other chat'` です。Node.js の環境値が未設定 (`undefined`) の場合だけ既定文を使います。空文字 `""` は nullish ではないため、そのまま空の入力として送られます。数値変換、trim、文字列比較、長さや値域の検査はありません（`apps/host/scripts/agent-flow.mjs:137`）。

## 有効になる条件

この読み取りと送信は `TWO_CHATS` が文字列 `1` と完全一致した場合に限られます。未設定、空文字、`true`、`01` などでは二つ目のチャットのシナリオに入らず、`PROMPT_B` は参照されません（`apps/host/scripts/agent-flow.mjs:124-125`）。大文字小文字や数値としての解釈はありません。

## 実行時の詳細

シナリオに入ると、スクリプトは二番目のチャットを開いてモデルを選び、`PROMPT_B`（または既定文）を `send()` に渡します。`send()` は最初のテキストエリアに値を入力し、Send ボタンをクリックします。したがって、Strata に渡されるのは子プロセス向け環境変数ではなく、アプリのチャット欄へ送信されるメッセージ本文です（`apps/host/scripts/agent-flow.mjs:51-55,133-138`）。

環境値はこの分岐の実行時に直接参照され、スクリプト内にキャッシュや後続の環境値伝播処理はありません。送信後は別の変数 `EXPECT_B`（未設定時の既定値は `the other chat`）を含む応答要素を最大60秒待ち、最初のチャットがまだ実行中かを確認します。`EXPECT_B` は検証対象の応答文字列であり、`PROMPT_B` の値や既定値を変更しません（`apps/host/scripts/agent-flow.mjs:137-141`）。

このスクリプトはチェックポイントを標準出力に記録します。待機やその他の処理で例外が起きると `FAIL <error message>` を出して失敗状態にし、最後に終了コード1で終わります。例外経路では `zz-failure.png` の保存も試みます。チェックポイントが失敗扱いになった場合も、最終終了コードは1です（`apps/host/scripts/agent-flow.mjs:21,148-156`）。

## 根拠

- `apps/host/scripts/agent-flow.mjs:1-10` — Chrome で実アプリを操作するスクリプトの目的と前提。
- `apps/host/scripts/agent-flow.mjs:51-55` — 指定文をチャット入力欄から送信する helper。
- `apps/host/scripts/agent-flow.mjs:124-141` — `TWO_CHATS` の条件、`PROMPT_B` の fallback、`EXPECT_B` による応答確認。
- `apps/host/scripts/agent-flow.mjs:148-156` — 失敗ログ、スクリーンショット、終了コード。
- `apps/host/server/agent/README.md:114-118` — `agent-flow.mjs` が実アプリを操作してスクリーンショットを撮る旨。
