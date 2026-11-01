# `PICS_OUT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査日の Strata 作業ツリーは `## main...origin/main` で、表示された未コミット変更はありません。`000_envvers.md` の候補一覧にも `PICS_OUT` が含まれています。

## 役割

`apps/host/scripts/pictures-ui.mjs` が UI の画像添付を確認するために作る画像と画面キャプチャの出力ディレクトリを指定します。この値を読むのは同梱の手動 UI 診断スクリプトだけです。`apps/host/package.json` の scripts にこのスクリプトを呼び出す項目はなく、通常のアプリ起動やエンジン設定では使われません。

## 値と判定

| 環境値 | `OUT` の値・結果 |
|---|---|
| 未設定 | OS の一時ディレクトリ名に `pics-ui` を加えたパス。Windows の `\\` は `/` に置換されます。 |
| 空文字 | 空文字をそのまま採用します。`??` は空文字を既定値扱いしません。続く `mkdirSync('')` が失敗するため、スクリプトは画像生成・UI 操作に進みません。 |
| その他の設定値 | 文字列を変換・検証せず、そのまま出力先として使います。絶対/相対パス、存在しないディレクトリ等に対する独自の制限や fallback はありません。 |

## 有効になる条件

スクリプト `apps/host/scripts/pictures-ui.mjs` を Node.js で実行した場合にだけ評価されます。`apps/host/package.json` は Node.js `>=24.12.0` を指定しています。先頭コメントによると、この UI 検査には使い捨て host（`STRATA_UI_BASE`、既定 `http://127.0.0.1:18791`）と、18899 番ポートでモデル役をする `tests/helpers/scripted-worker.mjs` が必要です。これは通常の製品実行経路ではなく、UI 検査用スクリプトです。

## 実行時の詳細

モジュール評価時に `process.env.PICS_OUT ?? join(tmpdir(), 'pics-ui')` で一度値を決め、その直後に `mkdirSync(OUT, { recursive: true })` を実行します。プロセス起動後の環境変更を読み直す処理はありません。生成する `blue.png` と、UI 状態を撮影する `1-paste.png`、`2-three.png`、`3-sent.png`、`4-settings-on.png`、`5-off.png` はすべて `${OUT}/...` に書かれます。

各 UI 条件の成否は標準出力に `ok` または `FAIL` として記録され、検査を続けた後、ブラウザを閉じて失敗が一つでもあれば終了コード 1、なければ 0 で終了します。出力先の作成や PNG 書き込み、Playwright の操作などが例外で失敗した場合、後続処理には到達しません。出力ディレクトリについて独自の警告・fallback 処理はありません。

## 根拠

- `apps/host/scripts/pictures-ui.mjs:7-10` — `PICS_OUT` の唯一の読み取り、nullish fallback、出力先ディレクトリ作成。
- `apps/host/scripts/pictures-ui.mjs:18-18,41-41,60-60,69-69,79-79,98-98` — PNG と画面キャプチャの出力先。
- `apps/host/scripts/pictures-ui.mjs:1-2,20-24,99-100` — 検査の前提、結果ログ関数の利用範囲、ブラウザ終了と終了コード。
- `apps/host/package.json:7-27,47-49` — package scripts に `pictures-ui.mjs` の起動項目がないこと、および Node.js 要件。
