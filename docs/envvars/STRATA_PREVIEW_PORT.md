# `STRATA_PREVIEW_PORT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata 所有ソースを対象とし、外部ライブラリ・driver の環境変数動作は含めない。

## 役割

`apps/host` の UI preview コマンドが、シミュレーション用 onboarding fixture の HTTP ポートを決めるために読みます。通常の Strata host や推論サーバーのポート設定ではありません。`apps/host/package.json` では `preview:ui` が `node scripts/preview-ui.mjs` に対応し、README はこの preview が隔離されたシミュレーションデータを使い、通常の host は `npm run dev` で起動すると説明しています（`apps/host/package.json:26`, `apps/host/README.md:5-10`）。

## 値と判定

スクリプト起動時に `Number(process.env.STRATA_PREVIEW_PORT ?? 5272)` で一度変換します（`apps/host/scripts/preview-ui.mjs:10`）。

| 環境変数 | `webPort` | 結果 |
|---|---:|---|
| 未設定 | `5272` | 既定値を使う |
| 空文字 | `0` | nullish fallback は適用されず、`Number("")` の結果を使う |
| 数値として変換できる文字列 | 変換後の数値 | そのまま fixture 起動用の値にする |
| `Number()` で数値にできない文字列 | `NaN` | Strata 独自の fallback や入力検査はない |

文字列全体を数値化し、`parseInt` のような先頭部分だけの変換ではありません。コードに整数化、範囲 clamp、無効値の fallback はありません。CLI 引数や別の環境変数との優先順位も定義されていません。`STRATA_PREVIEW_HOST_PORT` は別用途で、preview host のポートを決めます（同ファイル:9-10, 16-24）。

## 有効になる条件

この値を読むのは `apps/host/scripts/preview-ui.mjs` だけです。`apps/host` で `npm run preview:ui` を実行し、ビルド済みの `dist/index.html` が存在する場合に preview の起動フローへ進みます。dist がなければ `Run npm run build before starting the UI preview.` を stderr に出して終了コード 1 で終了し、fixture は起動しません（`apps/host/scripts/preview-ui.mjs:15-16`, `apps/host/package.json:26`）。このスクリプトは preview host と fixture を子プロセスとして起動し、実モデル・重みを使わない構成です（同ファイル:2-4, 13-25; `apps/host/README.md:10`）。OS/backend/build macro/モデル状態による分岐はありません。

## 実行時の詳細

スクリプトの起動時に値を読み、preview host の health check が通った後、fixture 子プロセスへ `STRATA_ONBOARDING_PORT: String(webPort)` として渡します（`apps/host/scripts/preview-ui.mjs:10, 13, 17-24`）。fixture はその環境変数を `Number()` で読み直し、`server.listen(port, '127.0.0.1', ...)` に渡します（`apps/host/tests/fixtures/onboarding-ui-host.mjs:124-125`）。したがって待受は loopback に限られます。元の `STRATA_PREVIEW_PORT` も子環境には継承されますが、この fixture の待受が使う名前は `STRATA_ONBOARDING_PORT` です。

値の変更はスクリプトを起動し直すまで再評価されません。`webPort` は fixture の起動時に渡されるもので、リクエストごとの再読込や cache の更新経路はありません。ポート 0 を渡した場合も、スクリプトは OS が割り当てた実ポートを取得して表示し直す処理を持たず、案内 URL には `webPort` の値を使います（`apps/host/scripts/preview-ui.mjs:24-25`; fixture の listen は上記）。

数値への変換後に値を検証せず fixture の `listen` に渡します。Strata 側には無効ポートの警告、別ポートへの fallback、fixture の `error` イベント処理はありません。子プロセスが異常終了すると親スクリプトの `exit` handler が `stop(code ?? 1)` を呼び、起動済みの子プロセスを停止します（`apps/host/scripts/preview-ui.mjs:12-13`）。

## 根拠

- 候補一覧には名前があります（`docs/envvars/000_envvers.md:1328-1332`）。Strata リポジトリ全体の完全一致検索では、本番コード上の読み取りは `apps/host/scripts/preview-ui.mjs:10` のみです。
- `apps/host/package.json:26`, `apps/host/README.md:5-10`: コマンド名と preview の用途。
- `apps/host/scripts/preview-ui.mjs:9-25`: 既定値、変換、子プロセスへの転送、起動条件、表示 URL、終了処理。
- `apps/host/tests/fixtures/onboarding-ui-host.mjs:124-125`: 渡されたポートを loopback listener に使う箇所。
