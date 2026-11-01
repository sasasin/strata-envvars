# `WIDTH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

同梱のホストアプリ用スクリーンショットスクリプト `apps/host/scripts/language-shots.mjs` が、Playwright のページ viewport の幅を決めるために読みます。Strata の通常のエンジン、CLI、サーバー設定が読む箇所はありません。このスクリプトはビルド済みのホストアプリを一時プロファイルと headless Chrome / Edge で開き、指定画面の PNG を作る開発・補助用途です（`apps/host/scripts/language-shots.mjs:3-9,47-59`）。

## 値と判定

| `WIDTH` | スクリプトが渡す viewport 幅 |
|---|---|
| 未設定 | `1280`。`??` の右辺を使う |
| 空文字 | `Number("")` の結果 `0` |
| 数値に変換できる文字列 | JavaScript の `Number(...)` で変換した数値 |
| 数値に変換できない文字列 | `NaN` |

コードは `Number(process.env.WIDTH ?? 1280)` をそのまま viewport の `width` に指定し、独自の整数チェック、範囲制限、fallback、エラーメッセージを設けていません（`apps/host/scripts/language-shots.mjs:49`）。したがって、正の幅でなければならない等の受理範囲や、変換後の値を Playwright がどう扱うかは Strata 側の実装からは断定しません。大文字小文字や `1` 専用の判定もありません。

## 有効になる条件

- `apps/host` の `scripts/language-shots.mjs` を Node.js で実行した場合に限ります。CLI 引数に幅の指定はなく、viewport の高さは別の `HEIGHT`（既定値 `800`）で決まります（`apps/host/scripts/language-shots.mjs:6-9,18-20,49`）。
- スクリプトは最初に `dist/index.html` の存在を確認し、Chrome / Edge が見つからず `CHROME` も指定されていない場合は終了します。これらの早期終了経路では viewport を作らず、`WIDTH` は使用されません（`apps/host/scripts/language-shots.mjs:20-22,48-49`）。
- `WIDTH` による OS / GPU backend / build macro / モデル状態の分岐はありません。Chrome 実行ファイルは `CHROME` またはコード内の OS 別候補から選ばれます（`apps/host/scripts/language-shots.mjs:21-22`）。

## 実行時の詳細

値は `browser.newPage(...)` を呼ぶ時点で一度読み取られ、同じ `page` を使う全画面の遷移、再読み込み、スクリーンショットで同じ viewport が使われます。リクエストごとの再評価やキャッシュ機構はありません。ページは `models`、`settings`、`setup`（または CLI で渡された route）を開き、それぞれ `${language}-${screen}.png` として保存します（`apps/host/scripts/language-shots.mjs:18-19,49,53-59`）。

このスクリプトは子プロセス環境を `{ ...process.env, ...scratch, ...extra }` から作るため、親の `WIDTH` はそのまま子プロセス環境にも継承されます。ただし、対象ソース内で `WIDTH` を読む箇所は上記 viewport 設定だけです（`apps/host/scripts/language-shots.mjs:26-30,49`）。WIDTH 固有のログ、警告、終了処理はありません。スクリプトの前提条件が満たされない場合のエラー出力は、ビルド不足時 `Run npm run build first.`、ブラウザ未検出時 `No Chrome or Edge found; set CHROME.` です（`apps/host/scripts/language-shots.mjs:20-22`）。

## 根拠

- 候補一覧の `WIDTH` は `docs/envvars/000_envvers.md:1706`。
- 全リポジトリの `WIDTH` 参照を確認し、環境から値を読む実装は `apps/host/scripts/language-shots.mjs:49` のみです。他のヒットは viewport の幅という語、画像サイズ形式の説明、カーネル・テスト内の `WIDTHS` などで、環境変数の読み取りではありません。
- 読み取りスクリプトとその利用例: `apps/host/scripts/language-shots.mjs:3-9,18-22,47-63`。
