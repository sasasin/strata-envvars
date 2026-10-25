# `--api-key`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` および setup を委譲する wrapper） |
| オプション | `--api-key` |
| 別名 | なし |
| 値 | クライアント認証キーを表す文字列。parser で型・選択肢・長さの制約は定義されていない |

## 役割

モデルの実行設定に API キーを指定します。キーを設定すると、サーバーの API クライアントは認証キーを送る必要があります。`--host 0.0.0.0` などで LAN に公開する場合、setup の help は API キーの利用を推奨しています（`setup.py:8473-8475`）。

## 使い方

```sh
./setup.sh --setup --api-key 'replace-with-a-long-random-key'
```

Windows では同じ引数を `START-HERE.bat --setup --api-key ...` に渡せます。POSIX wrapper は引数を `setup.py` に渡し、Windows wrapper も同様に `%*` を渡します（`setup.sh:76`、`START-HERE.bat:48-54`）。

## 値と既定値

- `--api-key` の後には一つの文字列を渡します。値を省略すると `argparse` が usage error を出して終了します。setup parser 自身は文字列に追加の型・形式・長さ validation を行いません（`setup.py:8420`、`setup.py:8475`、`setup.py:8553`）。
- 省略時の parser 値は `None` です。既存モデルの通常起動では指定されたキーだけを保持対象として渡すため、未指定なら保存済みキーを維持します（`setup.py:8677-8691`）。一方、`--setup` で設定を作り直すと `api_key` は setup 管理項目であり carry-over 対象ではないため、未指定なら新しい設定に引き継がれません（`setup.py:6162-6167`、`setup.py:6177-6187`、`setup.py:9671-9672`）。
- カンマ区切りで複数キーを指定できます（例: `key1,key2`）。サーバーは各キーの前後の空白を除去し、空要素を除いて受理します。キー自体にカンマを含める形式は CLI ではなく、設定ファイルの `api_key` 配列で指定する必要があります（`setup.py:8475`、`serve/server.py:7638-7646`）。
- `none`（大文字小文字を区別しない）を指定すると、サーバーはこれを認証キーではなく「キーなしを明示した値」として扱います。ネットワークへ公開した場合も認証を無効にするため、通常のキーとして `none` を使うことはできません（`serve/server.py:7649-7652`）。
- 空文字（`--api-key ""` または `--api-key=`）は、setup の生成設定には書き込まれません。既存モデルの通常起動では空文字も保持対象に含まれて `api_key` を空にするため、認証を外します。`--setup` で再構成した場合も新しい設定に既存キーが引き継がれません（`setup.py:6177-6187`、`setup.py:6745-6771`、`setup.py:9671-9672`）。空白だけの値は setup parser では拒否されませんが、サーバー起動時に空キーとして扱われ、stderr にエラーを出して終了コード `2` で終了します（`serve/server.py:8290-8303`）。

## 実行時の動作

新規 setup では、`--api-key` の値をモデル設定 JSON の `api_key` に格納し、設定を書き込みます。標準の setup 経路では設定ファイルを生成・更新して起動用スクリプトを作ります。既存設定を変更する場合は `.bak` のバックアップを作成します（`setup.py:6312-6345`、`setup.py:9669-9672`、`setup.py:9729-9730`）。Mac 用 Metal setup も独自 parser で同名オプションを受理し、同じ `api_key` 設定項目へ保存します（`metal/setup_mac.py:328-336`、`metal/setup_mac.py:539-548`）。

インストール済みモデルの通常起動時に指定した場合は、起動前に既存設定 JSON の `api_key` を更新して保存し、その後 `serve/server.py` を設定ファイル付きで起動します。保存時の表示は秘密値そのものではなく `api key` とだけ示します（`setup.py:6745-6775`）。

サーバーは設定値を API 認証キーとして使います。`Authorization: Bearer ...` または `x-api-key` ヘッダーのキーが一致しなければ API リクエストに HTTP 401 を返します（`serve/server.py:3842`、`serve/server.py:6352-6360`）。キーが未設定ならこの認証判定は通過します（同: `6352-6354`）。

## 適用条件と副作用

- オプションの値は設定ファイルへ保存されるため、後続の起動でも使われます。既存設定ファイルのキーを変える副作用があります（`setup.py:6766-6771`、`setup.py:9671-9672`）。
- 既存モデルを普通に起動する経路と setup 経路で反映されます。`--update` は `update_install` に早期委譲し、モデルを起動しない更新専用経路なので、このオプションを指定しても API キーの変更は行いません（`setup.py:8617-8619`、`setup.py:6682-6709`）。
- キーなしで LAN に待ち受けると、setup の完了表示はネットワーク上の誰でも利用できる旨を示し、サーバーも警告します。`--host` の未指定時は loopback が既定ですが、host 指定自体は別オプションです（`setup.py:8473-8475`、`setup.py:9744-9747`、`serve/server.py:8624-8633`）。
- `setup.py` の共通 parser を使う Linux/Windows 経路に加えて、Mac は `metal/setup_mac.py` の parser に分岐します。SYCL 経路は共通 `setup.py` の `main()` を引数付きで再利用します（`setup.py:8418-8420`、`sycl/setup_intel.py:541-554`）。

## 出力とエラー

- 引数値を省略した場合の usage error は `argparse` によるものです。setup 側に `--api-key` 専用の validation error はありません（`setup.py:8475`、`setup.py:8553`）。
- 空白だけのキーなど、サーバー側で空と判定された値は `[strata] an API key was given but it is empty` を stderr に出し、終了コード `2` でサーバー起動を中止します（`serve/server.py:8290-8303`）。
- 認証キーがない、または一致しない API リクエストは HTTP `401` と `authentication_error` JSON を返します（`serve/server.py:6352-6360`）。
- `--host` が loopback 以外でキーがなければ、サーバーの標準出力にネットワーク利用者への警告を出します（`serve/server.py:8624-8633`）。

## 根拠

- `setup.py:8420-8420`、`setup.py:8473-8475`、`setup.py:8553-8553` — 共通 parser と `--api-key` 定義、引数 parsing。
- `setup.py:8617-8619`、`setup.py:8677-8691`、`setup.py:9669-9672`、`setup.py:9729-9730` — 更新専用経路、起動時の保持、setup 設定への書き込み。
- `setup.py:6745-6775` — 起動時の設定 JSON 更新と server 起動引数。
- `serve/server.py:7638-7679`、`serve/server.py:8290-8303` — 複数キーの分解、`none` と空キーの扱い、起動時 validation。
- `serve/server.py:6352-6360`、`serve/server.py:8624-8633` — HTTP 認証とキーなしでのネットワーク警告。
- `metal/setup_mac.py:328-336`、`metal/setup_mac.py:539-548`、`sycl/setup_intel.py:541-554` — Mac parser と SYCL の共通 parser 委譲。
