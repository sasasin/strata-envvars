# `source-setup mac --api-key`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | Apple Silicon Mac 向け setup（`setup.py` から `metal/setup_mac.py` へ委譲） |
| オプション | `--api-key` |
| 別名 | なし |
| 値 | 任意の文字列 `KEY`。setup 側に型・形式・空白の validation はない |

## 役割

Apple Silicon 向けセットアップで生成する実行設定に API キーを保存し、その設定から起動する Strata server の API 認証に使います。キーは設定 JSON に平文で書かれます。既に Metal 設定があり、引数が通常起動扱いとなる場合は既存設定から直接起動するため、この指定は保存・適用されません。

## 使い方

Mac でリポジトリのルートから、セットアップを再実行して設定だけ作る例です。値は実際に使うキーへ置き換えます。

```sh
./setup.sh --setup --model Q2_0 --api-key example-key-change-me --no-start
```

## 値と既定値

- `argparse` は `--api-key` に値を1つ受け取ります。既定値は `None` で、短縮別名や setup 側の形式検査はありません（`engine/metal/setup_mac.py:372-403`）。
- 値が空文字列なら `if a.api_key` を通らず、設定にキーを書きません。空白だけの文字列は truthy なので設定に保存されますが、server のキー検証で拒否されます（`engine/metal/setup_mac.py:602-605`、`terminal/serve/server_parts/http_api.py:238-252`）。文字列のカンマ区切りは複数の有効キーとして扱われます（`terminal/serve/server_parts/http_api.py:211-219`）。
- `none`（大文字小文字を問わず、前後空白を除いた値）は server が「キーなしを明示した」値として扱います。これは認証キー `none` を設定する動作ではありません（`terminal/serve/server_parts/http_api.py:222-225`）。

## 実行時の動作

- `setup.py` は Mac 向け処理を `metal/setup_mac.py` に引数ごと渡します。Metal setup の再設定経路では `a.api_key` が truthy のとき `cfg["api_key"]` に入り、モデル別の `strata-<model>.json` へ書かれます（`terminal/setup.py:9205-9210`、`engine/metal/setup_mac.py:593-612`）。設定ファイルは一時ファイルに JSON を書いてから置き換えます（`terminal/setup.py:7447-7453`）。
- 通常起動の早期分岐は、Metal 設定があり、`--setup` / `--model` / `--check` / `--no-start` / `--update` / `--build` のいずれも指定されていない場合に既存設定をそのまま起動します。この経路では `--api-key` を新設定へ反映しません（`engine/metal/setup_mac.py:416-418`）。
- セットアップで生成した起動処理は `serve/server.py --config <設定ファイル>` を実行します（`engine/metal/setup_mac.py:311-332`）。server は CLI の `--api-key` または `STRATA_API_KEY` を設定中の `api_key` より優先し、いずれも空扱いなら設定値を参照します（`terminal/serve/server.py:8686-8688,8810-8823`）。キーが設定されると server の `/v1/*` API は Bearer または `x-api-key` による認証を要求します（`terminal/serve/server.py:4052`）。

## 適用条件と副作用

- この option は Apple Silicon 向けの委譲先 parser に属します。トップレベル setup が通常の起動分岐に入る条件では、上記のとおり指定値が既存設定に反映されないことがあります。設定変更には `--setup` など再設定経路を選びます（`terminal/setup.py:9205-9210`、`engine/metal/setup_mac.py:416-418`）。
- API キーは設定 JSON に保存されます。設定ファイルは全体を書き換える方式で、専用のファイル権限設定・暗号化処理はこの書き込み経路にはありません（`terminal/setup.py:7447-7453`）。
- 空白だけのキーは server 起動前検証に失敗します。server は `[strata] an API key was given but is empty: set a key, or leave it out` を stderr に出し、終了コード 2 を返します（`terminal/serve/server.py:8810-8823`、`terminal/serve/server_parts/http_api.py:238-252`）。
- この setup parser は設定保存後に server を起動するのが既定です。`--no-start` を付けた場合は設定を書いた後に終了するため、キー値の server 側検証は起動時まで行われません（`engine/metal/setup_mac.py:610-621`）。

## 根拠

- parser と受理値: `engine/metal/setup_mac.py:372-403`
- 通常起動への早期分岐: `engine/metal/setup_mac.py:416-418`
- 設定への格納と出力ファイル: `engine/metal/setup_mac.py:593-621`
- Mac setup への引数委譲: `terminal/setup.py:9205-9210`
- 設定 JSON の書き込み: `terminal/setup.py:7447-7453`
- 起動時のキー優先順位と空値エラー: `terminal/serve/server.py:8686-8688,8810-8823`
- キー正規化と `none` の特別扱い: `terminal/serve/server_parts/http_api.py:211-252`
