# `GGUF_DIR`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Docker イメージの既定サーバー起動で、コンテナ内に既にある GGUF ファイルの場所を指定する旧名です。entrypoint は `MODEL_PATH` が空の場合に `GGUF_DIR` を代替として使い、最終的に `strata launch --model-path` 引数へ渡します。GGUF_DIR を読むのは `docker/entrypoint.sh` だけです。Strata のエンジンや一般の `strata` CLI がこの環境変数を直接読む実装は見つかりませんでした。

`docs/DOCKER.md` も `GGUF_DIR` を `MODEL_PATH` の旧名として記載しており、entrypoint の互換処理と一致します（`docs/DOCKER.md:273`）。

## 値と判定

| 状態 | entrypoint の扱い |
|---|---|
| `MODEL_PATH` が空でなく設定されている | `GGUF_DIR` より優先して `MODEL_PATH` を使用 |
| `MODEL_PATH` が未設定または空、`GGUF_DIR` が空でなく設定されている | `GGUF_DIR` の値を使用 |
| 両方が未設定または空 | モデルパスを指定しない |

`${VAR:-...}` によるシェル展開なので、未設定と空文字は同じ扱いです。空白だけの値は空文字ではないため、そのままパスとして扱われます。値の文字列比較、数値変換、trim、大小文字変換はありません。優先順位の展開後にパスが存在するかを調べ、値が存在しないパスなら stderr に `[X] MODEL_PATH=... is not in the container ... Nothing was downloaded.` と出して終了コード 2 で停止します。ディレクトリの場合、`.gguf` が直下にないが深さ 2 までに見つかると、そのフォルダーを指定するよう案内して同じく終了コード 2 で停止します。`.gguf` が見つからない場合も終了コード 2 です。既存の単一ファイルは後続 CLI が受け付けるパス形式です。

## 有効になる条件

- `docker/entrypoint.sh` の通常サーバー経路（引数なし、または先頭引数が `run` / `serve`）でのみ参照されます。別コマンドを引数にして起動した場合は、そのコマンドを `exec` する分岐で終了するため、この変数は評価されません。
- 値が選ばれても、空文字なら `--model-path` を付けません。パスが指定されると `MODEL_PATH` と同じ方法で検査され、CLI に渡されます。
- `MODEL` も指定されると `--model` と `--model-path` の両方が渡ります。CLI は両方がある場合、明示したモデルを選びつつファイルパスも保持します。`MODEL` がなくパスだけの場合、CLI はそのファイル群からモデルを判定します。
- この変数は Docker entrypoint の互換入力です。付属の Docker Compose 定義は `MODEL_PATH` を環境へ渡しますが `GGUF_DIR` は渡さないため、Compose 経由で使う場合は Compose 側の設定でコンテナ環境に `GGUF_DIR` を渡す必要があります。

## 実行時の詳細

entrypoint は `MODEL_PATH` を優先して `GGUF_DIR` にフォールバックした値を検証し、非空なら `--model-path "$model_path"` を `strata launch --no-tui` の引数列に追加します。`MODEL` 等の設定も同じ引数列に加え、`strata launch` を子プロセスとして起動します。環境変数の値をキャッシュして再利用する仕組みはなく、entrypoint の起動処理で一度シェル展開されます。起動後に親環境を書き換えて再評価する経路はありません。

CLI は `--model-path` を受け取るとパスを設定に保存します。モデル指定がなければモデル一覧から該当ファイルを解決し、見つからない・不整合がある場合は `strata launch` のエラーとして終了します。Runner は選択されたファイルを `setup.py --gguf-dir` に渡して準備し、モデル準備中は `Preparing ... from your model files…` を出します。従って `GGUF_DIR` 自体がモデルのダウンロードを制御するのではなく、Docker wrapper が既存ファイルのパスを CLI に伝える役割です。

## 根拠

- `docker/entrypoint.sh:53-56` は通常サーバー経路以外を先に `exec` し、`docker/entrypoint.sh:176-192` で `MODEL_PATH` 優先の選択、パス検査、`--model-path` 追加を行います。
- `docker/entrypoint.sh:179-187` は存在しないパス、直下に `.gguf` がないディレクトリ、`.gguf` を含まないディレクトリの停止メッセージと終了コードを定めます。
- `docker/entrypoint.sh:274-292` は選択されたパスを起動表示に使い、`strata launch` を起動して失敗時に終了コードを伝えます。
- `strata_cli/launch/cmd.py:89,212-230` は `--model-path` の引数定義と設定への反映、`MODEL` と併用された場合のモデル選択を実装します。`strata_cli/launch/cmd.py:377-384,908-910` はモデル未指定時の推薦と、指定パスの確認呼び出しを示します。
- `strata_control/models.py:596-617` は CLI 側のパス検証、`strata_cli/launch/runner.py:1462-1508` はファイル群からのモデル特定と不正ファイル時の失敗、`strata_cli/launch/runner.py:965-968,1187-1191` は後続 setup に渡す処理と準備ログを示します。
- `docker/compose/docker-compose.nvidia.yml:16-19`（同様に AMD / Intel の compose 定義）は `MODEL_PATH` を渡し、`GGUF_DIR` は渡しません。
- `tools/dsv41/dense_requant.py:7` にも `GGUF_DIR` という文字列がありますが、これはコマンド例中の引数名であり、環境から値を読む箇所ではありません。
