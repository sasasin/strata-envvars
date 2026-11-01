# `MODEL_PATH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更は表示されなかった。

## 役割

Strata の Docker 起動用環境変数。コンテナ内に mount した既存 GGUF ファイル（1 ファイルまたは shard のあるフォルダー）の場所を `strata launch --model-path` に渡し、モデル重みの取得を避けてセットアップする。Strata の C++ エンジンや通常の CLI が `MODEL_PATH` を直接読む実装は見つからず、実際に値を読むのは `docker/entrypoint.sh` である。Compose 定義はホスト側の値をコンテナの同名環境変数へ渡す。

この設定は entrypoint の通常起動（引数なし、`run` または `serve`）に適用される。`strata ...` や `sh` など別コマンドを指定すると entrypoint はそのコマンドへ切り替わり、`MODEL_PATH` を `launch` 引数に変換しない（`docker/entrypoint.sh:53-56`）。

## 値と判定

entrypoint はシェル展開 `model_path="${MODEL_PATH:-${GGUF_DIR:-}}"` を使う。`MODEL_PATH` が未設定または空文字なら旧名 `GGUF_DIR` を使い、両方が空ならパス指定なし。非空の `MODEL_PATH` は `GGUF_DIR` より優先する。空白だけの値も非空として扱われ、trim や形式変換はしない（`docker/entrypoint.sh:176`）。

| 値・状態 | Strata の処理 |
|---|---|
| `MODEL_PATH` 未設定または空、`GGUF_DIR` も未設定または空 | `--model-path` を付けない。保存済み preset があればその設定を使い、なければモデル推奨など通常の `launch` 動作になる。旧 `/data/models` 内に GGUF がある場合は後述の guard が働く。 |
| 非空のパスが存在しない | `MODEL_PATH=... is not in the container... Nothing was downloaded.` を stderr に出して exit code 2。 |
| 存在するフォルダーに直下の `*.gguf` がない | `find` で深さ 2 までの最初の `*.gguf` を探す。見つかれば shard のある下位フォルダーを示して exit 2、見つからなければ「holds no .gguf files」として exit 2。 |
| 存在するファイルまたは直下に `*.gguf` があるフォルダー | `--model-path <値>` を `strata launch` に渡す。ファイルの拡張子や GGUF 内容の完全な妥当性は entrypoint のこの検査では検証しない。 |

glob の `*.gguf` と `find -name '*.gguf'` は大文字小文字を無視しない。パス値の数値変換や範囲制限はない。後続の `launch` では、パスが存在するか、フォルダー内に `.gguf` があるかを再確認し、既知モデルとの照合やセットアップ時のファイル検査へ進む。モデル未指定ならファイルからモデルを特定し、`MODEL` が指定されている場合はそのモデル名が優先され、パス内のファイルと異なる可能性は通知される（`strata_cli/launch/cmd.py:214-223,786-789`; `strata_cli/launch/runner.py:1352-1401`; `strata_control/models.py:591-612`）。

## 有効になる条件

- Docker entrypoint が `launch --no-tui` を実行する通常起動であること。Compose の NVIDIA/AMD/Intel 定義は `MODEL_PATH: ${MODEL_PATH:-}` として値をコンテナへ渡す。GPU backend による `MODEL_PATH` 自体の違いは見つからない（`docker/compose/docker-compose.nvidia.yml:16-27`; AMD/Intel 定義も同様）。
- パスはホスト側のパスではなく、コンテナ内から見えるパスである。通常は bind mount と組み合わせる。
- `MODEL` を同時指定するとそのモデルを使い、`FAMILY` はモデルファミリーの選択に使われる。`MODEL_PATH` がある場合でも `MODEL` は削除されず、preset より CLI 引数が優先される。`MODEL_PATH` があるが `MODEL` がなければ、preset の model/family を消して、own-files 判定がファイルから選ぶ（entrypoint `:190-192`; `strata_cli/launch/cmd.py:205-225`）。
- 非空の `MODEL_PATH` と `GGUF_DIR` の両方がある場合は `MODEL_PATH` が勝つ。`MODEL_PATH` が空の場合は `GGUF_DIR` が後方互換の別名として使われる（`docker/entrypoint.sh:176`; `docs/DOCKER.md:270-274`）。
- 保存済み `PRESET` は起動時に選ばれる。非空の環境値は `--model-path` として渡るため preset の `model_path` を上書きするが、環境値が空で引数自体がない場合、preset 内の値は残り得る（entrypoint `:173-192,242-249`; `strata_cli/launch/cmd.py:205-223`）。

