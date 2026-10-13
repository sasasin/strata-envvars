# `STRATA_SYCL_ROOT`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有のセットアップ・サーバー・起動スクリプト。外部ライブラリと Docker 自身の動作は対象外。

## 役割

Intel SYCL ポートの Docker 実行で、ホスト上のどのディレクトリをコンテナの `/work` にマウントするかを指定します。セットアップ時にはモデルやデータなどをコンテナ内の `/work/...` パスへ変換する基準にもなります。CUDA/HIP の通常セットアップや Strata エンジン本体がこの名前を直接読む処理はありません。

## 値と判定

| 読み取り箇所 | 未設定 | 空文字 | 非空の値 |
|---|---|---|---|
| `sycl/setup_intel.py` | Strata checkout の親ディレクトリ (`ROOT.parent`) | `or ROOT.parent` により同じ既定値 | 文字列をそのまま `Path` に渡す |
| `sycl/serve/strata-sycl.sh` | スクリプトが属する Strata checkout の親ディレクトリ | Bash の `${VAR:-...}` により同じ既定値 | 指定値を Docker の `-v "$root:/work"` に使う |

値のトリム、環境変数内での `~` 展開、存在確認、絶対パス化は環境変数自体に対して行いません。セットアップのパス変換では `MOUNT.resolve()` が使われます。相対値はその Python プロセスの作業ディレクトリ基準で解決されます。シェル側では値をパスとして検証・正規化せず、そのまま Docker のマウント引数に使います。

## 有効になる条件

- `./setup.sh --backend sycl` で Intel セットアップ経路を使う場合、`MOUNT` がセットアップ起動時に決まり、生成する SYCL 設定に反映されます。
- 指定したマウントルートの外にあるモデル等のパスを `sycl_path()` に渡すと、セットアップは `[X] ... is outside ...` とヒントを表示して終了します（`setup.py:331-336`）。コンテナ内で必要な checkout、モデル、データをマウント配下に置くための検査です。
- 生成設定では `STRATA_SYCL_ROOT` を省略するのは、解決後の指定ルートが既定の `ROOT.parent` と同じ場合です。異なる場合は設定の `env` に保存されます。
- SYCL サーバー起動で `sycl/serve/strata-sycl.sh` が呼ばれる場合に、実際の bind mount に使われます。別の backend の起動にはこのスクリプトを通じた効果はありません。

## 実行時の詳細

セットアップは Python モジュールの初期化時に `os.environ.get("STRATA_SYCL_ROOT") or ROOT.parent` を一度評価します。設定生成時、モデル等の各パスを `MOUNT.resolve()` からの相対パスにし、コンテナ用 `/work/...` に変換します。カスタムルートを使うときは `env["STRATA_SYCL_ROOT"] = str(MOUNT)` を設定へ書き込みます（ルートが既定と同じときは書き込みません）。セットアッププロセスの途中で環境を書き換えても `MOUNT` は再評価されません。

サーバー側の `child_env()` は親プロセスの環境を複製し、設定の `env` 項目を上書きします。したがって、生成設定に保存されたカスタムルートがあればそれが優先され、なければサーバープロセスから継承した値がラッパーに届きます。ラッパーは起動時にその値を使ってディレクトリを `/work` に bind mount し、エンジンをコンテナ内の checkout から実行します。

既定ルートの説明、コンテナから見たパスの制約、シンボリックリンク先をマウント外に置くとコンテナで使えない点は `docs/INTEL.md` にも記載されています。これは Strata の文書上の説明であり、Docker の内部動作そのものはこの調査の対象外です。

## 根拠

- `sycl/setup_intel.py:33-40`: checkout の `ROOT`、起動ラッパー、import 時の環境変数評価。
- `sycl/setup_intel.py:99-107`: `MOUNT.resolve()` を基準としたパス変換と、マウント外パスのセットアップエラー。
- `sycl/setup_intel.py:191-208`: 設定の `sycl_root` と、カスタムルートの `env` への保存。
- `serve/server.py:2622-2633`: エンジン子プロセス環境の複製と、設定 `env` の反映。
- `sycl/serve/strata-sycl.sh:6-16,37-41`: 変数の既定値と Docker の `/work` マウント、コンテナ内実行。
- `docs/INTEL.md:72-81`: SYCL 設定とマウント対象ディレクトリに関する説明。
