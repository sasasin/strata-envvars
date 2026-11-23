# `GGML_VK_VISIBLE_DEVICES`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の画像生成サーバーは、画像設定の GPU を `sd-cli` 子プロセスへ渡す環境変数名として `GGML_VK_VISIBLE_DEVICES` を選びます。対象は `terminal/serve/images.py` の `image_env()` が作る子プロセス環境です。Strata がこの名前を指定して `os.environ` から値を読み取ったり、その値を GPU 選択の分岐に使ったりする実装ではありません。一般の環境辞書コピーで親の同名キーが子へ引き継がれる場合と、画像設定からこのキーを作る場合があります。外部の `sd-cli` やライブラリが受け取った値をどう解釈するかは、この文書の対象外です。 (`terminal/serve/images.py:177-196, 467-469`)

## 値と判定

このコードは `GGML_VK_VISIBLE_DEVICES` の値を読み取って parse しません。代わりに画像設定の `gpu` を文字列化して子プロセス環境へ代入します。`images.backend` が大文字小文字を含めて厳密に `"vulkan"` で、`images.gpu` が `None` でない場合だけ、このキーを設定します。単一値は `str(gpu)`、list / tuple は各要素を `str()` 化して前後空白を除き、空になった要素を捨ててカンマで連結します。全体の数値検証、範囲検証、空値の拒否はありません。 (`terminal/serve/images.py:185-195`)

| 条件 | このキーに対する Strata の処理 | 例 |
| --- | --- | --- |
| `images.backend == "vulkan"` かつ `images.gpu` が `None` 以外 | GPU 設定から上書き代入 | `2` → `"2"`、`[1, 0]` → `"1,0"`、`[]` → `""` |
| `images.backend` が他の値、または `images.gpu` が `None` | GPU 設定からは代入しない。親環境からコピーされた同名キーがあればその値を維持 | unset は親環境に同名キーがなければ unset、空文字はあれば空文字のまま |
| `images.env` にこのキーがある | 上記の結果を最後に `str(value)` で上書き | `""` → `""`、`2` → `"2"` |

したがって `0`、`1`、`true`、`false`、`0anything`、空白付き文字列などを Strata が有効・無効に判定する規則はありません。これらの文字列は、設定から作られた場合は変換規則に従ってそのまま（list / tuple 要素では両端空白を除いて）子環境へ渡されます。親環境から継承した値は、この関数内では値の形式を検査しません。 (`terminal/serve/images.py:180, 185-195`)

## 有効になる条件

- サーバー設定に `images` セクションがあり、起動時に `ImageGen` が作成されること。画像生成 API の `/v1/images/generations` はこの設定がない場合は 404 を返します。 (`terminal/serve/server.py:7568-7575, 9004-9012`)
- 生成するジョブで `sd-cli` を起動すること。`image_env()` はジョブごとに作る子プロセス環境に使われます。 (`terminal/serve/images.py:441-443, 463-469`)
- 設定由来でこのキーを作るには、`images.backend` が `"vulkan"` で、`images.gpu` が `None` ではないこと。設定生成 helper は `gpu` が `None` でない場合に限って `images.gpu` を保存します。`tools/image/install.py` は `--gpu` を渡しますが、`setup.py` の `setup_images()` はこの引数を渡さないため、このセットアップ経路では `images.gpu` は設定されません。 (`terminal/tools/image/qimage.py:235-252`, `terminal/tools/image/install.py:89-91`, `terminal/setup.py:5925-5927`, `terminal/serve/images.py:185-191`)
- `tools/image/install.py` の `--gpu` は画像設定の `gpu` に渡されます。一方、サーバー本体の `--gpu` はトップレベルの engine 設定を書き換えるもので、画像設定の `images.gpu` をこの箇所で変更しません。 (`terminal/tools/image/install.py:52-53, 89-91`, `terminal/serve/server.py:8806-8807`)
- `images.env` に同名キーを設定すると GPU 設定から作った値を上書きします。`images.env` が無い、または同名キーが無い場合は、`image_env()` がコピーしたサーバー環境の値が引き継がれます。 (`terminal/serve/images.py:180, 185-195`)

## 実行時の詳細

値の生成はサーバー起動時ではなく、各画像ジョブの `run()` から `image_env(self.cfg)` を呼ぶ時点です。引数 `base` を省略した本番呼び出しでは、その時点の `os.environ` を辞書コピーし、`quiet_crash_env()` を適用してから GPU 設定、最後に `images.env` を順に反映します。関数内やモジュール内にこの値の cache はありません。各ジョブの起動時点の環境辞書が子へ渡され、起動済みの子プロセスには後からの変更は反映されません。 (`terminal/serve/images.py:177-196, 467-469`)

`images.gpu` がある場合の変換は単一値なら `str()`、list / tuple なら要素ごとの `str().strip()` と空要素除去、カンマ連結です。型・数値範囲・負値を検査する処理はこの経路にありません。`images.env` の値も `str()` に変換されます。Strata の CLI 引数をこの環境変数の値として優先する処理はなく、画像設定の `images.gpu` を使う分岐です。 (`terminal/serve/images.py:185-195`)

## ログと測定値

この変数の設定値や形式に対する専用ログ、警告、拒否、終了経路はありません。サーバー起動時には画像生成の backend などを表示しますが、この環境変数の値は表示しません。子 `sd-cli` の起動に失敗した場合は `sd-cli did not start (...)` を `ImageJobFailed` にし、画像 API は `image_generation_failed` の HTTP 500 を返します。子プロセスが非ゼロ終了、画像を出さない、または timeout / cancel した場合も画像ジョブの一般的な失敗として扱われ、子ログ末尾がエラーへ含まれます。これらは変数値の検査ではありません。 (`terminal/serve/server.py:9010-9024, 7582-7588`, `terminal/serve/images.py:467-471, 482-505`)

## 根拠

- `terminal/serve/images.py:177-196` — 親環境のコピー、backend と `gpu` によるキー選択、文字列化、`images.env` による最終上書き。
- `terminal/serve/images.py:441-471` — 画像ジョブごとの子プロセス起動と環境の受け渡し。
- `terminal/serve/images.py:482-505` — timeout / cancel、終了コード、画像未出力時の一般的な失敗処理。
- `terminal/serve/server.py:7568-7588, 9004-9024` — 画像 API の有効条件、初期化、起動ログ、HTTP エラー応答。
- `terminal/tools/image/qimage.py:235-252`, `terminal/tools/image/install.py:52-53, 89-91` — 画像設定の `gpu` 保存と installer の `--gpu`。
- `terminal/serve/server.py:8806-8807` — サーバー本体の `--gpu` がトップレベル設定を更新する箇所。
