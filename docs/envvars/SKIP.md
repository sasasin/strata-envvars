# `SKIP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの作業ツリーは `## main...origin/main` で変更なし。環境変数候補一覧 `docs/envvars/000_envvers.md:558` に掲載されています。

## 役割

`SKIP` は `apps/host/scripts/agent2-flow.mjs` と `apps/host/scripts/agent2-tools-flow.mjs` という、Host アプリをブラウザー経由で操作するシナリオスクリプトの一部ステップを省略します。Strata サーバー、CLI、推論エンジンの動作を設定する変数ではありません。各スクリプトは独立して同じ変数を読みます。

## 値と判定

両スクリプトとも起動時に `process.env.SKIP ?? ''` をカンマで `split` し、空要素を `filter(Boolean)` で除いた `Set` を作ります。メンバーの照合は大文字小文字を区別する完全一致です。空白の除去や名前の正規化、値の追加検証はありません（`apps/host/scripts/agent2-flow.mjs:25`, `apps/host/scripts/agent2-tools-flow.mjs:23`）。

| 値 | 結果 |
|---|---|
| 未設定または空文字 | 空の Set。省略ステップなし |
| `loop,goal` | `loop` と `goal` を省略 |
| `loop, goal` | `loop` のみ一致。2つ目は先頭空白付きの別文字列 |
| `Loop`、未知の名前 | 対応するステップは省略されない |
| `,loop,,` | 空要素は除去され、`loop` のみ一致 |

両スクリプトに共通の別名や数値変換はありません。CLI 引数や別環境変数で `SKIP` を上書きする処理もありません。

## 有効になる条件

それぞれのスクリプトを Node.js で実行した場合にだけ有効です。`agent2-flow.mjs` は `menu`、`loop`、`goal`、`timeskip` を個別に省略し、`agent2-tools-flow.mjs` は `own`、`search`、`use`、`off`、`browser` を個別に省略します（`apps/host/scripts/agent2-flow.mjs:72-84,86-115,117-137,139-170`; `apps/host/scripts/agent2-tools-flow.mjs:79-105,107-119,121-141,143-161,163-186`）。

Set に含まれないステップ名は通常どおり実行されます。各スクリプトのブラウザー起動、アプリへの初期アクセスなど `if (!SKIP.has(...))` の外にある処理は省略されません（`apps/host/scripts/agent2-flow.mjs:19-35,60-71`; `apps/host/scripts/agent2-tools-flow.mjs:18-37,74-78`）。

## 実行時の詳細

`SKIP` はモジュール評価時に一度読み取られて Set に保存されます。実行中にプロセス環境を書き換えても、この Set は再構築されません。省略対象のブロックは実行されず、そのブロック内の操作や `check` による `ok` / `FAIL` 出力もありません。残りのステップは順に実行されます。

たとえば `agent2-flow.mjs` では `menu` がスラッシュメニュー確認、`loop` が `/loop` の再実行確認、`goal` が `/goal` のファイル生成確認、`timeskip` が `/time-skip` の比較・適用・復元確認を制御します。ツール用スクリプトでは `own` が独自ツール作成、`search` が Web 検索、`use` が独自ツール利用、`off` が検索無効化、`browser` がブラウザー利用の確認を制御します（上記の各 `if` とその内部処理を参照）。

両スクリプトの `try` 節内で捕捉された例外は `ERROR` とエラーメッセージとして出力され、`failed` を立てます。終了時にはページ問題の件数を出力し、`failed` が立っていれば終了コード 1、そうでなければ 0 で終了します。ページ問題の出力だけでは `failed` は変更されません（`apps/host/scripts/agent2-flow.mjs:28-29,171-180`; `apps/host/scripts/agent2-tools-flow.mjs:26-27,187-196`）。

## 根拠

- `docs/envvars/000_envvers.md:558` — `SKIP` は候補一覧に掲載。
- `apps/host/scripts/agent2-flow.mjs:12-13,19-26` — 用途の記載、環境からの読み取りと Set 化。
- `apps/host/scripts/agent2-flow.mjs:72-84,86-115,117-137,139-170` — 4つのステップ判定と実行内容。
- `apps/host/scripts/agent2-flow.mjs:28-29,171-180` — 判定出力、例外経路、終了コード。
- `apps/host/scripts/agent2-tools-flow.mjs:18-24` — 環境からの読み取りと Set 化。
- `apps/host/scripts/agent2-tools-flow.mjs:79-105,107-119,121-141,143-161,163-186` — 5つのステップ判定と実行内容。
- `apps/host/scripts/agent2-tools-flow.mjs:26-27,187-196` — 判定出力、例外経路、終了コード。
