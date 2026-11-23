# `PYTHON`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`PYTHON` は Strata の実行時設定ではなく、Linux 向けエンジンのビルド・パッケージ作成や CUDA ヘッダー取得で Python コマンドを選ぶシェル変数である。対象スクリプトは、選択したコマンドで `collect_libs.py`、`package_engine.py` などを実行する。値が変えるのはこれらの補助スクリプトを起動するコマンドであり、生成される `strata` の実行時挙動ではない（`tools/packaging/build_cuda_linux.sh:28,73,78,81`、`tools/packaging/build_sycl_linux.sh:28,61,74,77`、`tools/packaging/build_cuda_linux_aarch64.sh:17,40,45,46`、`engine/spark/build_engine.sh:24,86`、`engine/sycl/tools/get-cuda-headers.sh:5-10`、`tools/docker/publish.sh:55,70`）。

## 値と判定

各スクリプトはシェルの `${PYTHON:-python3}` で選択する。未設定または空文字なら `python3`、それ以外は値をそのまま実行コマンドとして用い、Python のバージョンや値の形式を検証しない。`0`、`1`、`true`、`false` を特別扱いせず、いずれもコマンド名として渡す。空白だけの値も空文字ではないためフォールバックしない。

| 条件（スクリプト） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA x86_64、SYCL、CUDA ARM64、Spark エンジン | `python3` | `python3`、`/venv/bin/python` など実行可能なコマンド | 実行できないコマンド名（例: `missing-python`） |
| Docker publish | `python3` | `python3`、`/venv/bin/python` など実行可能なコマンド | 実行できないコマンド名 |
| `get-cuda-headers.sh` | `python3` | `python3`、`/venv/bin/python` など | 実行できないコマンド名 |

ここで「有効」は指定コマンドの起動に成功する意味で、スクリプトは実行可能性を事前確認しない。ほとんどのスクリプトではコマンドを `"$py"` / `"$PY"` と引用して一つの実行ファイル名として扱う。一方 `get-cuda-headers.sh` は `$py` を引用せず、`publish.sh` も `$PY` を引用せずに実行するため、空白や glob 文字を含む値は単一の実行ファイルパスとして保たれない（`engine/sycl/tools/get-cuda-headers.sh:7,10`、`tools/docker/publish.sh:70`）。

## 有効になる条件

- 関連する補助スクリプトを実行するビルド／パッケージ経路を使う場合に限り参照される。Strata エンジンの通常起動や CLI からは読み取られない。
- コマンドがシェルから起動可能であり、呼び出し先の Python スクリプトを実行できる必要がある。スクリプト側に失敗時の別 Python への再試行はない。
- `build_cuda_linux.sh` と `build_sycl_linux.sh` は選択コマンドをそれぞれライブラリ収集、パッケージ作成、検証にも使う。Spark のパッケージラッパーは環境を保ったまま `engine/spark/build_engine.sh` を起動し、そのスクリプト自身が選んだコマンドでライブラリ収集する（`tools/packaging/build_cuda_linux.sh:73-81`、`tools/packaging/build_sycl_linux.sh:61-78`、`tools/packaging/build_cuda_linux_aarch64.sh:34,40-46`、`engine/spark/build_engine.sh:86`）。
- CLI 引数や別の環境変数による Python コマンドの上書きはこれらの箇所にはない。なお `VARIANT`、CUDA/SYCL の build 条件などは各ビルドスクリプトの経路自体を決めるが、`PYTHON` の値判定は変えない。

## 実行時の詳細

値は各シェルスクリプトの実行時に、代入行で一度だけ展開され、そのスクリプト内の後続コマンドに使われる。プロセス起動後に親環境の値を変えても、既に代入した `py` / `PY` には反映されない。複数の独立したスクリプトを起動する場合、それぞれが自身の代入行で環境を読む。

対象経路は次の通り。

- CUDA x86_64 ビルド: Python コマンドで `collect_libs.py`、`package_engine.py` の作成・検証、`binary_deps.py` を実行する（`tools/packaging/build_cuda_linux.sh:28,73,78,81`）。
- SYCL ビルド: `collect_libs.py` とパッケージ作成・検証に使う（`tools/packaging/build_sycl_linux.sh:28,61,74,77`）。
- CUDA ARM64 パッケージ: ラッパーで Python コマンドを選び、Spark ビルドスクリプトへも同じ環境変数を継承させる。ラッパーは選択コマンドでパッケージ検証と依存確認を行い、Spark 側は独自に同じ既定規則で `py` を選ぶ（`tools/packaging/build_cuda_linux_aarch64.sh:17,34,40,45-46`、`engine/spark/build_engine.sh:24,86`）。
- Docker publish: Python コマンドで `fetch-engines.py` を実行する（`tools/docker/publish.sh:55,70`）。
- CUDA ヘッダー取得: Python の pip で NVIDIA CUDA wheel をダウンロードし、同じ Python に渡した短いスクリプトで wheel のヘッダーを展開する（`engine/sycl/tools/get-cuda-headers.sh:5-23`）。

いずれも `set -e` / `set -eu` が設定され、選択コマンドが存在しない、または Python スクリプトが失敗した場合は、そのコマンドの終了ステータスでシェル処理が停止する（例: `tools/packaging/build_cuda_linux.sh:16,73`、`tools/packaging/build_sycl_linux.sh:18,61`、`tools/packaging/build_cuda_linux_aarch64.sh:15,40`、`engine/spark/build_engine.sh:17,86`、`engine/sycl/tools/get-cuda-headers.sh:3,7`、`tools/docker/publish.sh:70`）。

## ログと測定値

`PYTHON` 固有の成功・失敗メッセージはなく、選択したコマンドの標準出力・標準エラーが通常どおり出る。コマンド起動や Python スクリプトが失敗すれば、上記のとおり `set -e` により処理が止まる。ビルド時のエラー文言は、そのコマンドや呼び出された Python スクリプトが出す内容に依存する。Strata の資料に `PYTHON` による性能測定値はない。

## 根拠

- `tools/packaging/build_cuda_linux.sh:16-32,73-81` — 空値を含む既定値、コマンド選択と Python ツール呼び出し。
- `tools/packaging/build_sycl_linux.sh:18-30,61-78` — 空値を含む既定値と SYCL パッケージ経路での使用。
- `tools/packaging/build_cuda_linux_aarch64.sh:15-28,34,40-46`、`engine/spark/build_engine.sh:17-25,86` — ARM64 パッケージラッパーと Spark エンジンビルドでの使用。
- `engine/sycl/tools/get-cuda-headers.sh:3-10` — CUDA header wheel の取得・展開。
- `tools/docker/publish.sh:48-70` — Docker publish 時の Python コマンド選択。
- リポジトリ全体の `PYTHON` 参照確認 — 上記以外に製品実行時の環境取得はなく、他の厳密一致参照は docs、コメント、テスト用識別子、固定バージョン定数などだった。
