# `METRICS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`METRICS` は Strata エンジンの設定ではなく、ホスト側の S4b E2E フロー `apps/host/scripts/agent-flow-s4b.mjs` がエンジンの `/metrics` エンドポイントをポーリングするための任意 URL です。二つの helper agent を動かすシナリオで、同時実行数のピークが 2 以上だったかを追加チェックします。通常の Strata サーバーや CLI の動作を切り替える読み取りは確認できません。

## 値と判定

このスクリプトは値を数値や真偽値として parse せず、JavaScript の truthiness で判定します。

| 環境値 | sampling の開始 | 同時実行数チェック |
|---|---|---|
| 未設定 | 開始しない | 実行しない |
| 空文字 | 開始しない | 実行しない |
| 空でない文字列 | 開始する | `peak >= 2` を確認する |

空でない値は URL としての形式検証や既定 URL への fallback なしで `fetch()` に渡されます。CLI 引数や別の設定値による上書きはありません。認証ヘッダーを付ける場合は、別環境変数 `KEY` が truthy なら `Authorization: Bearer <KEY>` を付けます。

## 有効になる条件

- `apps/host/scripts/agent-flow-s4b.mjs` を Node.js から実行し、そのシナリオが helper agent の実行段階に到達すること。
- sampling 開始時に `process.env.METRICS` が空でないこと。
- S4b フローは実際のホストアプリとモデルを使う手動 E2E フローとして説明されています。`METRICS` 自体に OS、GPU backend、build macro による分岐はありません。

`METRICS` が空なら sampling とピーク数の検査を省略し、残りのシナリオは続行します。値があってもポーリングから実行数を取得できず `peak` が 2 未満なら、同時実行数のチェックが `FAIL` となり、最終終了コードは 1 になります。

## 実行時の詳細

`startSampling()` は最初の二 helper のシナリオの直前に呼ばれます。呼び出し時に `METRICS` が truthy なら、1 秒ごとの interval を設定し、各回で現在の `process.env.METRICS` を `fetch()` します。レスポンスを JSON として読み、`live.running.length` があればその値を使い、なければ `live.slots` のうち `state` が truthy かつ `idle` でない要素数を数えます。その最大値を `peak` に記録します。`live.running` と `live.slots` の両方が使えない場合は 0 を記録します。

HTTP status や URL を別途検証する処理はありません。fetch、JSON 解析、またはデータ参照で例外が起きた回は `catch` で無視し、エラーを出力しません。interval は helper シナリオが終わった後に停止します。以後の実行時間にわたる監視ではありません。

値は static cache されず、sampling 開始時、各 fetch 時、ピーク検査時に読み直されます。そのため、開始時に空なら後で値を設定しても interval は開始せず、開始後に値を変えると次の fetch 先が変わり得ます。ピーク検査の条件もその時点の値で判定します。検査結果は `ok` または `FAIL` として stdout に出ます。失敗は `failed` フラグに反映され、スクリプト末尾で `process.exit(1)` になります。成功時は終了コード 0 です。

## 根拠

- `apps/host/scripts/agent-flow-s4b.mjs:1-14` — S4b E2E/画面撮影スクリプトであること、`METRICS` が任意の engine `/metrics` URL であること、KEY による Authorization の説明。
- `apps/host/scripts/agent-flow-s4b.mjs:46-60` — truthiness による開始判定、1 秒間隔の fetch、`KEY` の利用、JSON の読み出し、例外の無視、interval 停止。
- `apps/host/scripts/agent-flow-s4b.mjs:94-115` — helper シナリオ前の開始、終了後の停止、ピーク数チェックとログ。
- `apps/host/scripts/agent-flow-s4b.mjs:153-161` — シナリオ例外時の `FAIL` 出力と、最終終了コード。
