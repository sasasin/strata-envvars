# `ALLOW_DOWNLOAD`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは clean。調査範囲は Strata 所有ソースと同梱 Docker entrypoint。

## 役割

Docker イメージの標準起動時に、旧イメージの配置 `/data/models`（または `STRATA_LEGACY_MODELS` で指定した場所）に `.gguf` が残り、今回の起動で使う `MODEL_PATH` が指定されていない場合の停止ガードを解除します。`ALLOW_DOWNLOAD` が有効なら、entrypoint は通常なら停止する箇所で警告を出して `strata launch` へ進みます。

これは Strata エンジンにダウンロードを指示する環境変数ではありません。entrypoint はこの値を CLI 引数に加えず、環境値によって行うのはガードの停止／続行の選択と警告だけです。実際に何を取得するかは後続の `strata launch` の処理です（`docker/entrypoint.sh:45-50, 252-290`）。

## 値と判定

シェルの `${ALLOW_DOWNLOAD:-0}` を文字列 `1` と完全一致で比較します。数値変換や真偽値 parse はありません。

| 環境値 | ガードでの扱い |
| --- | --- |
| 未設定 | `0` に置き換わり、無効 |
| 空文字 | `:-` の既定値 `0` に置き換わり、無効 |
| `1` | 有効 |
| `0`、`01`、`true`、`yes`、空白を含む値など | `1` と一致しないため無効 |

この判定で無効でも、旧配置に対象ファイルが見つからなければ停止しません。逆に有効値 `1` でも、ガード条件が成立しなければログや起動動作に影響しません（`docker/entrypoint.sh:45-50`）。

## 有効になる条件

次の条件をすべて満たすと、値が判定されます。

- コンテナが通常の `run` または `serve` 起動経路に入る。`strata ...`、`sh` など別コマンドは entrypoint の早い分岐で直接実行され、ガードを通りません（`docker/entrypoint.sh:53-56`）。
- `MODEL_PATH` または旧名 `GGUF_DIR` から解決した `model_path` が空。`MODEL_PATH` が非空なら `GGUF_DIR` より優先されます。非空のパスが存在しない、または適切な `.gguf` を含まない場合は、ガードより前に別のエラーで終了します（`docker/entrypoint.sh:176-188`）。
- `STRATA_LEGACY_MODELS` の値（未設定または空なら `/data/models`）以下、深さ 3 以内に `.gguf` ファイルが少なくとも一つある。探索では最初に見つかった一つを説明文に使います（`docker/entrypoint.sh:45-49, 189`）。

起動前の移行処理が旧配置の中身を `/data/Strata-data` へ移せた場合、通常このガードが問題にする旧配置ファイルは残りません。ディレクトリ自体が mount point の場合や移動できなかった場合は残り得ます（`docker/entrypoint.sh:85-103`）。

## 実行時の詳細

Docker の標準 entrypoint は `/opt/strata/entrypoint.sh` です。両 Dockerfile はこのスクリプトをイメージへコピーして entrypoint に設定しています（`Dockerfile:100-111`, `docker/Dockerfile:87-89, 128-134`）。スクリプトは `legacy_models_guard` を `strata launch` の引数を組み立てる前に呼び出します（`docker/entrypoint.sh:169-192`）。

ガード対象の `.gguf` がある場合、`ALLOW_DOWNLOAD=1` なら標準エラーへ `[!]` から始まる説明を一度出して続行します。値が未設定、空、または `1` 以外なら同じ説明を `[X]` 付きで標準エラーに出し、終了コード `2` で停止します。メッセージには検出したフォルダー、`MODEL_PATH` を指定する方法、`ALLOW_DOWNLOAD=1` による続行方法、および `Nothing was downloaded.` が含まれます（`docker/entrypoint.sh:37-39, 47-50`）。

この変数はシェル起動時に一度だけキャッシュされる値ではなく、ガード関数内のパラメーター展開で評価されます。通常の entrypoint ではガード呼び出しは一回です。後続では `strata launch --no-tui ...` が子プロセスとして起動され、失敗時は launch の終了コードを使ってコンテナを終了します（`docker/entrypoint.sh:189, 252-290`）。ソース内に `ALLOW_DOWNLOAD` を読み取ってエンジンへ渡す箇所は見つかりませんでした。

## 根拠

- 変数の値とガードの警告／終了分岐: `docker/entrypoint.sh:42-50`
- 旧配置の移行条件: `docker/entrypoint.sh:85-103`
- 非標準コマンドの早期実行、`MODEL_PATH` / `GGUF_DIR` の解決と検証、ガード呼び出し: `docker/entrypoint.sh:53-56, 176-192`
- launch の起動と異常終了経路: `docker/entrypoint.sh:252-290`
- Dockerfile の標準 entrypoint: `Dockerfile:100-111`, `docker/Dockerfile:87-89, 128-134`
- Docker 利用者向けの設定説明: `docs/DOCKER.md:110-119, 277-283`
