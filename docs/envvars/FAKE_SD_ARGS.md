# `FAKE_SD_ARGS`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

`FAKE_SD_ARGS` は通常の Strata 実行ファイルや画像生成サーバーの設定ではなく、画像 API のテストで `sd-cli` の代役として起動される `serve/fixtures/fake_sd_cli.py` 専用の診断用フックです。設定されていると、fixture に渡されたコマンドライン引数を JSON 配列として指定ファイルへ記録します。記録対象は `argv`（Python スクリプト名を除いた引数）です。

## 値と判定

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | 引数ファイルを書かない |
| 空文字 | `os.environ.get()` の戻り値が false 扱いとなり、書かない |
| 空でない文字列 | その文字列をファイルパスとして `open(..., "w", encoding="utf-8")` し、`argv` を JSON で書く |

文字列の parse、空白除去、相対パスの補正、値域検査はありません。相対パスは fixture の作業ディレクトリを基準に解決されます。`"w"` モードなので、同じパスの既存ファイルは上書きされます。親ディレクトリがないなど `open()` が失敗した場合の個別処理はなく、fixture の実行が例外で中断します。

## 有効になる条件

- `serve/fixtures/fake_sd_cli.py` をプロセスとして起動する経路に限られます。`serve/test_images.py` はこの fixture を `sd-cli` の stand-in として使うと説明しています。
- 画像サーバー本体 `serve/images.py` は、設定された実際の `exe` を起動する際に `image_env()` で現在の `os.environ` を複製し、設定の `env` 項目を上書きして子プロセスへ渡します。したがって、その子プロセスがこの fixture である場合は、明示的な `env` 上書きがなければ親プロセスの `FAKE_SD_ARGS` が継承されます。
- `serve/images.py` 自体は `FAKE_SD_ARGS` を参照しません。通常の `sd-cli` や Strata engine がこの変数を読む根拠は見つかりませんでした。

## 実行時の詳細

fixture の `main(argv)` は、引数を辞書化した後、他の fixture 処理や画像生成より前に `FAKE_SD_ARGS` を読みます。環境値が空でなければ指定先を UTF-8 の書き込みモードで開いて `json.dump(argv, f)` を実行します。この値はモジュール初期化時にキャッシュされず、fixture の `main()` 呼び出しごとに評価されます。環境変数の変更を実行中に再評価する動作はなく、通常は子プロセス起動時の環境が使われます。

値の設定自体による標準出力・標準エラーのログ追加はありません。ファイルを開けない場合は Python の例外が表面化し、通常の画像サーバー経路では子プロセスの非ゼロ終了として扱われ得ます。

## 根拠

- `serve/fixtures/fake_sd_cli.py:1-4` は、画像テスト用 stand-in であり `FAKE_SD_ARGS=<file>` が引数リストを JSON で書くことを説明します。
- `serve/fixtures/fake_sd_cli.py:25-37` は `main(argv)` での判定、パスの使用、書き込み内容を実装します。
- `serve/test_images.py:1-4,23-30` は fixture のテスト用途と起動コマンドを示します。
- `serve/images.py:131-150,221-239` は子プロセス環境の構築と起動を示します。

`000_envvers.md` の候補名全体を通常利用者向け設定として扱わず、対象 HEAD でこの名前の参照を検索しました。`serve/fixtures/fake_sd_cli.py` 以外に実装上の読み取りはなく、`docs/DETAILS.md` にもこの変数の製品機能としての説明は見つかりませんでした。したがって本書は fixture の動作のみを記述し、テスト用コードを製品機能の根拠にはしていません。
