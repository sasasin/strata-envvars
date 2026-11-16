# `BUTTON`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`BUTTON` は、ホストの `/#/models` ページで `load-pictures-e2e.mjs` が待ち受けてクリックする `<button>` の表示文字列を指定する。このスクリプトは実 Chrome を DevTools Protocol で操作する同梱 E2E 用スクリプトであり、Strata の通常のサーバー起動やエンジン処理が読む環境変数ではない。既定では `Load model` を探す。ページ上のボタンの `textContent.trim()` が指定文字列と完全一致し、かつ有効なときに待機を終え、そのボタンをクリックする（`apps/host/scripts/load-pictures-e2e.mjs:3-12,19-25,48-60`）。

リポジトリ内の `BUTTON` 全参照を確認したところ、環境値を読む箇所はこのスクリプトだけだった。他の一致箇所は GTK の修飾キー定数、UI テスト内の文字列定数で、環境変数の読み取りではない（`apps/desktop/src-tauri/src/main.rs:1188`、`apps/desktop/scripts/ui-flows.mjs:212`、`apps/host/tests/chat-save-notice.test.mjs:23,31,40,89`）。

## 値と判定

スクリプトのモジュール初期化時に `process.env.BUTTON ?? 'Load model'` を一度評価する。Node.js の環境値が未設定（`undefined`）の場合だけ既定値になり、空文字列はそのまま有効な検索文字列として使われる。数値・真偽値への変換、空白除去、大文字小文字変換、妥当性検査はない（`apps/host/scripts/load-pictures-e2e.mjs:25`）。

| 条件 | unset | 有効になる値（例） | 一致しない値・動作例 |
|---|---|---|---|
| スクリプトがページ操作まで到達 | `Load model` を検索 | `Load model`。ページ上のボタンの trim 済み表示文字列との完全一致が必要 | `load model` は大文字小文字が異なるため一致しない。`Load model ` は環境値側の末尾空白が残るため、ページ表示側が trim 後 `Load model` なら一致しない。空文字も検索対象で、空の表示文字列のボタンがなければ一致しない |

検索は有効なボタンが見つかるまで行われ、見つからない場合は値が不正だとは判定せず、タイムアウト経路に進む（`apps/host/scripts/load-pictures-e2e.mjs:52-55`）。

## 有効になる条件

- `HOST_URL` が truthy で設定されている必要がある。未設定または空文字ならページ操作前に `HOST_URL is required` を stderr に出して終了コード 2 となる（`apps/host/scripts/load-pictures-e2e.mjs:19-20`）。
- `CHROME` で指定した実行ファイル（未設定時 `/usr/bin/google-chrome`）が起動し、DevTools ページに接続でき、`HOST_URL` の `/#/models` ページが操作可能である必要がある（`apps/host/scripts/load-pictures-e2e.mjs:21,29-45,48-50`）。
- 対象ボタンの trim 済み表示文字列が `BUTTON` と完全一致し、ボタンが disabled でない必要がある。別の名前を指定した場合、ボタンが現れる／有効になるまでの待機条件もクリック対象もその名前に変わる（`apps/host/scripts/load-pictures-e2e.mjs:51-59`）。
- CLI 引数や別の環境変数による `BUTTON` の上書きは実装されていない。ほかの設定との優先順位もない（`apps/host/scripts/load-pictures-e2e.mjs:19-25`）。
- OS、GPU backend、build macro による `BUTTON` の分岐はない。この読み取りは Node.js スクリプト内に限られ、C++/CUDA/HIP/SYCL エンジンの機能を直接切り替えない（`apps/host/scripts/load-pictures-e2e.mjs:14-25`）。

## 実行時の詳細

スクリプト起動時に環境値を定数へ読み込むため、実行中に環境を変更してもこのプロセス内の値は更新されない。読み込んだ値は JSON 文字列化されて、ページ内でボタンを探す JavaScript 式に埋め込まれる。最初に同名ボタンが存在して有効になることをポーリングし、待機後に同じ条件で検索したボタンの `.click()` を呼ぶ（`apps/host/scripts/load-pictures-e2e.mjs:25,48-60`）。

待機は最大 240 回、各未成立後に 500 ms 待つ。成立しなければ `never-ready.png` を保存して `The "<BUTTON>" button never came up` を投げ、catch 節でメッセージを stderr に出し、スタックを `OUT/error.txt` に保存し、Chrome と一時プロファイルの後始末後に終了コード 2 で終了する（`apps/host/scripts/load-pictures-e2e.mjs:45-46,52-55,84-88,28-31`）。ページ評価またはクリックで例外になった場合も catch 節の同じエラー経路を通る。

クリック後は `LIMIT_S`（既定 900 秒）の間ジョブ状態をポーリングし、結果を記録する。ジョブ状態が `done` なら終了コード 0、それ以外または制限時間までに完了しなければ終了コード 1 となる。これらはクリック後の共通処理であり、`BUTTON` 自体が変えるのは検索・クリック対象の文字列である（`apps/host/scripts/load-pictures-e2e.mjs:23,60-83`）。

## ログと測定値

`BUTTON` によるボタンが待機中に見つからない／有効にならない場合、`never-ready.png` と `OUT/error.txt` が作られ、stderr には `The "<BUTTON>" button never came up` が出る。成功時の標準出力には終了状態や経過秒数などの JSON が出るが、`BUTTON` の値そのものを成功ログへ出す処理はない（`apps/host/scripts/load-pictures-e2e.mjs:55,81-87`）。この変数に関する性能測定値は該当しない。

## 根拠

- `apps/host/scripts/load-pictures-e2e.mjs:3-12` — スクリプトの E2E 用途とコメント上の実行例・環境変数一覧。
- `apps/host/scripts/load-pictures-e2e.mjs:19-25` — `BUTTON` の直接読み取り、既定値、他の起動時環境値。
- `apps/host/scripts/load-pictures-e2e.mjs:48-60` — ページ遷移、完全一致による有効待ち、同じボタンのクリック。
- `apps/host/scripts/load-pictures-e2e.mjs:84-88` — エラー表示、`error.txt`、終了コード 2。
- `apps/host/scripts/load-pictures-e2e.mjs:60-83` — クリック後のポーリング、出力、終了コード 0/1。
