# `API_KEY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Docker イメージの起動スクリプトで、コンテナ内の `strata launch` に渡す API キーを指定する変数。`tools/docker/entrypoint.sh` が値を選び、非空なら `STRATA_LAUNCH_KEY` と `--api-key-env STRATA_LAUNCH_KEY` を使って `strata launch --no-tui --access lan` に渡す（`tools/docker/entrypoint.sh:177-185,247,299-304`）。`strata launch` は指定された環境変数を読み、空または未設定ならエラー、値があれば起動設定の API キーに採用する（`terminal/strata_cli/launch/cmd.py:288-301`）。

この名前を直接読む実装は Docker 用シェルスクリプトにあり、通常の Strata CLI や engine が `API_KEY` を直接読む経路は見つからない。Docker Compose の NVIDIA / Intel / AMD 定義はホストの `API_KEY` をコンテナへ渡す（`tools/docker/compose/docker-compose.nvidia.yml:23-24`、`docker-compose.intel.yml:21-23`、`docker-compose.amd.yml:21-23`）。

## 値と判定

| 条件 | `API_KEY` の扱い | 結果 |
|---|---|---|
| 未設定または空文字 | `key="${API_KEY:-}"` で空として扱う | `API_KEY_FILE` が非空ならそちらを読む。そうでなければ `--api-key-env` を渡さず、`strata launch` 側の LAN 向けキー選択へ進む（`tools/docker/entrypoint.sh:178-182,247`; `terminal/strata_cli/launch/cmd.py:402-411`）。 |
| 非空 | 文字列をそのまま `key` に代入 | `API_KEY_FILE` より優先し、`STRATA_LAUNCH_KEY` として launch に渡す（`tools/docker/entrypoint.sh:178-182,247,300-303`）。 |
| 16 文字未満 | 拒否・切り詰めはしない | 起動スクリプトが `[!] API_KEY is short (<長さ> characters). Use 16 or more; 'openssl rand -hex 24' makes a good one.` を stderr に出し、その値で続行する（`tools/docker/entrypoint.sh:88-90`）。 |
| 16 文字以上 | 長さによる追加処理なし | その値で続行する。 |

`API_KEY` 自体は数値・真偽値・文字種として parse されない。たとえば `0`、`false`、空白だけの非空文字列も、シェルの非空判定では設定値である。大文字小文字の変換、前後空白の除去、値の形式検証はない。短さの判定は長さだけで、境界は 16 未満で警告、16 以上で警告なし（`tools/docker/entrypoint.sh:88-90,178-182`）。`strata launch --api-key-env` 側は参照先が空または未設定の場合だけ `ValueError` にし、その他の非空文字列を設定値にする（`terminal/strata_cli/launch/cmd.py:290-294`）。

`API_KEY` が空で `API_KEY_FILE` が非空なら、起動スクリプトはそのファイルを読める必要があり、内容からすべての CR と LF を削除する。読めなければ `[X] API_KEY_FILE=<path> cannot be read.` を stderr に出して終了コード 1 で停止する。読めたファイルが空ならキーなしとして扱う（`tools/docker/entrypoint.sh:54,178-182,247`）。

## 有効になる条件

- Docker イメージの既定起動（引数なし、または `run` / `serve`）を通ること。`entrypoint.sh` はそれ以外のコマンドを早期に `exec` するため、その経路では `API_KEY` を選択・転送しない（`tools/docker/entrypoint.sh:68-71`）。
- `API_KEY` が空なら `API_KEY_FILE` が代替入力になる。両方から非空の値を得られない場合、起動スクリプトは API キー用 CLI 引数を付けず、`strata launch` が LAN アクセス向けの保存済みキーを維持するか、新しいキーを作る（`tools/docker/entrypoint.sh:178-182,247`; `terminal/strata_cli/launch/cmd.py:402-411`）。
- `API_KEY` が非空なら `API_KEY_FILE` と保存済みプリセットのキーより優先される。`strata launch` は `--api-key-env` の値を `s.api_key` に代入し、`--no-api-key` が同時に指定された場合もキーを保持するコードだが、Docker 起動スクリプトは `--no-api-key` を付けない（`terminal/strata_cli/launch/cmd.py:288-301`; `tools/docker/entrypoint.sh:184-185,247`）。
- Compose 定義では `${API_KEY:-}` を使うため、Compose 側で値を省略した場合は空文字としてコンテナへ渡る。スクリプト上は未設定と同じ分岐になる（`tools/docker/compose/docker-compose.nvidia.yml:23-24`、`docker-compose.intel.yml:23`、`docker-compose.amd.yml:23`）。

## 実行時の詳細

`entrypoint.sh` の起動ごとに環境を参照する。`API_KEY` の値は起動時の長さ警告（`tools/docker/entrypoint.sh:88-90`）と、後段のキー選択（`tools/docker/entrypoint.sh:177-182`）で読み直される。起動後に環境変数を変更しても、すでに選択した `key` や起動中の launch には反映されない。

値を得た場合、スクリプトは `--api-key-env STRATA_LAUNCH_KEY` を引数に加え、launch 子プロセスの環境だけに `STRATA_LAUNCH_KEY="$key"` を設定して起動する（`tools/docker/entrypoint.sh:247,299-304`）。CLI はその変数を launch の設定へ読み込む（`terminal/strata_cli/launch/cmd.py:290-301`）。launch が正常終了すると、スクリプトは `strata launch --show-key --preset "$PRESET"` の出力を既定 `/data/state/api-key`（または `STRATA_KEY_FILE` の指定先）へ権限 `077` の umask で保存し、空ファイルなら削除する（`tools/docker/entrypoint.sh:46-47,315-317`）。キー未入力で launch がキーを作った場合は「No API_KEY was set...」と表示して、表示方法も案内する（`tools/docker/entrypoint.sh:318-320`）。

Docker healthcheck は実行のたびに `API_KEY`、次に読める `API_KEY_FILE`、最後に保存済みキーの順で選び、`/v1/models` へ Bearer 認証付き GET を行う。`API_KEY_FILE` が読めない場合はここでは停止せず、保存済みキーを試す。応答が HTTP 200 かつ `data` が空でないときだけ終了コード 0、それ以外や例外時は失敗終了し、例外内容を `not healthy: ...` と stderr に出す（`tools/docker/healthcheck.sh:4-18`）。これは healthcheck 用の読み取りで、サーバー起動時のキー選択とは別に行われる。

## ログと測定値

短い `API_KEY` の警告と `API_KEY_FILE` の読み取り失敗は上記のとおり stderr に出る。Docker 起動後に launch 子プロセスが非 0 で終了すると、entrypoint は `[X] strata launch stopped with code <終了コード> ...` を出してコンテナを終了する（`tools/docker/entrypoint.sh:310-312`）。キー未入力時の警告は launch が正常終了した後に出る（`tools/docker/entrypoint.sh:318-320`）。測定値は該当しない。

## 根拠

- Docker からの値選択・警告・CLI への転送・保存: `tools/docker/entrypoint.sh:46-47,68-71,88-90,177-185,247,299-320`
- launch CLI による環境変数の読み取りと LAN 用キーの維持・生成: `terminal/strata_cli/launch/cmd.py:288-301,402-411`
- healthcheck での別読み取り: `tools/docker/healthcheck.sh:4-18`
- Compose からの環境変数受け渡し: `tools/docker/compose/docker-compose.nvidia.yml:23-24`、`docker-compose.intel.yml:23`、`docker-compose.amd.yml:23`
