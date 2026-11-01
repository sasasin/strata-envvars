# `STRATA_ONBOARDING_PREVIEW`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/tests/fixtures/onboarding-ui-host.mjs` を使った UI プレビューで、模擬 install/tune 操作を自動で次の段階へ進める開発用フラグです。値が有効な場合、fixture はダウンロード中・準備中・モデル準備完了などの状態をタイマーで切り替えます。Strata の通常のアプリ本体や推論エンジンの動作を制御する読み取り箇所は見つかりませんでした。

## 値と判定

| 値 | fixture の動作 |
|---|---|
| 未設定 | 自動進行しない |
| 空文字 | 自動進行しない |
| 文字列 `1` | 自動進行する |
| その他の文字列（例: `0`, `true`, `01`） | 自動進行しない |

比較は `process.env.STRATA_ONBOARDING_PREVIEW === '1'` で、文字列全体との完全一致です。数値変換や trim、大文字小文字変換はありません。fixture のモジュール読み込み時に `automatic` 定数へ一度だけ保存されます。

## 有効になる条件

この変数を読むのは `apps/host/tests/fixtures/onboarding-ui-host.mjs` だけです。読み取り結果が使われるのは、fixture の `/api/native/operations` が `install` または `tune` を受け付けた経路です。通常のアプリやエンジンからこの fixture を起動しない限り、変数を設定しても Strata の通常実行には影響しません。

同梱の UI 起動スクリプト `apps/host/scripts/preview-ui.mjs` と `apps/host/scripts/language-shots.mjs` は、fixture 起動時の子プロセス環境へ `STRATA_ONBOARDING_PREVIEW: '1'` を明示して渡します。どちらも `{...process.env, ...extra}` の順に環境を組み立てるため、親プロセス側で未設定・空・別の値を指定しても、これらの起動経路では `1` に上書きされます。fixture を直接起動する場合は、呼び出し側の環境値がそのまま判定されます。

## 実行時の詳細

fixture は install 操作を受けると、まずダウンロード状態を作ります。`automatic` が true のときは 4 秒後にダウンロード表示を更新し、8 秒後に準備中へ、12 秒後に prepared へ進めます。tune 操作では 4 秒後に進行中の要約を更新し、8 秒後に ready へ進めます。タイマー発火時には、その operation がまだ running であることも確認します。これらはスクリーンショットや UI 確認向けの fixture 内状態の変更であり、実際のモデルのダウンロード、ロード、推論ではありません。

値を読む箇所は `apps/host/tests/fixtures/onboarding-ui-host.mjs:30`、値による処理と模擬段階の切り替えは `apps/host/tests/fixtures/onboarding-ui-host.mjs:33-46,89-96` にあります。子プロセスへ `1` を渡す箇所は `apps/host/scripts/preview-ui.mjs:13,23-25` と `apps/host/scripts/language-shots.mjs:30,40` です。fixture がプレビュー用であることは `apps/host/tests/fixtures/onboarding-ui-host.mjs:1` と `apps/host/scripts/preview-ui.mjs:2` の説明に記されています。

## 根拠

- `apps/host/tests/fixtures/onboarding-ui-host.mjs:1` — スクリーンショット用の fixture であり、重み・子プロセス・本番書き込みを使わない旨。
- `apps/host/tests/fixtures/onboarding-ui-host.mjs:30` — 環境変数を完全一致で読み、モジュール内定数に保存。
- `apps/host/tests/fixtures/onboarding-ui-host.mjs:33-46` — fixture 内の段階遷移。
- `apps/host/tests/fixtures/onboarding-ui-host.mjs:89-96` — install/tune API と自動進行タイマー。
- `apps/host/scripts/preview-ui.mjs:13,23-25` — UI プレビュー起動時に子プロセス環境へ `1` を設定。
- `apps/host/scripts/language-shots.mjs:30,40` — 言語別スクリーンショット起動時に子プロセス環境へ `1` を設定。
