# `API_KEY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。対象は Strata 所有コード。Docker 起動スクリプトで使われる変数であり、通常の engine/server プロセスがこの名前を直接読む設定ではない。

## 役割

Docker イメージの標準起動で、クライアントが送る API key を指定します。entrypoint は値を `STRATA_LAUNCH_KEY` に移し、`strata launch --api-key-env STRATA_LAUNCH_KEY` で CLI に渡します。CLI はその環境変数を読み、起動設定の `api_key` に設定します。コンテナの healthcheck は API_KEY の値を `Authorization: Bearer ...` に使います（`docker/entrypoint.sh:225-226,278-282`; `strata_cli/launch/cmd.py:131,270-276`; `docker/healthcheck.sh:4-14`）。

この `API_KEY` を直接読むのは Docker の entrypoint と healthcheck です。`serve/server.py` の通常サーバー起動で読む環境変数は別名の `STRATA_API_KEY` です（`serve/server.py:9013-9014`）。Docker entrypoint は `API_KEY` を `STRATA_API_KEY` として渡さず、launch CLI の `STRATA_LAUNCH_KEY` 経由で設定します。

## 値と判定

| `API_KEY` の状態 | entrypoint の処理 |
|---|---|
| 未設定または空文字 | 空として扱う。`API_KEY_FILE` に非空のパスがあればそのファイルへ進む。ファイルも指定されない場合は `strata launch` に key を渡さず、標準起動で key がなければ Strata が生成する。 |
| 非空 | その文字列をそのまま key として優先する。長さが16文字未満なら stderr に短い key の警告を出すが、起動を拒否したり値を変更したりはしない。 |

`API_KEY` 自体について、entrypoint は文字種、数値、空白、大文字小文字を検証せず、trim もしません。長さだけを警告判定に使います（`docker/entrypoint.sh:77-79,163-167`）。

`API_KEY_FILE` は別の入力経路です。`API_KEY` が空の場合に限り参照され、指定パスが読めなければ `API_KEY_FILE=<path> cannot be read.` を stderr に出して終了コード1で停止します。読める場合は CR と LF をすべて除去した内容を key とします。除去後も空なら key は渡されません（`docker/entrypoint.sh:163-167`）。したがって優先順位は、非空の `API_KEY`、非空の `API_KEY_FILE` 内容、既存 preset の設定または Strata の key 生成です。

CLI の `--api-key-env` 側も、指定した環境変数が未設定または空なら `The environment variable STRATA_LAUNCH_KEY is empty or not set.` の `ValueError` になります。ただし entrypoint は key が非空の場合にだけこのオプションを追加します（`strata_cli/launch/cmd.py:270-276`; `docker/entrypoint.sh:225-226`）。

## 有効になる条件

- Docker イメージを通常のサーバー起動経路で起動する場合に有効です。entrypoint は `launch` 用の引数を組み立てます（`docker/entrypoint.sh:169-170`）。Compose の NVIDIA / AMD / Intel 定義は `API_KEY` をコンテナ環境へ渡し、値が空なら空文字を設定します（`docker/compose/docker-compose.nvidia.yml:23`; `docker/compose/docker-compose.amd.yml:22`; `docker/compose/docker-compose.intel.yml:22`）。
- `docker run IMAGE strata ...` や `docker run IMAGE sh` のように別コマンドを指定した場合、entrypoint は標準起動処理を通らず、そのコマンドを `exec` します。この経路では entrypoint による `API_KEY` の読み取り・変換はありません（`docker/entrypoint.sh:53-56`）。
- key が非空なら、entrypoint は launch CLI に `--api-key-env STRATA_LAUNCH_KEY` を追加し、その子プロセスに値を設定して起動します。CLI で `--no-api-key` は追加されないため、CLI の既存 preset に key があっても与えた key が `s.api_key` に設定されます（`docker/entrypoint.sh:225-226,278-282`; `strata_cli/launch/cmd.py:270-283`）。
- API_KEY が空で `API_KEY_FILE` も使わない初回起動では、entrypoint は launch CLI に key を指定しません。起動後に `strata launch --show-key --preset "$PRESET"` の出力を `/data/state/api-key`（または `STRATA_KEY_FILE` で指定したパス）へ保存し、key が空だった場合は stderr に自動生成した旨と表示コマンドを警告します（`docker/entrypoint.sh:32,293-299`）。保存済み preset が使われる再起動では、その設定との関係も含めて launch CLI の preset 動作に従います。

## 実行時の詳細

entrypoint 起動時に `API_KEY` を shell 展開して判定します。`API_KEY` の読み取り結果は entrypoint 内の `key` 変数に保持され、その値は launch CLI の子プロセスを開始するときだけ `STRATA_LAUNCH_KEY` として渡されます。entrypoint は環境変数を後から再読込しません。Docker の healthcheck は別プロセスとして実行され、その都度 `API_KEY` を読み、空なら `STRATA_KEY_FILE`（既定 `/data/state/api-key`）の key を使います。key があれば Bearer header を付けて `http://127.0.0.1:${PORT:-8080}/v1/models` を4秒 timeout で要求し、HTTP 200 かつ `data` が非空の場合だけ成功します。例外は `not healthy: ...` を stderr に出して失敗します（`docker/healthcheck.sh:4-17`）。

entrypoint は起動後、key file を `umask 077` の下で書きます。保存に失敗するか空ファイルなら削除を試みます。標準の Dockerfile はこの healthcheck を30秒間隔、8秒 timeout、3 retry で登録しています（`docker/entrypoint.sh:293-299`; `Dockerfile:109`）。

## 根拠

候補一覧 `docs/envvars/000_envvers.md` の `API_KEY` は実読み取りを伴う候補です。全参照を調べた結果、設定値の実装は Docker entrypoint / healthcheck にあり、他の一致は Docker Compose の環境受け渡し、例・文書、テストやサンプルでした。`API_KEY` を直接読む engine/server の実装は確認できませんでした。Docker の説明も、16文字以上を推奨し、未指定時に key を作成して volume に保持する旨を記載しています（`docs/DOCKER.md:126,159-170`）。
