# `FAKE_SD_ARGS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

これは通常の Strata エンジン用設定ではなく、画像 API のテスト用 stand-in `terminal/serve/fixtures/fake_sd_cli.py` に渡された argv を JSON ファイルへ記録する診断用フックである。値が空でなければ、stand-in が受け取った引数配列を指定先に書く。Strata の本番 `serve/images.py` 自身はこの名前を読まず、画像 API の動作や生成画像を変える設定ではない（`terminal/serve/fixtures/fake_sd_cli.py:1-5,45-57`; `terminal/serve/test_images.py:1-2,23-30,489-501`）。

## 値と判定

stand-in は `os.environ.get("FAKE_SD_ARGS")` の真偽値を調べ、真なら同じ変数を添字参照して `open(..., "w", encoding="utf-8")` に渡す。文字列の parse、trim、拡張子・パス検証はしない。未設定と空文字は記録を行わず、空でない任意の文字列は出力先のパスとして扱う。`0`、`false`、空白だけの文字列も Python では空でないため有効であり、値の大文字小文字による違いもない。数値境界はない（`terminal/serve/fixtures/fake_sd_cli.py:55-57`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| テスト用 stand-in `fake_sd_cli.py` の起動 | 記録しない | 空文字以外の文字列。例: `/tmp/argv.json`、`0`、`false`、` ` | 空文字。例: `""` |

この環境変数を Strata の CLI 引数や設定ファイルから解釈するコードはない。画像サービスの設定 `images.env` が同名キーを持つ場合、`image_env()` は継承した環境の後でその設定を文字列化して上書きし、stand-in の子プロセスへ渡す（`terminal/serve/images.py:177-196,467-469`）。

## 有効になる条件

- `terminal/serve/fixtures/fake_sd_cli.py` が画像 CLI として実際に起動されること。通常の `sd-cli` バイナリには、この Strata ソース内で `FAKE_SD_ARGS` を読む処理は確認できない（`terminal/serve/test_images.py:23-40`; `terminal/serve/fixtures/fake_sd_cli.py:1-5,55-57`）。
- 環境値が空文字でないこと。設定先に書き込み可能な親ディレクトリがあることはコードで検査されず、パスが無効・書き込み不能ならファイル操作の例外となる（`terminal/serve/fixtures/fake_sd_cli.py:55-57`）。
- テスト `test_the_prompt_reaches_sd_cli_in_a_file_and_not_in_its_arguments` は一時ディレクトリ内の `argv.json` を値に設定して HTTP リクエストを送り、記録した配列に prompt 本文がなく `--prompt-file` があることを確認する（`terminal/serve/test_images.py:489-501`）。

## 実行時の詳細

サービスの `ImageJob.run()` は `image_env()` で作った環境を `lifeline.popen()` に渡す。通常の継承環境はコピーされ、設定の `images.env` があれば後から同名値を上書きする（`terminal/serve/images.py:177-196,441-469`）。テストでは `mock.patch.dict` によってリクエスト処理中だけ値を設定し、同じ stand-in を subprocess として起動する（`terminal/serve/test_images.py:28-30,489-495`）。

読み取りは stand-in の起動ごとに、argv を受け取った直後に行われる。値が真なら指定パスを書き込みモードで開き、引数配列を JSON として書く。既存ファイルは上書きされる。環境変数の値は cache されず、この処理の後に stand-in は待機・ログ出力・画像ファイル生成へ進む（`terminal/serve/fixtures/fake_sd_cli.py:45-58,63-79`）。

書き込み失敗時の fallback はなく、例外は stand-in の起動失敗として非ゼロ終了につながる。サービス側は子プロセスの stdout と stderr を結合してログへ取り込み、非ゼロ終了なら `image job failed: ...` とログ末尾を出し、`ImageJobFailed` を送出する（`terminal/serve/fixtures/fake_sd_cli.py:55-57`; `terminal/serve/images.py:460-471,474-480,496-505`）。この環境変数自身についての成功・失敗ログはない。

## 根拠

- `terminal/serve/fixtures/fake_sd_cli.py:1-5,45-57` — stand-in 用であること、環境値の判定と argv JSON の書き込み。
- `terminal/serve/test_images.py:23-40,489-501` — テストで stand-in を選び、テスト内だけ環境値を設定して argv の内容を検証。
- `terminal/serve/images.py:177-196,441-471,474-505` — 子プロセス環境の継承・設定上書き、起動、失敗のログと例外。
