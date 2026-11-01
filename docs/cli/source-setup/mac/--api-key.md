# `--api-key`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | macOS の `setup.py` / `setup.sh`（`metal/setup_mac.py` に委譲されたとき） |
| オプション | `--api-key` |
| 別名 | なし |
| 値 | 任意の1引数（文字列）。macOS setup parser に選択肢・形式・長さの制約はない |

## 役割

Apple Silicon の Metal setup が生成するモデル別 run config に API キーを保存し、そこから起動する Strata server に渡します。server はキーを必要とする API リクエストを認証します。`--host` で他の端末から接続できるようにする場合にも利用できます。

## 使い方

初回 setup、または既存モデルを設定し直すときに指定します。

```sh
./setup.sh --setup --api-key 'REPLACE_WITH_A_LONG_RANDOM_KEY'
```

`setup.py` は macOS で `STRATA_CONTROL_INSTALL=1` が設定されていない場合、引数を `metal/setup_mac.py` に渡します（`setup.py:9068-9069`）。`setup.sh` は `setup.py` に引数を転送します（`setup.sh:6-12`）。この文書はその Mac parser の option scope です。

## 値と既定値

- 値は必須で、`argparse` が1つの文字列として受け取ります。省略時は `None` です。短縮名・既定キーはありません（`metal/setup_mac.py:327-337`）。
- Mac setup 自体は値の内容を検証しません。値が truthy のとき `cfg["api_key"]` に格納します。空文字列を指定した場合は格納されず、他に `STRATA_API_KEY` がなければ認証なしで起動します（`metal/setup_mac.py:551-560`, `serve/server.py:9134-9139`）。
- server は文字列のカンマ区切りを複数キーとして解釈し、各キー前後の空白と空要素を取り除きます。したがってカンマをキーの一部として使う値はこの文字列形式では表現できません（`serve/server.py:8358-8366`）。
- 空白だけ、またはカンマだけの値は Mac setup では受理・保存されますが、server 起動時に「API key was given but it is empty」として拒否されます。`none`（大文字小文字を問わず、前後空白を除いた値）はキーではなく、明示的に認証なしで serve する指定です（`serve/server.py:8369-8372`, `8385-8399`）。

## 実行時の動作

setup は `--api-key` の値を `strata-<model-tag>.json` の `api_key` として保存し、`setup.py` 共通の writer が JSON を一時ファイルに書いてから置換します（`metal/setup_mac.py:542-560`, `setup.py:6490-6495`）。このためキーは run config に平文で保存されます。run script は config のパスで `serve/server.py` を起動し、Mac の start 処理は `--api-key` 自体を server に再転送しません（`metal/setup_mac.py:302-323`）。

server 起動時に `STRATA_API_KEY` が設定されていれば server parser の既定値になり、空でない環境変数は config の値より優先します（`serve/server.py:9013-9015`, `9127-9142`）。空文字または空白だけの `STRATA_API_KEY` は明示的な空キーとして扱われ、起動を終了コード 2 で拒否します（`serve/server.py:9128-9142`）。

server は正規化したキーを認証サービスに設定します。リクエストは `Authorization: Bearer <key>` または `x-api-key: <key>` で認証でき、不一致・欠落時は HTTP 401 を返します（`serve/server.py:7006-7014`, `9366`）。

## 適用条件と副作用

- 有効なのは `setup.py` が macOS 委譲経路を選ぶ場合です。`STRATA_CONTROL_INSTALL=1` の Control 経路では `setup.py` 自身の別 parser が使われます（`setup.py:9068-9070`）。
- 既存の Mac config が見つかり、`--setup`、`--model`、`--check`、`--no-start`、`--update`、`--build` のいずれも指定されていない場合、Mac setup は既存 config から直ちに起動します。この早期経路は `--api-key` を条件に含めず、値も config に適用しません。既存モデルのキーを変更するには、例のように `--setup` を付けて config を再生成してください（`metal/setup_mac.py:369-371`, `551-560`）。
- 再 setup では新しい config を生成して書き換え、Mac setup は旧 config の `api_key` を引き継ぎません。`--api-key` を再指定しなければ、新 config にキー項目は入りません（`metal/setup_mac.py:542-560`, `setup.py:6490-6495`）。
- `--api-key none` は認証を無効にします。server はネットワークに公開された host でキーなしの場合、到達可能な利用者がモデルを使える旨を警告します（`serve/server.py:8369-8372`, `9495-9505`）。

## 出力とエラー

- `--api-key` の値を省略すると、macOS parser の `argparse` が usage とエラーを表示し、終了します。値の空白・カンマのみなどの検査は setup 時ではなく server 起動時に行われます（`metal/setup_mac.py:327-358`, `serve/server.py:9128-9142`）。
- 不正な空相当キー、または telemetry 用キーとの重複は server が標準エラーに理由を出し、終了コード 2 を返します（`serve/server.py:9138-9142`, `9366-9374`）。
- キーが設定されている server への認証失敗は HTTP 401 と `missing or wrong API key` を返します（`serve/server.py:7006-7014`）。

## 根拠

- parser と未認識引数の扱い: `metal/setup_mac.py:327-358`
- 既存 config からの早期起動: `metal/setup_mac.py:369-371`
- config への保存と server 起動: `metal/setup_mac.py:302-323`, `542-570`; `setup.py:6490-6495`
- キーの分割・`none`・空値検査: `serve/server.py:8358-8399`, `9127-9142`
- HTTP 認証と失敗応答: `serve/server.py:7006-7014`, `9366-9374`
