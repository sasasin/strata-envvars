# `STRATA_GGUF_PY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

同梱の Python 準備ツールが使う GGUF ライブラリを、ユーザーが指定した `gguf-py` の `gguf` パッケージへ切り替えるためのパスである。指定先は `gguf/` ディレクトリを直接含むフォルダー（例: `<llama.cpp>/gguf-py`）。主な切替箇所は `terminal/tools/_paths.py` の `gguf_lib()` で、未指定なら `strata_gguf.py` を返し、指定が有効なら `gguf` を import して返す（`terminal/tools/_paths.py:57-72`）。

setup はこの値を準備用子プロセスへ引き継ぎ、モデルの pack 作成などから同じ選択を利用できる（`terminal/setup.py:4219-4223, 9883-9888, 10838-10845, 11061-11074, 12217-12247`）。これは setup と同梱 Python ツールのための設定であり、エンジンの推論・サーバー起動時の設定ではない。CPU/GPU backend、OS、ビルド macro、モデルの種類に応じた値変換はない。

## 値と判定

値を boolean や数値として parse せず、`os.environ.get` の返す文字列をパスとして使う。`gguf_lib()` は未設定または空文字列なら既定の `strata_gguf.py` を使い、空でない値なら `<値>/gguf` がディレクトリかを検査する。存在確認は `Path(...).is_dir()` であり、文字列の trim、大文字小文字変換、`~` の展開はしない（`terminal/tools/_paths.py:60-72`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `gguf_lib()` を使うツール | `strata_gguf.py` を使う | `/opt/llama.cpp/gguf-py` に `gguf/` ディレクトリがある | 空文字列は unset と同じ。`/missing` など、非空だが `gguf/` がないパスは終了する |
| `gguf_py()` / `add_gguf_py()` を使う converter 系ツール | vendored copy、開発ツリー、install folder の順に探索 | 指定先に `gguf/` がある場合は最初に選ばれる | 指定先が無効ならその候補を飛ばし、後続候補も無ければ探索失敗で終了する |

`0`、`1`、`true`、`false`、`0anything` は特別な値ではない。たとえば `1` は `<cwd>/1/gguf` が実在する場合だけパスとして有効であり、そうでなければ `gguf_lib()` では無効となる。空白だけの値も trim されず、その空白を含むパスとして検査される（`terminal/tools/_paths.py:46-54, 60-67`）。

setup の `gguf_py_dir()` は有効な非空パスならそれを返し、それ以外では vendored path を返す。`gguf_py_env()` は有効な指定時だけ上書き用の辞書を返す（`terminal/setup.py:4209-4223`）。ただし呼び出し側は `dict(os.environ, **gguf_py_env())` を作るため、無効な非空値は setup の子環境から削除されず元の値のまま残る。その値を `gguf_lib()` が読む子ツールでは明示エラーになる。このため setup の `gguf_py_dir()` が vendored path を選ぶことだけでは、無効値を指定した pack ツールが vendored へ fallback する保証にならない（`terminal/setup.py:9887-9888, 10842-10845, 11063-11074, 12220-12228`; `terminal/tools/_paths.py:60-67`）。CLI 引数による上書きは確認できない。

## 有効になる条件

- 対象プログラムが `gguf_lib()`、`gguf_py()` または `add_gguf_py()` を呼ぶ同梱 Python ツールであること。`gguf_lib()` 呼び出しは pack、検証、helper など複数のツールにある（例: `terminal/tools/iq_pack.py:117-125`, `terminal/tools/nvfp4_local_pack.py:456-462, 638-646`）。
- `gguf_lib()` で override を使うには、指定先に `gguf/` ディレクトリが必要。無効な非空値では fallback せず終了する（`terminal/tools/_paths.py:60-67`）。
- converter 系の `add_gguf_py()` は `gguf_py()` の探索順に従い、有効な指定先が無ければ vendored、開発ツリー、install folder を順に探す（`terminal/tools/_paths.py:46-54, 75-78, 81-86`; 呼び出し例: `terminal/tools/nvfp4_convert.py:39`, `terminal/tools/nvfp4_verify.py:28`）。
- GPU の有無、backend、モデル状態、サーバーモード、CLI のフラグによって変数自体を有効化する条件はない。値が作用するかは、その実行した Python ツールがどの helper を呼ぶかによる。

## 実行時の詳細

`gguf_lib()` と setup の `gguf_py_dir()` / `gguf_py_env()` は呼び出しごとに環境を参照し、値を保持する独自の static cache はない（`terminal/tools/_paths.py:57-72`; `terminal/setup.py:4209-4223`）。ただし選択後は通常の Python import を行うため、同一プロセスで import 済みの `gguf` / `strata_gguf` を環境値の変更だけで切り替える仕組みはない。setup の各準備処理は `os.environ` を複製した環境で Python 子プロセスを起動し、有効な指定時は helper が選んだパスをその環境に設定する（`terminal/setup.py:1131-1152, 9887-9888, 10842-10845, 11063-11074, 12220-12228`）。

`gguf_lib()` の override 分岐ではパスを `sys.path` の先頭へ挿入して `gguf` を import し、そのモジュールを呼び出し元へ返す。未指定・空文字列ならツールディレクトリを `sys.path` に加えて `strata_gguf` を import する（`terminal/tools/_paths.py:60-72`）。この切替が変えるのは準備ツール内の GGUF 読み書き・量子化 API の実装であり、エンジンが読み込むモデルや推論時の環境設定を直接変更するコードはない（`terminal/tools/_paths.py:3-5, 57-72`; `terminal/setup.py:9883-9888`）。

## ログと測定値

`gguf_lib()` に空でない無効な値を渡すと `sys.exit` により「STRATA_GGUF_PY=<値> does not hold a `gguf` package」を出して終了する（`terminal/tools/_paths.py:60-67`）。`gguf_py()` の探索先がすべて見つからない場合は「gguf-py was not found. It ships with Strata in third_party/strata-gguf-py; set STRATA_GGUF_PY to the folder that holds the `gguf` package (for example <llama.cpp>/gguf-py) to use another copy」で終了する（`terminal/tools/_paths.py:46-54`）。setup 経由で子コマンドが失敗すると、通常は `> <command>` を表示し、終了コードを含む `command failed (exit <n>): <program>` を setup 側で報告する（`terminal/setup.py:1141-1156`）。既定のライブラリを選んだことだけを示すログはこの helper にはない。Strata の測定値は該当しない。

## 根拠

- `terminal/tools/_paths.py:46-78` — GGUF パッケージ候補の探索、override の検証、モジュール選択。
- `terminal/setup.py:4209-4223, 4240-4242` — setup 側のパス判定と子環境用辞書。
- `terminal/setup.py:9883-9888, 10838-10845, 11061-11074, 12217-12247` — setup が準備用子ツールへ環境を渡す箇所。
- `terminal/setup.py:1131-1156` — 子プロセス実行と失敗時の報告。
- `terminal/tools/iq_pack.py:117-125`, `terminal/tools/nvfp4_local_pack.py:456-462, 638-646` — `gguf_lib()` を使う処理の例。
- `terminal/tools/nvfp4_convert.py:39`, `terminal/tools/nvfp4_verify.py:28`, `terminal/tools/nvfp4_verify_gguf.py:32` — `add_gguf_py()` を使う converter 系処理。