## 実行時の詳細

`MODEL_PATH` は entrypoint 実行時に毎回シェル展開され、キャッシュされない。非空値は存在検査後 `--model-path` として子プロセスの `strata launch` に渡る。CLI は引数を `Path(...).expanduser()` した文字列で設定へ取り込み、own-files の事前確認を行う。runner はそのパスを setup.py の `--gguf-dir` に渡し、フォルダーならそのまま、単一ファイルなら親フォルダーを指定する（`docker/entrypoint.sh:176-192,273-284`; `strata_cli/launch/cmd.py:214-223,783-789`; `strata_cli/launch/runner.py:926-929,1119-1144`）。

モデルパスが setup に渡ると、Strata は当該モデル重みのダウンロードを行わず、ファイルを検査して既存ファイルとして使う（`setup.py:8940-8965,9973-10005`）。ただし `MODEL_PATH` は補助ファイル全般を無効化する設定ではない。選択内容により、vision encoder や draft layer など不足している付属ファイルは別途取得される（例: `setup.py:8967-8978,10007-10016`; `strata_cli/launch/runner.py:1943-1957`）。read-only mount は重みの読み取りには使えるが、作成済み pack や設定などは `--data-dir /data/Strata-data` 側へ置かれる。

`MODEL_PATH` が空の場合も、entrypoint は旧レイアウト `/data/models`（または `STRATA_LEGACY_MODELS` で指定した場所）を検索する。深さ 3 までに `.gguf` があれば、`ALLOW_DOWNLOAD=1` のとき警告して続行し、それ以外では「Nothing was downloaded.」を含む説明を stderr に出して exit 2 する。これは `MODEL_PATH` がない旧配置データによる意図しない再ダウンロードを防ぐ経路であり、`MODEL_PATH` の不正パス検査を回避するものではない（`docker/entrypoint.sh:42-50,189`）。

パス検査での拒否は entrypoint の stderr と exit 2 で観測できる。後続 launch が非ゼロ終了した場合は entrypoint が phase を `failed` にし、`strata launch stopped with code ...` を stderr に出してコンテナを終了する（`docker/entrypoint.sh:288-290`）。

## 根拠

- 候補名のコード全体検索では、`MODEL_PATH` の値を読む本番箇所は `docker/entrypoint.sh:176`。同ファイル `:179-192` が存在・フォルダー内容の判定、CLI 引数への転送、`:42-50,189` が legacy guard を実装する。Compose は `docker/compose/docker-compose.nvidia.yml:16-27` などでコンテナへ値を渡す。
- CLI の `--model-path` 定義、preset とのマージ、own-files の確認は `strata_cli/launch/cmd.py:83-90,205-225,783-789`。CLI 自身が `MODEL_PATH` 環境変数を読むのではなく、Docker entrypoint が CLI 引数へ変換する。
- runner から setup.py への引き渡しと setup 時のローカル重み利用は `strata_cli/launch/runner.py:926-929,1119-1144`; `setup.py:8940-8965,9973-10005`。
- Docker 利用方法と旧 `GGUF_DIR` 名の説明は `docs/DOCKER.md:113-118,143-156,270-282`。記載内容は entrypoint の検査・転送と整合する。
