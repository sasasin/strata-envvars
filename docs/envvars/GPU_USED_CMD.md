# `GPU_USED_CMD`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`GPU_USED_CMD` は Strata リポジトリ同梱の `docker/smoke-test.sh` が、ホスト側から GPU 使用量を表示するための任意のシェルコマンドです。Strata の C++/Python 実行時設定ではなく、モデルの計算や GPU 選択、コンテナ設定を変えません。スクリプト冒頭の使用例は `nvidia-smi --query-gpu=memory.used --format=csv,noheader` です（`docker/smoke-test.sh:1-9,23`）。

## 値と判定

スクリプトは `${GPU_USED_CMD:-}` で未設定または空文字を空に展開し、`[ -n ... ]` で非空かどうかだけを判定します。空でない値は全体を二重引用符で `bash -c` に渡します。コマンド文字列の形式・終了状態・数値性は検証せず、空白だけの値も非空として実行を試みます。大文字小文字の比較や数値変換はありません（`docker/smoke-test.sh:10,23`）。

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | コマンドを実行せず `n/a` を出力 |
| 空文字 (`GPU_USED_CMD=`) | 未設定と同じく `n/a` を出力 |
| 非空（例: `nvidia-smi ...`、`echo 1`、空白だけ） | 文字列全体を `bash -c` のコマンドとして実行し、出力を処理 |

`0`、`false`、`true` も特別な真偽値ではなく、非空のシェルコマンド文字列です。シェル文法として無効な文字列や存在しないコマンドに対する独自 fallback はありません（`docker/smoke-test.sh:23`）。

## 有効になる条件

- `docker/smoke-test.sh` をホスト上で実行し、`gpu_used` 関数が呼ばれる場合に限ります。同スクリプトは Docker イメージの smoke test 用で、通常の Strata CLI・サーバー・engine の実行経路はこの変数を読みません（`docker/smoke-test.sh:1-9,23,26,77,91,105`; `docs/DOCKER.md:301`）。
- `GPU_USED_CMD` が非空であると、OS/backend/GPU 世代による分岐なしに `bash -c` の実行を試みます。例の `nvidia-smi` が利用可能かどうかはスクリプト内で確認しません。
- この値を `docker run` の環境変数としてコンテナへ渡す処理はありません。コンテナ起動引数は `API_KEY` と `${ENVS:-}`・`${VOLS:-}`・`${RUN_FLAGS:-}` 等から組み立てられます（`docker/smoke-test.sh:27-30`）。
- CLI 引数や別の環境変数による上書き・優先順位はありません。スクリプト起動時に呼び出し元から継承した環境値をシェルが参照します。

## 実行時の詳細

`gpu_used` は、スクリプト開始前後の GPU 使用量を表示するステップ（開始前、serving 中、最初の stop 後）で呼び出されます。さらに `RESTART` が文字列 `1` の場合は、2回目の stop 後の表示にも使われます（`docker/smoke-test.sh:23,26,77,91,94-105`）。関数は各呼び出し時に環境変数を展開してコマンドを実行し、値を static cache する処理はありません。スクリプト自身が値を書き換える処理もないため、通常は各回同じ継承値を使います。

非空値の場合、`bash -c "$GPU_USED_CMD"` の標準出力と標準エラーを合わせ、パイプで `head -3` に渡して先頭最大3行を取り、`tr '\n' ' '` で改行を空白に置き換えます。関数の出力は呼び出し元の `step` 文字列に埋め込まれ、スクリプト全体の stdout/stderr は `$OUT/test.log` に追記されると同時に `tee` で表示されます（`docker/smoke-test.sh:15-17,23,26,77,91,105`）。

## ログと測定値

独自の成功・失敗メッセージはなく、成功時はコマンド出力の先頭3行が `before: GPU used = ...`、`GPU used while serving: ...`、`GPU used after stop: ...` などのステップ表示に含まれます。未設定または空文字ならその箇所に `n/a` が入ります（`docker/smoke-test.sh:23,26,77,91,105`）。

コマンドが失敗しても、その終了状態を判定する処理や `bad` による smoke-test 失敗登録はありません。スクリプトは `set -u` のみを有効にしており、`set -e` や `pipefail` は設定していません。コマンドのエラー出力は標準出力と合わせて表示対象になりますが、3行を超える出力は表示されません（`docker/smoke-test.sh:10,22-23`）。この補助コマンドの失敗を理由にスクリプトが終了したり、最終終了コードが変わったりする実装はありません。

## 根拠

- `docker/smoke-test.sh:1-9` — スクリプトの用途と GPU 使用量コマンド例。
- `docker/smoke-test.sh:10-17,22-23` — シェル設定、出力先、失敗フラグ関数、および値の判定・実行・出力処理。
- `docker/smoke-test.sh:26,77,91,94-105` — 関数の全呼び出し位置と再起動条件。
- `docker/smoke-test.sh:27-30` — `docker run` 引数。`GPU_USED_CMD` をコンテナへ渡す指定がない。
- `docs/DOCKER.md:301` — `docker/smoke-test.sh` を実カード上の image smoke checks として案内。
- `GPU_USED_CMD` の Strata checkout 全体の完全一致検索では、実装参照は `docker/smoke-test.sh:23`、使用例コメントは同 `:6` のみ。索引候補は strata-envvars `docs/envvars/000_envvers.md:601`。
