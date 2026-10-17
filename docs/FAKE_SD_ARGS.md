# `FAKE_SD_ARGS`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`serve/fixtures/fake_sd_cli.py` が受け取ったコマンドライン引数を JSON 配列としてファイルへ保存するための変数です。この Python スクリプトは `serve/test_images.py` が実際の `sd-cli` の代わりに起動するテスト用 fixture です。Strata エンジンや通常の `sd-cli` の設定を制御する環境変数ではありません。

## 値と判定

fixture は `os.environ.get("FAKE_SD_ARGS")` の結果を Python の真偽値で判定します。

| 状態 | 動作 |
|---|---|
| 未設定 | ファイルを書かない |
| 空文字 | ファイルを書かない |
| 空でない文字列 | その文字列を出力ファイルのパスとして開き、引数配列を JSON で書く |

値は数値や真偽値として parse されず、前後の空白も除去されません。書き込みは UTF-8 テキストモードで行われ、同名ファイルがあれば上書きします。保存する配列は `main(sys.argv[1:])` の `argv`、つまり Python 実行ファイル名と fixture のパスを除いた引数です。指定パスを開けない、または書き込めない場合の例外処理はなく、通常のログ出力や fake CLI の処理より前にスクリプトが失敗します。

## 有効になる条件

`serve/test_images.py` の画像生成テストでは、`images_api.sd_cli_args` が返すコマンドを fixture を使う形に置き換えます。`serve/images.py` は `subprocess.Popen` に `image_env(self.cfg)` を渡し、`image_env` は既定でサーバーの `os.environ` をコピーします。その後、画像生成設定の `env` に同じキーがあればその値で上書きします。したがってテストで fixture を起動する場合、親環境の `FAKE_SD_ARGS` は子プロセスへ渡り、画像生成設定の `env.FAKE_SD_ARGS` があればそちらが優先します。

この変数を読むのは fixture のみです。通常の Strata 実行経路への効果は確認できません。また、テスト専用コードは製品機能の実装根拠から除くという調査範囲に従い、この文書の説明はテスト fixture の挙動に限定します。

## 実行時の詳細

画像生成リクエストごとに `serve/images.py` が `sd-cli` 相当の子プロセスを起動します。テストではその子プロセスが `fake_sd_cli.py` です。fixture は起動時に環境を読み、`FAKE_SD_ARGS` が空でない場合は引数配列を JSON として一度書き出してから、テスト用の待機・ログ・PNG 生成へ進みます。fixture 側で値をキャッシュする処理はなく、別々に起動されたプロセスでは起動時の環境が使われます。

通常の保存成功時には、この環境変数専用の stdout/stderr ログはありません。書き込み失敗時は未捕捉例外になります。出力ファイルの内容は引数配列の JSON です。

## 根拠

- `serve/fixtures/fake_sd_cli.py:1-4,35-37,56-57` — fixture であること、条件判定、JSON 書き込み、引数の渡し方。
- `serve/test_images.py:23-30,233-234` — テストで fake CLI を `sd-cli` の代わりにする箇所。
- `serve/images.py:131-149,220-237` — 子プロセス環境の組み立て、設定 `env` による上書き、fixture を含むコマンドの起動。
