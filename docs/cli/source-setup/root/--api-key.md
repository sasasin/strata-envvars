# `setup.py --api-key`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat` / `UPDATE.bat` 等の wrapper（root scope） |
| オプション | `--api-key` |
| 別名 | なし |
| 値 | `KEY` 文字列。複数キーはカンマ区切りで指定可能 |

## 役割

セットアップで作る、または既存モデルを起動する run config に API キーを設定します。server はそのキーを使って推論 API へのリクエストを認証します。ネットワークインターフェースを広く公開する場合にキーを設定するよう、setup の parser は案内しています。`--api-key` 自体は listen host を変更しません。

## 使い方

```sh
# 新しいモデルの setup にキーを設定
./setup.sh --model IQ3_S --api-key 'local-demo-key'

# 既に setup 済みのモデルを起動し、キーを保存
./setup.sh --api-key 'local-demo-key'

# 複数のクライアント用キーを設定
./setup.sh --host 0.0.0.0 --api-key 'client-a-key,client-b-key'
```

実際の起動時には、クライアントが設定したいずれかのキーを送ります。例のキーは説明用であり、実運用では推測されにくい値を使ってください。

## 値と既定値

- 値は必須の文字列で、parser に `type`、`choices`、長さなどの追加制約はありません。値を省略すると argparse が usage を表示して失敗します（`terminal/setup.py:11503`）。
- 複数の `--api-key` を繰り返した場合の setup 側の指定値は、argparse の通常の `store` 動作により最後の値です。複数キーを指定する書式は一つの値のカンマ区切りです（`terminal/setup.py:11503-11504`）。
- setup の設定組み立てでは値が truthy の場合に `api_key` として保存します（`terminal/strata_control/setup_config.py:531-534`）。新規 setup で空文字を渡した場合はこの代入を通らず、空キーを明示的に検証する処理もありません。
- `none`（大文字小文字を問わず前後空白を除いて一致）は server 側で「キーなしを明示した」値として扱われ、キー認証を無効にします。parser の help に記載されていない server 共通の特別値です（`terminal/serve/server_parts/http_api.py:222-225`、`terminal/serve/server.py:9331-9336`）。

## 実行時の動作

setup がモデル用 run config を作るとき、値が空でなければ `api_key` フィールドへ格納します（`terminal/strata_control/setup_config.py:531-534`）。既存モデルの通常起動では、指定された値を `start(..., keep=...)` に渡し、保存値と異なるとき run config を更新してから server を起動します（`terminal/setup.py:11761-11775`、`terminal/setup.py:8566-8602`）。setup の再実行で既存 config を書き直す際は、旧 config を読み込み、setup が管理するキーは新しい設定値で構成します（`terminal/setup.py:7540-7545`、`terminal/setup.py:7715-7735`）。

起動時の server はコマンドラインの `--api-key` があれば config の値より優先し、なければ config の `api_key` を読みます。setup は server を config 付きで起動します（`terminal/setup.py:8601-8602`、`terminal/serve/server.py:9331-9339`）。キー文字列はカンマで分割され、各要素の前後空白と空要素が除かれます。HTTP リクエストは `Authorization: Bearer …` または `x-api-key` ヘッダーで照合されます（`terminal/serve/server_parts/http_api.py:211-219`、`terminal/serve/server.py:7283-7294`）。

## 適用条件と副作用

- 指定したキーはモデルごとの `strata-<model>.json` run config に保存されます。config は JSON として一時ファイルへ書き、置換して更新されます。キーはそのファイルに平文で含まれます（`terminal/setup.py:7531-7537`）。
- 既存モデルを通常起動する経路で空文字を渡すと、`keep` から `None` だけが除かれるため空文字が保存されます（`terminal/setup.py:8577`、`terminal/setup.py:8590-8595`）。server は空 config 値を認証なしとして起動し、config に `api_key` が存在する場合は未設定の警告を stderr に出します（`terminal/serve/server.py:9331-9339`、`terminal/serve/server.py:9595-9597`）。空文字をキー解除手段として使う場合の動作は、新規 setup の場合と異なります。
- キーが有効なとき、キーのない、または一致しない API リクエストは HTTP 401 になります（`terminal/serve/server.py:7283-7294`）。ネットワーク listen がキー設定を必須にするわけではありません。
- 通常の Apple Silicon setup は `terminal/setup.py` から `engine/metal/setup_mac.py` へ引数ごと委譲されます（`terminal/setup.py:11434-11437`）。その CLI は索引上 `source-setup/mac` の別 scope で、parser は `engine/metal/setup_mac.py:383` にあります。この文書の root scope と区別してください。

## 出力とエラー

- `--api-key` の値を指定しない場合、argparse の引数解析エラーになります（parser 定義 `terminal/setup.py:11444`、オプション登録 `terminal/setup.py:11503`）。
- setup parser 自身には API キー値の形式検証がありません。空白だけの文字列など、server が空キーと判定する値は server 起動時の検証対象です。server は `[strata] an API key was given but it is empty: set a key, or leave it out` を stderr に出して終了コード 2 で戻ります（`terminal/serve/server_parts/http_api.py:238-252`、`terminal/serve/server.py:9335-9339`）。
- 正しく設定されたキーの内容は setup の「保存した」通知には出ず、`api key` とだけ表示されます（`terminal/setup.py:8590-8595`）。一方、run config ファイルには値が保存されます。

## 根拠

- `terminal/setup.py:11444-11504` — root parser と `--api-key` の値・help。型や choices の追加検証なし。
- `terminal/strata_control/setup_config.py:531-534` — setup が truthy な値を config の `api_key` に保存。
- `terminal/setup.py:7531-7537`、`terminal/setup.py:7715-7735` — run config の JSON 書き込みと既存設定の引き継ぎ。
- `terminal/setup.py:8566-8602`、`terminal/setup.py:11758-11775` — 起動時の明示値保存と server 起動。
- `terminal/serve/server_parts/http_api.py:211-252`、`terminal/serve/server.py:9331-9339` — カンマ区切りキーの正規化、`none` の扱い、起動時検証。
- `terminal/serve/server.py:7283-7294` — API キー認証と不一致時の 401。
- `terminal/setup.py:11434-11437`、`engine/metal/setup_mac.py:375-384` — Apple Silicon の委譲先と別 parser scope。
