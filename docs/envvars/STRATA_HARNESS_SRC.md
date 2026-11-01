# `STRATA_HARNESS_SRC`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

デスクトップアプリ用のビルド時ステージングスクリプト `apps/desktop/scripts/stage-harness.mjs` に、構築済み DeepSeek Harness checkout の場所を渡します。このスクリプトはインストーラー用の `harness/` 成果物を作る同梱開発・ビルド用ツールです。Strata の通常起動時や Harness の実行時設定として読む箇所は見つかりませんでした。

## 値と判定

| 状態 | `--src` がない場合の値 | 結果 |
|---|---|---|
| 環境変数が未設定 | 空文字列 `''` | 必須値チェックに失敗し、説明を stderr に出して終了コード 2 |
| 空文字列 | 空文字列 | 同上 |
| 空でないパス | `resolve()` で絶対パス化 | `apps/cli/lib/bin.js` が存在すれば入力として続行。なければ同じエラーで終了コード 2 |
| `--src <path>` を指定 | CLI 引数の値 | 環境変数より優先。環境変数が未設定・空でも CLI 値で検証する |

真偽値や数値への変換、大小文字判定、範囲制限はありません。パス文字列を `resolve()` に渡し、その下に `apps/cli/lib/bin.js` が存在するかを検査します。`--src` が指定されて値が空なら必須値チェックに失敗します。`--src` の値を省略した場合は `resolve(undefined)` が先に評価されるため、必須値チェックのエラーメッセージに到達せず Node.js の例外になる可能性があります。

## 有効になる条件

- `node apps/desktop/scripts/stage-harness.mjs` を実行すること。ソース内の使用例は `--src <built Harness checkout>` を示しています。
- CLI の `--src` がない場合は `STRATA_HARNESS_SRC` に空でないパスを設定すること。
- 指定パスの直下に `apps/cli/lib/bin.js` が存在すること。スクリプトコメントは、対象を pin された commit の checkout に install/build を行ったものと説明しています。
- OS、GPU backend、モデル状態に応じた条件分岐は、この変数の読み取り・検査にはありません。

## 実行時の詳細

スクリプト起動時に `--src` を優先して値を選び、環境変数を fallback として参照します。環境からの値を保存する専用 cache はありません。選択した値は `resolve()` で絶対パスにし、必須値と Harness のエントリーファイルを検証します。失敗時の stderr は `Give --src <a built Harness checkout> (apps/cli/lib/bin.js must exist).`、終了コードは 2 です。

検証後、選んだ checkout を `pnpm deploy` の作業ディレクトリとして使い、依存パッケージやライセンスを読み込んで指定出力フォルダーへステージします（既定出力先は `apps/desktop/src-tauri/resources/harness`）。このスクリプトは出力フォルダーを削除して作り直すため、`STRATA_HARNESS_SRC` は入力 checkout を指定する値です。以後、deploy 等のコマンドが非ゼロ終了すると stderr にコマンドと終了理由を出し、終了コード 1 で終了します。ステージ後の import 検査や `--version` 起動確認にも失敗時のエラー経路があります。

`STRATA_HARNESS_COMMIT` は同じスクリプトで別途参照され、`BUNDLE.json` に記録する commit 値を指定します。未設定または空文字なら、選択された checkout で `git rev-parse HEAD` を実行して補います。この変数は Harness のソースパス選択には影響しません。

## 根拠

- `apps/desktop/scripts/stage-harness.mjs:3-14` — ビルド時ステージング用途、入力 checkout、出力の説明。
- `apps/desktop/scripts/stage-harness.mjs:24-30` — `--src` と `STRATA_HARNESS_SRC` の優先順位、空値・エントリーファイル検査、stderr と終了コード 2。
- `apps/desktop/scripts/stage-harness.mjs:38-43,148-157` — 出力フォルダーの作り直し、選択した checkout を使った deploy、ライセンス読み込み、関連する commit メタデータ。
- `apps/desktop/scripts/stage-harness.mjs:169-180` — ステージ後の import 検査、起動確認、失敗時の終了処理。

`000_envvers.md` には候補名がありますが、Strata リポジトリでの実参照は上記スクリプトの2箇所だけでした。`docs/DETAILS.md` にこの変数の説明は見つかりませんでした。
