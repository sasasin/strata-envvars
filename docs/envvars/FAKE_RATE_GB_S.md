# `FAKE_RATE_GB_S`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`apps/desktop/scripts/ui-flows.mjs` の headless UI フロー用 fake installer において、ダウンロード進捗の模擬速度（GB/s）を指定します。Strata の通常の engine、サーバー、CLI の設定ではなく、このスクリプトが一時生成する Python fake installer 専用です。同ファイルの説明も、fake installer / fake engine を使い実際のダウンロードや engine 実行をしない headless UI flow としています（`apps/desktop/scripts/ui-flows.mjs:3-14,51-56`）。

## 値と判定

fake installer の起動時に Python の `float()` で一度変換します（`apps/desktop/scripts/ui-flows.mjs:51-56`）。

| 状態 | 値 | 結果 |
|---|---|---|
| 未設定 | `0.5` | 既定の模擬速度は 0.5 GB/s |
| 設定あり | Python `float()` が受理する文字列表現 | その浮動小数点値を速度として使用 |
| 空文字・変換できない文字列 | 既定値には戻らない | `float()` が `ValueError` を送出し、fake installer は初期化中に失敗 |

範囲検査や clamp はありません。したがって負数も `float()` 変換後に受理されます。正数以外の値の進捗表示は本番動作ではなく、この fixture の式に従います。`nan` / `inf` 等も `float()` が認識する表現なら変換されますが、特別な処理や妥当性検証はありません。

## 有効になる条件

- `apps/desktop/scripts/ui-flows.mjs` を実行し、`download` flow を含む scenario を実行する必要があります。`--only` を指定した場合は `download` を含めます（既定の flow 一覧は `apps/desktop/scripts/ui-flows.mjs:33`、download scenario は同:190-198）。
- scenario が fake installer のコードを `control/tools/strata_mcp.py` に書き込み（同:43-48,104）、ホストに渡す環境を組み立てます（同:126-153）。`process.env` を基礎に scenario の `env` を後から展開するため、同名の scenario 固有値があればそれが優先します（同:133）。
- Strata の通常起動、通常のモデルダウンロード、engine の環境変数としては読み取られません。この名前の完全一致参照はこの fixture 内の1箇所です。

## 実行時の詳細

Python fake installer は生成コードの初期化時に値を読み、`RATE` に保持します。`FAKE_RATE_GB_S` 自体を後から再読込しません。fake install job が開始されると開始時刻を state file に記録し、進捗問い合わせごとに `min(TOTAL, RATE * 経過秒)` を `done_gb` として計算します。ここで `TOTAL` は fixture に固定された `83.6` GB です。残量と percent も同じ問い合わせ時に算出されます（`apps/desktop/scripts/ui-flows.mjs:63-72,80-89`）。正値なら経過時間に応じて進捗が進み、上限は `TOTAL` です。既定値 `0.5` はこの模擬計算にのみ適用されます。

fake installer の Python プロセスは UI ホストから起動され、親プロセスの環境を基にした環境を受け取ります。パッケージ済み経路でも `controlEnvironment()` は元環境を複製して一部の Python 関連変数等だけを削除するため、この名前は残ります（`apps/host/server/native-control.mjs:102-110`, `apps/host/server/control-runtime.mjs:88-103,107-111`）。空文字や不正値による例外は子プロセスの stderr に流れ、ホストは stderr を control log に記録します。子プロセスが終了した場合、保留中の RPC は `Strata control stopped. Python 3.10 or newer is required.` で reject されます（`apps/host/server/native-control.mjs:99,106-110`）。このエラー文は終了理由を必ず正確に示すものではなく、実際の Python 例外内容は stderr 側に記録される経路です。

## 根拠

- 候補名の読み取り、既定値、変換: `apps/desktop/scripts/ui-flows.mjs:51-56`
- fake progress の計算と返却値: `apps/desktop/scripts/ui-flows.mjs:63-72`
- fake installer の生成と host 用環境の構成: `apps/desktop/scripts/ui-flows.mjs:43-48,91-104,126-153`
- Control 起動環境の継承と子プロセスの stderr / 終了処理: `apps/host/server/control-runtime.mjs:88-111`, `apps/host/server/native-control.mjs:99,102-110`
