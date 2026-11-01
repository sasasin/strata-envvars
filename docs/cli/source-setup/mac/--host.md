# `--host`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `metal/setup_mac.py`（Apple Silicon 用。`setup.py` から委譲） |
| オプション | `--host` |
| 別名 | なし |
| 値 | 接続待受アドレスを表す文字列。parser に型・選択肢の制限はない |

## 役割

生成する Metal サーバー設定の `host` を指定し、起動時にサーバーが待ち受けるアドレスを変えます。既定の loopback では同じ Mac からの接続に限られます。ネットワーク上の他の端末から接続させる場合は、たとえば `0.0.0.0`（IPv4 全 interface）を指定します。外部端末に公開する設定では API key の利用を推奨します。

## 使い方

Apple Silicon Mac で、セットアップ設定を作成・更新するときに指定します。

```sh
./setup.sh --setup --host 127.0.0.1
```

`setup.py` は macOS で `STRATA_CONTROL_INSTALL=1` が設定されていない場合、引数を `metal/setup_mac.py` に渡します（`setup.py:82, 9068-9069`、`setup.py:7703-7707`）。

## 値と既定値

- `argparse` の値を一つ取ります。`type`、`choices`、明示的な validation は指定されていません（`metal/setup_mac.py:327-336`）。空文字列は parser で受理されますが、後段の `if a.host:` が偽になるため設定値として書き込まれません（同:551-552）。
- 新しい設定では `--host` を省略したとき `host` キーを追加せず、サーバー側の既定値 `127.0.0.1` が使われます（`metal/setup_mac.py:239-243, 551-552`; `serve/server.py:9127`）。
- 同じオプションを複数回指定した場合の個別処理はありません。値は `argparse` の通常の単一値引数として扱われます。

## 実行時の動作

`--host` に空でない値を渡すと、セットアップが生成する設定 JSON の `host` にその値を保存します。サーバー起動時に `serve/server.py` は明示引数、設定 JSON の値、`127.0.0.1` の順でアドレスを選びます。Mac セットアップの起動ラッパーは設定 JSON を渡し、`--host` を別途渡さないため、このオプションの保存値が適用されます（`metal/setup_mac.py:551-552, 559-570, 302-323`; `serve/server.py:9127`）。

注意点として、Metal 設定がすでにあり、`--setup`、`--model`、`--check`、`--no-start`、`--update`、`--build` のいずれも指定しない通常の再起動経路では、`--host` は再設定されません。この分岐は既存設定をそのまま `start()` に渡して終了します（`metal/setup_mac.py:369-371`）。既存設定に反映するには再設定経路を使います。

設定ファイルは `strata-<model>.json` です。`write_config()` は一時ファイルを書いてから既存ファイルに置き換えるため、再設定時は同名の設定ファイルが更新されます（`metal/setup_mac.py:559-560`; `setup.py:6490-6495`）。

## 適用条件と副作用

- 対象は `setup.py` が委譲する macOS の Metal セットアップ経路です。`STRATA_CONTROL_INSTALL=1` の Control 経路はこの委譲条件の対象外です（`setup.py:82, 9068-9069`）。
- セットアップ parser は host 値の形式や到達範囲を検査しません。実際に待受ソケットを作る段階で OS の bind が失敗すると、server parser の usage error となり起動を中断します（`serve/server.py:9144-9147`）。
- 指定値はサーバーのネットワーク待受範囲を変えます。loopback 以外で起動した場合、サーバーは他端末向け URL を表示し、API key が設定されていなければ警告を表示します。API key はこの経路では必須ではありません（`serve/server.py:9143-9147, 9486-9505`）。API key の指定方法は [`--api-key`](--api-key.md) を参照してください。
- `--port` と組み合わせると、そのポートで指定 host に bind します。設定方法は [`--port`](--port.md) を参照してください。

## 出力とエラー

セットアップ完了時の API URL 表示は host 指定にかかわらず `127.0.0.1` を示す固定文字列です（`metal/setup_mac.py:564-570`）。実際の起動後は `serve/server.py` が待受アドレスとポートを `ready:` 行に表示し、loopback 以外では他端末向け URL も出します（`serve/server.py:9490-9505`）。

無効なアドレスや使用中のアドレス・ポートなど bind 時の `OSError` は `ap.error()` に渡され、usage とエラーで起動が止まります（`serve/server.py:9144-9147`）。`argparse` のエラー終了コードや OS ごとのアドレス解釈は、この checkout 上で実行確認していません。

## 根拠と調査範囲

- parser と設定への代入: `metal/setup_mac.py:327-336, 551-552`
- 既存設定での再起動分岐、設定生成と起動: `metal/setup_mac.py:302-323, 369-371, 542-570`
- 設定ファイルの置換: `setup.py:6490-6495`
- `setup.py` から Mac parser への委譲: `setup.py:82, 7703-7707, 9068-9069`
- 待受値の既定、bind、起動後表示: `serve/server.py:9127, 9143-9147, 9486-9505`

同一 revision のソースを調査しました。CLI help の実行、ビルド、サーバー起動は行っていません。アドレスごとの OS 固有の bind 挙動や、実ネットワークからの到達性は未検証です。
