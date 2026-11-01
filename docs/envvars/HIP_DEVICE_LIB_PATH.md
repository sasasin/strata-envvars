# `HIP_DEVICE_LIB_PATH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `main...origin/main` で変更なし。

## 役割

この候補名を Strata エンジン本体が独自設定として読むコードは見つかりませんでした。Strata の Python サーバーは起動環境から値を子プロセス用環境へ引き継ぎ、AMD/HIP backend では値が空でなく、そのパスが存在しないときに子プロセスへ渡さないよう除去します。つまり Strata が行うのは環境の引き継ぎと stale path の除去です。転送後にエンジン、HIP runtime、driver が値をどう使うかはこの文書の対象外です。

## 値と判定

`hip_env_guard()` は文字列を数値や真偽値に変換しません。`env.get("HIP_DEVICE_LIB_PATH")` の値が Python の真として評価される（空文字列でない）場合だけ `Path(v).exists()` を調べます。

| 子環境に入った値 | HIP backend のサーバー処理 |
|---|---|
| 未設定 | 何もしない。未設定のままエンジンに渡す |
| 空文字列 | `if v` が偽なので何もしない。空文字列のまま渡す |
| 空でない文字列で、サーバーの現在の作業ディレクトリ基準でパスが存在する | その値を保ったまま渡す。`exists()` のみを確認し、ディレクトリかどうか、値の形式、内容は検証しない |
| 空でない文字列で、パスが存在しない | 子環境からキーを削除し、stderr に `strata serve: AMD: HIP_DEVICE_LIB_PATH=<値> does not exist: not passed to the engine` を出す |

空白、相対パス、絶対パス、シンボリックリンクなどを Strata 独自の規則で変換する処理はありません。相対パスの存在確認は `Path(v).exists()` によるもので、`cfg["cwd"]` を基準に解決する処理ではありません（`serve/server.py:3823-3827`）。

## 有効になる条件

- `child_env()` はまずサーバーの `os.environ` を辞書に複製し、設定の `cfg["env"]` があればその項目を `str(k)` / `str(v)` にして上書きします。したがって設定の `env.HIP_DEVICE_LIB_PATH` は親プロセス環境の値より優先され、その後の HIP guard の検査対象になります（`serve/server.py:3747-3760`）。
- guard が呼ばれるのは `cfg["backend"] == "hip"` のときだけです。CUDA など他 backend の場合、サーバーはこの値を guard で検査せず、複製または設定から得た値を子環境に残します（`serve/server.py:3782-3790`）。
- 通常のエンジン起動に加え、replica と split serving の各エンジンも `child_env()` の結果を使います（`serve/server.py:8704-8710,8769-8777,9193,9273-9279`）。
- CLI 引数や別環境変数との値の優先順位、CLI による上書きはこのキーについて実装されていません。エンジン本体の設定として解釈するコードも確認できませんでした。

## 実行時の詳細

この値の処理は子エンジンの環境を組み立てるときに行われます。`child_env()` が呼ばれるたびに `os.environ` を複製し、HIP backend ならその時点で guard が存在確認します。値を static cache する処理はありません。作成された環境辞書は `StrataEngine` から `popen(..., env=env)` に渡され、起動した子プロセスの環境になります（`serve/server.py:3747-3790,1074-1079`）。したがって、サーバー稼働中に親環境が変わっても既に起動中の子の環境は変更されず、後で `child_env()` を再度呼ぶ起動ではその呼び出し時点の環境が使われます。

存在しない非空パスを guard が除去しても、この処理自体は例外終了させず、診断行を stderr に出して環境辞書を返します（`serve/server.py:3815-3845`）。パスが存在すると guard はその値を変更しません。エンジン起動後の値の利用、起動失敗や GPU runtime の挙動は、Strata がこの値を読む・転送するコードからは断定できません。

## 根拠

- `serve/server.py:3747-3790` — 親環境の複製、設定 `env` の上書き、HIP backend での guard 呼び出し。
- `serve/server.py:3815-3845` — `HIP_PATH` / `HIP_DEVICE_LIB_PATH` / `LLVM_PATH` の存在確認、削除条件、stderr の文言。
- `serve/server.py:1074-1079` — 作成した環境辞書を `popen` に渡す箇所。
- `serve/server.py:8704-8710,8769-8777,9193,9273-9279` — 通常、replica、split serving の起動経路。
- `serve/test_server.py:1981-1995` — テストは存在しない `HIP_DEVICE_LIB_PATH` が環境辞書から除かれることを確認する（本番動作の根拠は上記実装）。
- `docs/TROUBLESHOOTING.md:305-310` — Windows AMD の起動時問題の説明。詳細な挙動の根拠は実装箇所。
