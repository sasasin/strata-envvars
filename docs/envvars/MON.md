# `MON`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の Strata 作業ツリーは `main...origin/main` で、未コミット変更の表示はありませんでした。

## 役割

`MON` は Strata の通常のエンジン・サーバー設定ではなく、`apps/host/scripts/chat-growth.mjs` というチャット画面のメモリ・DOM 計測スクリプト内で、計測の最後に Monitor 画面を開いて追加計測するかを選びます。`MON` が有効なら `Monitor` のテキストをクリックし、25 秒待って追加の heap/DOM 等の計測値を出力します。無効ならこの追加区間を丸ごと飛ばします（`apps/host/scripts/chat-growth.mjs:1,23-29,55`）。

## 値と判定

スクリプトのモジュール初期化時に `process.env.MON !== '0'` と比較します。文字列変換や数値 parse はせず、文字列として厳密に `0` である場合だけ false になります（`apps/host/scripts/chat-growth.mjs:7`）。

| `MON` の値 | 判定 | 結果 |
|---|---|---|
| 未設定 (`undefined`) | 有効 | Monitor の追加計測を行う |
| 空文字 | 有効 | Monitor の追加計測を行う |
| `0` | 無効 | Monitor の追加計測を省略する |
| `00`, `0 `, `false`, `FALSE`, `1` などその他すべて | 有効 | Monitor の追加計測を行う |

CLI 引数による上書きや別環境変数との優先順位はありません。`TURNS` と `PICS` は同じ行で別々に読み取られますが、`MON` の判定を変更しません（同: `apps/host/scripts/chat-growth.mjs:7`）。

## 有効になる条件

これは `apps/host/scripts/chat-growth.mjs` を実行した場合に限る開発・診断用スクリプトの設定です。ファイル先頭の説明では、破棄可能な host、`chat-growth-proxy.mjs`、Chrome が必要とされています（`apps/host/scripts/chat-growth.mjs:1`）。スクリプトが先行する画面遷移や各ターンの計測を通過して Monitor 区間まで到達した場合にだけ判定結果が使われます（同: `apps/host/scripts/chat-growth.mjs:21-22,31-55`）。Strata エンジン、通常の CLI、サーバー起動時の機能を制御する読み取り箇所は確認できませんでした。

## 実行時の詳細

値は Node.js がこのモジュールを初期化するときに一度読み、`MON` 定数に保持されます。スクリプト内で後から環境値を再読込する処理はありません（`apps/host/scripts/chat-growth.mjs:7`）。

有効時は、ページ上の完全一致テキスト `Monitor` の最初の要素をクリックします。クリックの失敗は catch され、標準出力に `no monitor link` を出します。クリック成功・失敗にかかわらず、その後 25 秒待ち、`metrics('monitor 25s')` を呼んで heap、DOM node/listener 等を標準出力に記録します（`apps/host/scripts/chat-growth.mjs:23-29,55`）。無効時はクリック、待機、追加計測のいずれも行いません。クリック失敗後の待機や計測も失敗すれば、この箇所では catch されずスクリプトの失敗経路になります。

## 根拠

- 直接の環境読み取りは `apps/host/scripts/chat-growth.mjs:7` の `process.env.MON` のみです。大文字小文字を区別する全リポジトリ検索で、他の Strata 所有コードに同名の環境値読み取りは見つかりませんでした。helper に動的な名前を渡して読む経路も確認できませんでした。
- 効果と観測結果: `apps/host/scripts/chat-growth.mjs:23-29,55`。
- `bench/results/2026-10-05-community-rx-6700-xt/run_speed.sh:9,13` と `run_all.sh:9,15` にもシェル変数 `MON` がありますが、これはバックグラウンド監視プロセスの PID を保持して `kill` に使うシェル内変数であり、環境から `MON` を読み取る処理ではありません。
