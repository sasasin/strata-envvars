# `HOST`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

Docker コンテナ起動時に、セットアップへサーバーの待受アドレスを渡します。これは Strata エンジンの環境変数ではなく、`docker-entrypoint.sh` が `HOST` を読み、`setup.py --setup` に `--host` として渡す経路です。イメージの Dockerfile は `HOST` をセットアップ用環境変数として列挙しています（`docker-entrypoint.sh:24,76-78`、`Dockerfile:25-28`）。

## 値と判定

シェルの `${HOST:-0.0.0.0}` 展開を使います。未設定または空文字なら `0.0.0.0`、それ以外は入力文字列をそのまま使います。前後の空白除去、アドレス形式の検証、値の列挙は entrypoint では行いません。たとえば空白だけの値も空文字ではないため、そのまま引数になります（`docker-entrypoint.sh:24`）。

## 有効になる条件

- entrypoint が新規セットアップを行う、または `REINSTALL=1` の場合に限り、`HOST` が `setup.py --setup ... --host "$HOST"` に含まれます。
- `CONFIG` が指定される場合、または既存設定を再利用する場合は、このセットアップ引数を作らないため、その起動での `HOST` は設定に反映されません。既存設定で値を変更するには再セットアップが必要です（`docker-entrypoint.sh:59-78,89-106`）。
- API キーは `HOST` と別の `API_KEY` で渡します。非 loopback のアドレスで API キーがない場合、setup は警告を表示します（`setup.py:5829-5831`）。

## 実行時の詳細

セットアップの `--host` は文字列引数で、既定値は setup CLI 自体にはありません。値が truthy なら設定 JSON の `host` に保存されます（`setup.py:4862-4864,5773-5776`）。コンテナ entrypoint のデフォルト `0.0.0.0` は truthy なので、新規セットアップでは設定に記録されます。

後続起動では entrypoint は保存済み設定を選び、`setup.py` を `--port` などで起動しますが `--host` は再指定しません。その後 `serve/server.py` は CLI の `--host`、設定 JSON の `host`、`127.0.0.1` の順で待受先を決め、HTTP サーバーをそのアドレスに bind します。不正なアドレスなどで bind に失敗すると argparse error になります（`serve/server.py:6306-6308,6348-6358,6570`）。

`0.0.0.0` は全インターフェースで待ち受ける設定です。実際に外部から到達できるかはコンテナのポート公開などにも依存します。Strata は非 loopback 待受時に LAN アドレスを案内し、API キーがない場合は警告を出します（`serve/server.py:6572-6587`）。

## 根拠

- `docker-entrypoint.sh:19-35` — 環境変数の既定値。`HOST` は unset と空文字を `0.0.0.0` に置換。
- `docker-entrypoint.sh:59-78,89-106` — 初回セットアップ時のみ `--host` へ渡し、後続起動では設定を使う。
- `setup.py:4862-4864,5773-5776,5829-5831` — CLI 引数、設定への保存、非 loopback で API キーがない場合の案内。
- `serve/server.py:6306-6308,6348-6358,6570-6587` — CLI・設定・既定値の優先順位、bind、起動時の案内と警告。
- `Dockerfile:25-28,108-117` — `HOST` をコンテナの設定環境変数として記載し、entrypoint を起動。
