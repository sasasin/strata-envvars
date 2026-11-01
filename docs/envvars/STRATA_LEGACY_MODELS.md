# `STRATA_LEGACY_MODELS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。作業開始時の状態は `main...origin/main` で未コミット変更なし。

## 役割

Docker entrypoint が、旧モデル配置に `.gguf` ファイルが残っていて今回の起動で使うモデルパスが指定されていない場合に、誤って大きなモデルを再ダウンロードしないよう確認する際の検索先を指定します。環境変数の値は `/data/models` の代わりに `find` の検索ルートとして使われます。Strata engine にこの値を CLI 引数として渡す処理はありません（`docker/entrypoint.sh:45-50,176-189`）。

この読み取りは Docker イメージの標準起動経路にあります。ルート `Dockerfile` はこのスクリプトをコピーして entrypoint に指定し、既定の command を `run` にしています（`Dockerfile:100-111`）。`strata ...` や `sh` など別コマンドを直接指定した場合は、スクリプト冒頭で `exec` して終了するため、この変数を読むガードには到達しません（`docker/entrypoint.sh:53-56`）。

## 値と判定

シェルの `${STRATA_LEGACY_MODELS:-/data/models}` 展開を使います。未設定または空文字なら `/data/models`、空でない値は文字列のまま検索ルートになります。数値や特定の真偽値への変換・検証はありません。相対パスも拒否されず、entrypoint の作業ディレクトリを基準とする `find` のパスとして扱われます（`docker/entrypoint.sh:189`）。

| `STRATA_LEGACY_MODELS` | 使用される検索ルート |
|---|---|
| 未設定 | `/data/models` |
| 空文字 | `/data/models` |
| 空でない文字列（例: `/mnt/old-models`） | 指定文字列 |

## 有効になる条件

- Docker entrypoint が標準の `run` / `serve` 起動経路を進み、引数をそのまま `exec` する別コマンド経路に入らないこと（`docker/entrypoint.sh:53-56`）。
- `MODEL_PATH` と `GGUF_DIR` の優先規則で決まる `model_path` が空であること。`MODEL_PATH` が空または未設定なら `GGUF_DIR` が使われ、両方が空ならガードが有効です。非空の `model_path` は guard の先頭で検査を省略します。なお、指定されたモデルパスが存在しない、または `.gguf` がない場合は guard より前に exit 2 になります（`docker/entrypoint.sh:176-189`）。
- 検索先以下、深さ 3 までに `*.gguf` が少なくとも一つ見つかること。該当ファイルがなければ何もせず続行します（`docker/entrypoint.sh:45-48`）。

該当ファイルが見つかったときは `ALLOW_DOWNLOAD` が結果を決めます。`ALLOW_DOWNLOAD` が文字列 `1` と完全一致すれば警告を出して続行し、それ以外（未設定、空文字、`true`、`0` など）は説明を stderr に出して exit 2 します（`docker/entrypoint.sh:37-39,49-50`）。

旧標準位置 `/data/models` が独立した bind mount などでない場合、entrypoint は先に旧配置のファイルを `/data/Strata-data/models` へ移動します。移動に失敗した項目は警告されます。独立 mount は移動を飛ばすため、旧位置に残るモデルがこのガードの検索対象になり得ます（`docker/entrypoint.sh:85-103`）。カスタム `STRATA_LEGACY_MODELS` にファイルが残る場合も、同じガード条件で扱われます。

## 実行時の詳細

値は entrypoint 実行中に、引数を組み立てる段階で一度だけシェル展開されます（`docker/entrypoint.sh:176-189`）。`legacy_models_guard` は `model_path` が空でなければ即時 return し、空なら指定ルートに対して `find "$2" -maxdepth 3 -name '*.gguf'` を実行します。標準出力を `head -1` に通し、見つかった最初のパスを説明文に使います。検索エラーは stderr を `/dev/null` に捨てるため、検索先が読めない場合も結果が空ならガードは続行します（`docker/entrypoint.sh:45-49`）。

モデルファイルを見つけ、ダウンロードを許可しない場合、stderr に旧配置の場所、`MODEL_PATH` で使う方法、または `/data/Strata-data/models/<model folder>/` へ置く方法を含む説明を出し、文末に `Nothing was downloaded.` と表示して exit code 2 で終了します。`ALLOW_DOWNLOAD=1` の場合は同じ説明を `[!]` 付きで stderr に警告し、`Going on, because ALLOW_DOWNLOAD=1.` を加えて後続の `strata launch` 引数処理へ進みます（`docker/entrypoint.sh:37-39,49-50,189-193`）。

## 根拠

- 候補一覧に名前があります（`docs/envvars/000_envvers.md:1001`）。Strata ソースでの完全一致参照は `docker/entrypoint.sh:189` の1箇所で、値を読んで関数へ渡しています。
- 判定、検索、警告・終了は `docker/entrypoint.sh:37-50,176-193` にあります。
- 標準 Docker 起動への組み込みは `Dockerfile:100-111` にあります。

したがってこれは Strata engine 全般の設定ではなく、Docker entrypoint の旧配置モデル検出用の環境変数です。GPU backend や OS、build macro による分岐はこの読み取り経路にはありません。
