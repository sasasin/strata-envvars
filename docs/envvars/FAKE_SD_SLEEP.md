# `FAKE_SD_SLEEP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

これは Strata サーバーの設定ではなく、画像生成サーバーのテストで使う fake `sd-cli` fixture の待ち時間を制御する環境変数です。通常の Strata 実行ファイルや実 `sd-cli` の動作を変える設定としては確認できません。fixture は `FAKE_SD_SLEEP` の値を秒数として `time.sleep()` に渡し、キャンセル待ちのテストで画像生成子プロセスを遅らせます（`serve/fixtures/fake_sd_cli.py:1-4,38`, `serve/test_images.py:322-338`）。

## 値と判定

fixture は環境変数の値を `os.environ.get("FAKE_SD_SLEEP") or 0` で取得し、それを Python の `float()` に渡します（`serve/fixtures/fake_sd_cli.py:38`）。

| 状態・値 | fixture の処理 |
|---|---|
| 未設定 | `0` を `float()` に渡し、待ち時間は 0 秒 |
| 空文字 | `or 0` により未設定と同じく 0 秒 |
| 数値文字列 | `float()` で浮動小数点数に変換し、その秒数を `time.sleep()` に渡す |
| 数値として不正な文字列 | `float()` が例外を送出する。fixture 側に捕捉・fallback はない |

整数専用の判定、文字列全体の独自検査、clamp はありません。負数などの `float()` 変換後の許容範囲は fixture で検査せず、`time.sleep()` に渡します。CLI 引数や他の環境変数との優先順位もありません。

## 有効になる条件

`serve/test_images.py` は `images_api.sd_cli_args` をテスト用 `fake_args` に差し替え、画像 API が起動する子プロセスを `serve/fixtures/fake_sd_cli.py` に向けます（`serve/test_images.py:23-30,234-242`）。同ファイルの `test_chat_waits_for_the_image` は `FAKE_SD_SLEEP=1.5` を一時設定して画像要求を開始し、その処理中に送った chat 要求が画像要求の完了後に返ることを検査します（`serve/test_images.py:322-338`）。

テスト用の差し替えがない通常経路では実 `sd-cli` が起動されます。サーバーの `image_env()` は、明示した別の `base` がなければサーバーの `os.environ` をコピーし、画像設定の `env` を上書き適用して子プロセスへ渡します（`serve/images.py:131-150,221-237`）。この転送だけで Strata が `FAKE_SD_SLEEP` を解釈するわけではなく、実 `sd-cli` 側のこの名前の動作も本調査の対象・根拠には含めません。

## 実行時の詳細

fixture の `main()` が呼ばれるたびに、引数記録処理の後、進捗ログを出す前に環境を読み、sleep します。値をモジュール内へ cache する処理はありません（`serve/fixtures/fake_sd_cli.py:25-40`）。サーバーは設定環境を子プロセス起動時に作るため、fixture は起動されたプロセスの環境を読みます（`serve/images.py:131-150,231-237`）。テストは同一プロセス内で `os.environ` を一時変更して画像要求を始めます（`serve/test_images.py:322-327`）。

sleep 中は fixture の標準出力にまだ進捗行が出ません。サーバーは子プロセスの出力をログファイルへ読み込み、プロセス終了後に非ゼロ終了・timeout・cancel を失敗として扱います。タイムアウト時またはキャンセル時には子プロセスを kill します（`serve/images.py:242-273`）。値が不正で fixture が例外終了した場合も非ゼロ終了として検出され、サーバー側で `image job failed: sd-cli exited with code ...` とログ末尾を出して `ImageJobFailed` にします（同:264-273）。

## 根拠

- 読み取り、変換、sleep の位置: `serve/fixtures/fake_sd_cli.py:1-4,25-40`
- fake fixture のテストへの接続: `serve/test_images.py:23-30,234-242`
- 待ち時間を設定するテスト: `serve/test_images.py:322-338`
- 子プロセス環境の複製と起動、終了・失敗処理: `serve/images.py:131-150,221-273`
