# `STRATA_LAUNCH_KEY`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Docker イメージの entrypoint が、起動時に指定された API キーを `strata launch` に渡すために使う環境変数名です。Strata 本体がこの名前を固定して読むのではなく、entrypoint が `--api-key-env STRATA_LAUNCH_KEY` を付け、launch CLI がその引数で指定された名前を `os.environ.get()` に渡します。したがって、通常のエンジン設定や `strata launch` の暗黙の設定値ではなく、Docker 起動経路専用の受け渡し名です。

## 値と判定

| 状況 | 処理 |
|---|---|
| Docker の `API_KEY` が空でなく設定されている | その値を `STRATA_LAUNCH_KEY` に設定して launch プロセスを起動する。値そのものは引数には含めない。 |
| `API_KEY` が空で、`API_KEY_FILE` が指定されている | entrypoint はファイルから CR/LF を除いた内容をキーとして読む。読み取れない場合は entrypoint がエラー終了する。空の内容ならキーなしとして扱う。 |
| `API_KEY` も `API_KEY_FILE` も有効な値を提供しない | `STRATA_LAUNCH_KEY` は設定されず、entrypoint は `--api-key-env` を渡さない。共有アクセス用のキーは launch 側で生成される。 |
| `--api-key-env NAME` の `NAME` が未設定または空文字 | CLI は `ValueError`（`The environment variable NAME is empty or not set.`）を送出する。 |
| キーに空白や任意の文字が含まれる | CLI は値を trim・parse せず、その文字列を API キーとして設定する。 |

entrypoint が `API_KEY` を優先し、空のときに `API_KEY_FILE` を読む順序は `docker/entrypoint.sh` の処理です。launch CLI では既存プリセットを読み込んだ後、`--api-key`、続いて `--api-key-env` の値でキーを上書きします。`--no-api-key` も同時に指定された場合、キーは維持され、警告 notice が追加されます。

## 有効になる条件

- `docker/entrypoint.sh` の通常起動経路で、API キー値が空でない場合に限り `--api-key-env STRATA_LAUNCH_KEY` が追加されます。
- `--api-key-env` は汎用の `strata launch` オプションです。CLI に別の環境変数名を指定すれば、その名前を動的に読み取ります。`STRATA_LAUNCH_KEY` という固定名自体は Docker entrypoint で使われます。
- entrypoint は指定されたキーで `access lan` の launch を起動します。キーが指定されなければ launch 側で共有用キーを生成し、保存します。
- `--plan` でも引数から設定を組み立てる段階で環境変数を読むため、`--api-key-env` を直接指定して変数が空ならエラーになります。

## 実行時の詳細

entrypoint は `API_KEY` が空の場合に限り、`API_KEY_FILE` の内容を読み取って改行を除きます。得られたキーが空でなければ `--api-key-env STRATA_LAUNCH_KEY` を引数に加え、launch を起動する子プロセスの環境に `STRATA_LAUNCH_KEY="$key"` を設定します。Python の短い中継プロセスは環境を引き継いで `strata` を `execv` するため、launch CLI はその環境変数を参照できます。

CLI は `os.environ.get(a.api_key_env)` で値を取得し、偽値（未設定または空文字）なら `ValueError` にします。成功した値は launch settings の `api_key` となり、runner が実行設定の `api_key` に書き込みます。`--save-preset` が指定される Docker 経路では、その settings がプリセットに保存されます。Docker entrypoint はサーバー起動後、キーを `launch --show-key` で取得して保護された `/data` 上のキー・ファイルにも保存し、`docker exec ... strata monitor` や health check で使えるようにします。

## 根拠

- `docker/entrypoint.sh:150-155` — `API_KEY` 優先、空の場合の `API_KEY_FILE` 読み込み、CR/LF 除去。
- `docker/entrypoint.sh:157-159,213,258-268` — launch 引数の構成、キーがある場合の `--api-key-env STRATA_LAUNCH_KEY` 追加、子プロセス環境への設定と起動。
- `strata_cli/launch/cmd.py:118` — `--api-key-env` 引数の定義。
- `strata_cli/launch/cmd.py:190-194,235-251` — プリセットを基にした設定の読み込み、CLI 指定キーの適用順、空値エラーと `--no-api-key` との関係。
- `strata_cli/launch/runner.py:288-295` — API キーをサーバー設定の `api_key` に反映する処理。
- `docker/entrypoint.sh:280-285` — 起動後のキー保存と、キーが自動生成された場合の案内。
