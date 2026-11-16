# `STRATA_GGUF_PY`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

この変数は、Strata の Python 準備・変換ツールが使う GGUF Python モジュールの場所を指定する。`tools/_paths.py:50-65` の `gguf_lib()` は、有効な指定があればそのディレクトリを `sys.path` の先頭に置いて `gguf` を返し、指定がなければ Strata 所有の `tools/strata_gguf.py` を返す。例えば `iq_pack.py` は返されたモジュールから `GGUFReader` などを取得している（`tools/iq_pack.py:113-119`）。エンジンの実行時設定ではなく、GGUF を準備する Python プロセスのライブラリ選択である。

別経路の `add_gguf_py()` は llama.cpp の converter を import するための検索に同じ変数を使う。指定、Strata 同梱のコピー、開発ツリー、インストール先の順で `gguf` パッケージを探し、見つかったディレクトリを `sys.path` に追加する（`tools/_paths.py:22-47,68-71`; 呼び出し例: `tools/nvfp4_convert.py:32-40`）。

## 値と判定

値は文字列全体をパスとして扱い、真偽値や数値への変換はしない。前後空白の除去、大文字小文字変換、`~` 展開、絶対パス化は行わない。相対パスはその Python プロセスの作業ディレクトリ基準となる。受理条件は指定ディレクトリ直下に `gguf/` ディレクトリがあること（`tools/_paths.py:39-45,53-60`; `setup.py:3788-3802`）。

| 読み取り経路 | 未設定 | 空文字 | 有効な指定の例 | 無効な指定の例と結果 |
|---|---|---|---|---|
| `gguf_lib()` を使う準備ツール | Strata の `tools/strata_gguf.py` を選ぶ | 未設定と同じ | `/src/llama.cpp/gguf-py`（直下に `gguf/` がある）を選ぶ | `true`、`0`、空白だけの文字列なども文字列パス。直下に `gguf/` がなければ `STRATA_GGUF_PY=<値> does not hold a \`gguf\` package` で終了 |
| `add_gguf_py()` を使う converter 経路 | 同梱・開発・インストール先の順に検索 | 未設定と同じ | 同じディレクトリを優先候補にする | 指定先に `gguf/` がなければ次の候補を検索。候補がすべてなければ `gguf-py was not found...` で終了 |
| `setup.py` の子プロセス環境 | 既存環境を引き継ぐ（この変数は追加しない） | 既存の空文字を引き継ぐ | `gguf/` のある指定ならそのパスを子環境にも設定 | `gguf/` がない指定では helper が追加設定しないため、元の非空値が子環境に残る。子の `gguf_lib()` は上記エラーで終了 |

`true` / `false` / `0` / `1` に特別な意味はない。`own` の真偽値判定なので空文字だけが未設定と同じ扱いで、空白文字列は非空のパスとして検査される（`tools/_paths.py:53-56`; `setup.py:3792-3802`）。

## 有効になる条件

- Strata のエンジン起動ではなく、`tools/_paths.py` の helper を使う Python ツールが実行されること。OS、GPU backend、build macro、モデル状態による条件はない。
- `gguf_lib()` 経路では、非空の指定先に `gguf/` が必要。条件を満たすと `gguf` モジュールを選択し、満たさない場合は vendored fallback をせず終了する（`tools/_paths.py:50-65`）。
- `add_gguf_py()` 経路では指定先が不適合でも後続候補を検索する。`STRATA_INSTALL_DIR` はこの検索のインストール先候補を追加し得るが、`gguf_lib()` の分岐条件ではない（`tools/_paths.py:22-47,68-71`）。
- `setup.py` は有効な override だけを子環境に明示設定する一方、`run()` は指定された環境を子プロセスに渡す。従って不適合な非空値が親環境にある場合、その値は通常の準備ツールにも残り、`gguf_lib()` を使う子では失敗する（`setup.py:3798-3802,894-912`）。

## 実行時の詳細

Strata の C++/CUDA/HIP/SYCL エンジンやサーバーモードからの読み取りは見つからなかった。読み取りは `setup.py` の helper 呼び出し時、または各 Python ツールが `_paths.py` の helper を呼ぶ時点で行われる。対象箇所に環境値の static cache はない。helper を再度呼べばその時点の環境を再読するが、ツールが import 時に `gguf = gguf_lib()` を実行する場合は、そのモジュール選択はその import 時点で行われる（`tools/_paths.py:39-71`; 例: `tools/mtp_pack.py:32-35`）。

setup の各準備段階では `dict(os.environ, **gguf_py_env())` を作り、tokenizer、pack、MTP などの Python 子ツールへ渡す。値を有効な別ディレクトリへ後から変更しても、既に作成済みの `env` や起動済み子プロセスには反映されない（`setup.py:8844-8849,9011-9018,9233-9246,10292-10303`）。

## ログと測定値

- `gguf_lib()` が不適合な非空値を受け取ると、標準エラーに `STRATA_GGUF_PY=<値> does not hold a \`gguf\` package` を出して終了する（`tools/_paths.py:53-60`）。setup がこの子プロセスを実行する場合、`run()` は非ゼロ終了を `command failed (exit <番号>): <実行ファイル名>` として失敗扱いにする（`setup.py:894-912`）。
- `add_gguf_py()` の検索先がすべて見つからない場合は `gguf-py was not found. It ships with Strata in third_party/strata-gguf-py; set STRATA_GGUF_PY to the folder that holds the \`gguf\` package (for example <llama.cpp>/gguf-py) to use another copy` で終了する（`tools/_paths.py:39-47,68-71`）。
- Strata の資料に、この変数による性能測定値は見つからなかった。

## 根拠

- 値の読み取り、パッケージ選択、検索順、終了経路: `tools/_paths.py:22-71`
- setup における値の検証と子環境への設定: `setup.py:3788-3802`
- 子プロセス実行と非ゼロ終了時の扱い: `setup.py:894-912`
- setup の準備ツールへの環境引き渡し: `setup.py:8844-8849,9011-9018,9233-9246,10292-10303`
- `gguf_lib()` の利用例: `tools/iq_pack.py:113-119`; converter 経路: `tools/nvfp4_convert.py:32-40`
