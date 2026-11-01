# `STRATA_TEST_BROWSER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata の作業ツリーは `main...origin/main` で clean。調査対象は Strata 所有コードで、外部依存の内部動作は含めない。

## 役割

この名前は通常の Strata アプリや engine の設定ではなく、Host の Node.js テスト `apps/host/tests/agent-tools-settings.test.mjs` にある実ブラウザ統合テストの opt-in です。`STRATA_TEST_BROWSER=1` としてテストプロセスを起動したときだけ、そのテストが実行対象になります。テストファイル以外にこの名前を読む参照はありません。

## 値と判定

| 環境値（テストファイル評価時） | 判定 |
|---|---|
| 未設定 | テストを skip。理由は `starts a real browser: set STRATA_TEST_BROWSER=1` |
| 空文字 | 同上 |
| 文字列が厳密に `1` | 次の Harness・ブラウザ条件を評価 |
| その他（例: `0`, `true`, `01`, ` 1`） | skip。同上 |

比較は `process.env.STRATA_TEST_BROWSER !== '1'` という文字列の完全一致です。数値変換、trim、大文字小文字変換はありません。値はテストモジュールの評価時に読み取られ、そこで `browserSkip` に保持されます。テスト中に環境変数を変えてもこの skip 判定は再計算されません。

## 有効になる条件

`STRATA_TEST_BROWSER` が厳密に `1` でも、次のいずれかに当たる場合は実ブラウザテストを skip します。

- `STRATA_HARNESS_DIR` が未設定、または指定先が有効な built Harness でない。
- 実行環境で Chrome / Edge が見つからない。
- Harness 内の Playwright MCP CLI が見つからない。

Harness 不成立時とブラウザ／CLI 不在時の skip 理由は `needs STRATA_HARNESS_DIR with the browser tool server and Chrome or Edge on this computer` です。README も Harness を必要とするテストとしてこのファイルを挙げています。

## 実行時の詳細

条件を満たしたときに限り、テストは `node:test` の skip オプションを解除し、最大 240 秒の実ブラウザテストを登録します。ローカル HTTP ページを起動し、テスト内の scripted worker と Harness bridge を使ってブラウザの gate 動作を確認します。テストは実行中だけ `STRATA_BROWSER_HEADLESS=1` を設定し、終了時に元の値へ戻します。`STRATA_TEST_BROWSER` 自体が Strata のアプリ起動、engine、サーバー、モデル動作を変更するコードは確認できません。

skip 時は Node.js テストランナー上で対象テストが skip され、理由文字列が付与されます。明示的なエラー終了や警告をこの変数の判定が発生させる実装はありません。

## 根拠

- `apps/host/tests/agent-tools-settings.test.mjs:374-379` — Harness／ブラウザ候補の取得、厳密な `'1'` 比較、skip 理由、実ブラウザテスト登録と timeout。
- `apps/host/tests/agent-tools-settings.test.mjs:380-393,403-412` — テスト実行時のローカルページ、headless 環境設定、Harness bridge、ブラウザ操作の検証。
- `apps/host/tests/agent-tools-settings.test.mjs:26-27` — `STRATA_HARNESS_DIR` と Harness 検証による既存 skip 条件。
- `apps/host/server/agent/README.md:114-117` — 該当テストと Harness 要件の説明。
