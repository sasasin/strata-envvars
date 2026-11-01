# `STRATA_ONBOARDING_SCENARIO`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

これは `apps/host/tests/fixtures/onboarding-ui-host.mjs` が提供する、スクリーンショット/UI プレビュー専用の擬似オンボーディングホストのシナリオ指定です。Strata エンジンや通常のアプリ起動時に読む設定ではありません。fixture は重み・推論・本番データへの書き込みを行わないとコメントに記されています（`apps/host/tests/fixtures/onboarding-ui-host.mjs:1`）。

## 値と判定

fixture は値を parse せず、文字列全体を `===` で比較します。判定は大文字小文字を区別します。

| 値 | fixture の動作 |
|---|---|
| unset、空文字、または以下以外の文字列 | シナリオ固有の変更なし。fixture の初期ハードウェア・カタログを使う |
| `multi-gpu` | 初期の GPU 配列に NVIDIA RTX 3090（index 1、24 GB）を追加する |
| `limited` | 全モデルを「does not fit」にし、Swift family の最初のサイズだけ「fits」に戻す。推薦理由も互換性がない旨に差し替える |
| `telemetry` | `STRATA_ONBOARDING_START=ready` の場合に限り、ready 状態の擬似インスタンスへ固定の生成メトリクスと系列データを設定する |

数値変換、範囲制限、無効値エラーはありません。未知の値はどの分岐にも一致しません（`apps/host/tests/fixtures/onboarding-ui-host.mjs:8-18,48-61`）。

## 有効になる条件

- この値を読むのは `apps/host/tests/fixtures/onboarding-ui-host.mjs` だけです。`multi-gpu` と `limited` の分岐は fixture を直接起動した場合に適用されます。
- `telemetry` のデータ設定には、別の環境変数 `STRATA_ONBOARDING_START` が `ready` であることも必要です。`make-it-yours` のみ、またはその他の値では telemetry 分岐に入りません（同ファイル:48-61）。
- `STRATA_ONBOARDING_GPUS` が truthy なら、その値を JSON として parse して GPU 配列を置き換えるため、`multi-gpu` が追加した GPU も置き換わります。不正な JSON の場合は fixture の初期化が例外になり、HTTP リクエスト内の例外は 400 応答の JSON `{error: ...}` にされます（同ファイル:9-10,64,66-68,122）。
- `apps/host/scripts/preview-ui.mjs` と `apps/host/scripts/language-shots.mjs` は fixture を子プロセスとして起動し、環境を組み立てる際にどちらも `STRATA_ONBOARDING_SCENARIO: 'telemetry'` を明示設定します。これが親プロセス側の同名値より優先され、両プレビューは telemetry シナリオを使います（`apps/host/scripts/preview-ui.mjs:13,24`; `apps/host/scripts/language-shots.mjs:30,40`）。

## 実行時の詳細

値の判定は fixture のモジュール初期化中、該当する分岐ごとに行われます。リクエストごとの再評価や、値を保存する明示的な cache はありません。`multi-gpu` は擬似 hardware 情報を変更し、`limited` は擬似 catalog の適合状態を変更します。これらは `/api/native` の応答など fixture が返す UI 用データに現れます。`telemetry` は ready にした擬似インスタンスの `phase` と `metrics` を設定し、UI に表示する診断データを作ります（`apps/host/tests/fixtures/onboarding-ui-host.mjs:8-24,48-61,80-82`）。

値ごとのログ、終了、警告はありません。通常の fixture 起動ログは待受 URL の表示です（同ファイル:123-127）。この環境変数による変更はすべてプレビュー用データに限られ、実機検出・モデル適合判定・推論・エンジン設定を変更しません。

## 根拠

- 全参照: `apps/host/scripts/language-shots.mjs:40`, `apps/host/scripts/preview-ui.mjs:24`, `apps/host/tests/fixtures/onboarding-ui-host.mjs:9,15,58`。
- fixture は `apps/host/package.json:26-27` の `preview:ui` や README にある言語別スクリーンショット手順で使う開発用 UI プレビューです（`apps/host/README.md:24`）。この名前をエンジン、サーバーの本番コード、または通常のユーザー設定として読む箇所は、調査対象 commit の全参照検索では見つかりませんでした。
