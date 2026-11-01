# `PROMPT_AFTER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`PROMPT_AFTER` は、`apps/host/scripts/agent-flow.mjs` が実アプリを Chrome で操作する UI フローで、チャットを再読み込みして開き直した後に送るメッセージ本文を指定します。通常の Strata アプリやエンジンの設定ではなく、このスクリプト専用の入力です。スクリプトの説明は、実アプリを操作してチェックポイントごとに結果を出し、失敗時は非ゼロで終了するとしています（`apps/host/scripts/agent-flow.mjs:1-21`）。README もこのスクリプトを実アプリの操作とスクリーンショット取得に使うと説明しています（`apps/host/server/agent/README.md:114-118`）。

## 値と判定

スクリプトのモジュール初期化時に `process.env.PROMPT_AFTER ?? 'SCRIPT:echo still here after reopening'` で読みます。文字列の parse、trim、値域検査はありません（`apps/host/scripts/agent-flow.mjs:34`）。

| 状態 | 使われるメッセージ |
|---|---|
| 未設定 | `SCRIPT:echo still here after reopening` |
| 設定あり（空文字を含む） | 環境変数の文字列をそのまま使う。空文字も既定値には置き換えない |

ここで使う `??` は値が nullish のときだけ既定値を選びます。Node.js の環境変数値は文字列なので、空文字や `0`、`false` という文字列は設定値として残ります。CLI 引数や別の環境変数でこの値を上書きする処理はありません。`EXPECT_AFTER` が設定されている場合は送信後に返信テキストを照合しますが、送るメッセージを変えるものではありません（同 `:116`）。

## 有効になる条件

この変数が使われるのは、Node.js で `apps/host/scripts/agent-flow.mjs` を実行し、実アプリに接続してフローが再読み込み後のチャット送信段階まで到達した場合だけです。スクリプトは `STRATA_URL` が空または未設定なら `STRATA_URL is required` を stderr に出し、終了コード 2 で終了します。説明コメント上の実行条件は、Harness がインストールされ API 接続が保存されたホストです（同 `:4-6,27-28`）。

`PROMPT_AFTER` はアプリ起動時の設定、モデル選択、バックエンド選択には使われません。`MODEL` はフロー中のモデル選択に使われ、`STRATA_URL` は接続先、`EXPECT_AFTER` は任意の返信チェックに使われます（同 `:27-39,65-70,111-116`）。`package.json` にこのスクリプト専用の npm コマンド登録はなく、ソース内の実行例は `node scripts/agent-flow.mjs` です（`apps/host/package.json`、`apps/host/scripts/agent-flow.mjs:4`）。

## 実行時の詳細

値はスクリプト読み込み時にトップレベル定数へ一度格納されます。実行中に環境変数を変更しても再読み込みはされません（`apps/host/scripts/agent-flow.mjs:34`）。フローは既存チャットを開き直した後、`send(PROMPT_AFTER)` を呼びます。`send` は最初の `textarea` に本文を入力して `Send` ボタンをクリックします。その後ストリーミング終了を待ち、スクリーンショットを保存し、待機中の tool card がないことを確認します（同 `:51-55,103-116`）。この環境変数からアプリや別プロセスへ環境値を転送するコードはありません。本文を UI に入力して送信するところまでが Strata スクリプトの処理です。

スクリプトはチェックポイントを `ok` または `FAIL` として stdout に表示します。送信、待機などの例外は catch 節で `FAIL <エラーメッセージ>` を表示し、失敗スクリーンショットを試み、最終的に終了コード 1 にします。正常時は 0 です（同 `:21,41-43,149-156`）。また `EXPECT_AFTER` が設定されると、返信にその正規表現が見つかるかを追加チェックします。これは `PROMPT_AFTER` の値の有効性を検査するものではありません（同 `:116`）。

## 根拠

- `apps/host/scripts/agent-flow.mjs:12-21` — スクリプトの用途、環境一覧、失敗時の終了についての説明。
- `apps/host/scripts/agent-flow.mjs:27-39` — 環境値の読み取り、`PROMPT_AFTER` の既定値と定数化。
- `apps/host/scripts/agent-flow.mjs:51-55,103-116` — UI 入力、再読み込み後の送信、任意の返信チェック。
- `apps/host/scripts/agent-flow.mjs:149-156` — 失敗時の表示、スクリーンショット、終了コード。
- `apps/host/server/agent/README.md:114-118` — このスクリプトを実アプリ操作・スクリーンショット取得に使うという説明。
- `apps/host/package.json` — `agent-flow.mjs` 専用の npm script 登録がないこと。
