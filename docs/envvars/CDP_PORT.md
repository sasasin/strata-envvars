# `CDP_PORT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`apps/host/scripts/load-pictures-e2e.mjs` が起動する Chrome の DevTools 接続ポートを指定する。同スクリプトは同じ数値を Chrome の `--remote-debugging-port` 引数と、`127.0.0.1` 上の `/json/list` 接続先に使う。Strata の通常サーバーや推論エンジンのポート設定ではなく、この E2E スクリプト内でのみ読み取られる（`apps/host/scripts/load-pictures-e2e.mjs:24,29,35`）。

## 値と判定

モジュール初期化時に `process.env.CDP_PORT ?? 9333` を JavaScript の `Number` で変換する。環境変数が未設定 (`undefined`) のときだけ既定値 `9333` となる。空文字は nullish ではないため `Number('')` により `0` になる。数値の全体的な妥当性、整数性、ポート範囲は検証せず、clamp や無効値時の fallback もない（`apps/host/scripts/load-pictures-e2e.mjs:24`）。

| 条件 | unset | 数値化される例 | 数値として変換できない例 |
|---|---|---|---|
| スクリプトが `HOST_URL` 検査を通過して実行 | `9333` | `9333`, `0`, `-1`, `1.5`, `1e3`, `0x10`, 空文字（`0`）、空白のみ（`0`） | `true`、`0anything`（`NaN`） |

数値文字列は `Number` の規則で変換されるため、前後の空白を許し、十進数以外の数値表記も受け付ける。大文字小文字の比較はしない。`Infinity` なども拒否されず、変換後の値は文字列化されて Chrome 引数と URL に埋め込まれる。`NaN` や範囲外の値でもスクリプト側の事前エラーにはならない（同 `:24,29,35`）。

## 有効になる条件

- `HOST_URL` が truthy であること。未設定または空文字なら、スクリプトは `CDP_PORT` を定義する行に到達する前に `HOST_URL is required` を stderr に出し、終了コード `2` で終了する（`apps/host/scripts/load-pictures-e2e.mjs:19-24`）。
- `apps/host/scripts/load-pictures-e2e.mjs` を Node.js で実行すること。この読み取りは同梱ホストの通常起動経路にはなく、Node の package scripts にも同 E2E スクリプトの登録はない（`apps/host/package.json:7-26`）。
- スクリプトはポート値を検証せず Chrome に渡し、その後 `127.0.0.1:<PORT>/json/list` を最大 80 回、250 ms 間隔で取得する。Chrome が指定先で DevTools 応答を返すことが、後続処理へ進む条件になる（`apps/host/scripts/load-pictures-e2e.mjs:29,33-40`）。

OS・GPU backend・build macro・サーバーモードによる分岐や、別の CLI 引数・環境変数による `CDP_PORT` の上書きはこの実装にない。`CHROME` は Chrome 実行ファイルを選ぶが、ポート値は別途この変数から決まる（同 `:21,24,29`）。

## 実行時の詳細

`HOST_URL` の検査後、モジュール初期化時に一度 `PORT` 定数へ読み込むため、同一プロセス内で後から環境値を変更しても再評価されない（`apps/host/scripts/load-pictures-e2e.mjs:19-25`）。この値を Chrome の `--remote-debugging-port=<PORT>` 引数に埋め込み、起動後はローカル固定ホスト `127.0.0.1` の `/json/list` をポーリングする。80 回失敗すると `Chrome did not start` を throw する。接続成功後は取得した WebSocket URL で DevTools に接続する（同 `:29,33-45`）。

Chrome は `spawn` で起動される。起動時の明示的な `env` 上書きは指定されていないが、`CDP_PORT` の値を子プロセス環境に個別に設定する処理もない。Strata 側で確認できる値の受け渡しはコマンドライン引数である（同 `:29`）。

## ログと測定値

ポート値自体を表示するログはない。Chrome の stdout/stderr は `stdio: 'ignore'` で破棄される（`apps/host/scripts/load-pictures-e2e.mjs:29`）。DevTools 一覧の取得に失敗した場合は最大 80 回再試行し、最終的に `Chrome did not start` を throw する。catch 節はエラーメッセージを stderr に出し、`OUT/error.txt` に stack またはエラー文字列を書いて終了コード `2` で後処理する。WebSocket 接続エラーは `DevTools socket` として同じ catch 経路に入る（同 `:33-41,84-88`）。

## 根拠

- `apps/host/scripts/load-pictures-e2e.mjs:11-12` — コメント上の用途と既定値（実装挙動は以下のコードで確認）。
- `apps/host/scripts/load-pictures-e2e.mjs:19-25` — `HOST_URL` の先行検査と `CDP_PORT` の直接読込・変換。
- `apps/host/scripts/load-pictures-e2e.mjs:29-45` — Chrome への引数渡し、DevTools 接続先、再試行と接続。
- `apps/host/scripts/load-pictures-e2e.mjs:84-88` — エラー出力・ファイル記録・終了処理。
- `apps/host/package.json:7-26` — package scripts にこの E2E スクリプトの登録がないこと。
