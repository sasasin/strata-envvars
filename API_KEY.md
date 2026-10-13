# `API_KEY`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数は対象外。

## 役割

Docker コンテナの初回セットアップまたは再セットアップで、API 認証キーを `setup.py --api-key` に渡すための変数です。`docker-entrypoint.sh` が読みます。推論エンジンや `serve/server.py` が `API_KEY` という名前を直接読むわけではありません。セットアップでキーが設定ファイルに保存され、サーバーはその設定を使います。

## 値と判定

| `API_KEY` の状態 | entrypoint と setup の処理 |
|---|---|
| 未設定または空文字 | entrypoint 内で空文字になる。セットアップ時には `--api-key ""` を渡すが、setup.py は空文字を設定ファイルへ書かない。 |
| 空白だけ | 引数としてそのまま渡り、setup.py は truthy な値として `api_key` に保存する。サーバーはキーを trim した結果が空なら起動を拒否する。 |
| その他の値 | 引数としてそのまま渡る。シェルでの単語分割や glob 展開は起きない。setup.py は値が truthy なら設定ファイルの `api_key` に保存する。 |

サーバー側の `api_key` 文字列はカンマ区切りで複数キーとして扱われ、各キーの前後の空白を除去します。値がカンマや空白だけで有効なキーを含まない場合、`api_key_of()` が `ValueError` を返し、サーバーは stderr に `[strata] an API key was given but it is empty: set a key, or leave --api-key / STRATA_API_KEY / "api_key" out` と出して終了コード 2 を返します。

## 有効になる条件

- `docker-entrypoint.sh` は、選択中のモデル設定がまだない場合、または `REINSTALL=1` の場合に限って setup.py を呼び、`API_KEY` を `--api-key` として渡します。
- 既存モデル設定があり `REINSTALL` が `1` でない通常起動では、この変数を setup.py に渡しません。コンテナ起動時に `API_KEY` を変更しても、既存設定のキーは更新されません。設定変更には `REINSTALL=1` が必要です。
- setup.py はセットアップ設定を書き直す際、`api_key` を setup が管理するキーとして扱います。空値の場合は新しい設定にキーを記録しません。
- `CONFIG` で別の設定ファイルを選ぶ場合も、entrypoint の `API_KEY` 自体をサーバーへ渡す実装はありません。キーは実際にセットアップした設定ファイルと、起動時にサーバーが読む設定に依存します。

## 実行時の詳細

entrypoint は `API_KEY="${API_KEY:-}"` として未設定・空文字を同じ空文字にし、セットアップコマンドの `--api-key "$API_KEY"` に渡します。setup.py は `if a.api_key:` の条件でのみ `cfg["api_key"]` を設定し、`write_setup_config()` が設定ファイルに保存します。セットアップ後のコンテナ起動では `setup.py` が設定を読み、`serve/server.py --engine strata --config <設定ファイル>` を起動します。server.py は parser が `STRATA_API_KEY` を `--api-key` の既定値にするため、環境にその別名が非空で設定されていれば設定ファイルより優先します。`STRATA_API_KEY` が設定されていて空文字だけの場合は、起動時に明示的な空キーとして終了コード 2 で拒否されます。どちらもなければ設定ファイルの `api_key` が認証キーになります。

キーが設定されていない状態でサーバーが非 loopback アドレスで待ち受ける場合、server.py は標準出力に `WARNING: no API key - anyone on your network can use this model. Add "api_key": "..." to the config (clients send it as their API key; the web page asks for it)` を出します。Dockerfile と `docs/INSTALL.md` も、ネットワークに公開する前に `-e API_KEY=<secret>` を設定するよう案内しています。なお、server.py が直接参照する環境変数は別名の `STRATA_API_KEY` であり、`API_KEY` とは読み取り経路が異なります。

## 根拠

- `Dockerfile:25-35`: Docker セットアップ用の環境変数として `API_KEY` を列挙し、公開前に設定するよう案内。
- `docker-entrypoint.sh:19-35,46-48,70-87,96-106`: 既定値、セットアップ条件、`--api-key` への引き渡し、後続起動時の引数。
- `setup.py:4862-4865,5773-5776,3951-3975`: CLI 引数の型、truthy 判定、設定ファイルへの保存と再セットアップ時の処理。
- `setup.py:4341-4342,4747-4750`: 起動時に設定ファイルを server.py へ渡す経路。
- `serve/server.py:5983-6008,6321-6323,6464-6477,6570-6586`: 設定キーの解析、空キーのエラー、キーなしでネットワーク待受する場合の警告。
- `docs/INSTALL.md:103-111,126-128`: Docker での設定変数、`REINSTALL=1` と保存済み設定の説明。
