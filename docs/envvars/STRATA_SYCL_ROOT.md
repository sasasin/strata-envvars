# `STRATA_SYCL_ROOT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata の SYCL セットアップと起動ラッパーでの読み取りを対象とする。

## 役割

Intel SYCL 版を Docker コンテナで起動するとき、ホスト側のどのディレクトリをコンテナ内 `/work` にマウントするかを指定します。セットアップでは同じ値をパス変換の基準にも使い、モデルや pack などのホストパスをコンテナ内の `/work/...` に変換します。環境変数は `sycl/setup_intel.py` の import 時に一度読み取られ、生成する実行設定に必要な場合は記録されます。起動ラッパーはそのプロセス環境から値を読み、Docker の volume 指定に使います。

## 値と判定

| 場面 | 未設定 | 空文字 | 設定値 |
|---|---|---|---|
| `sycl/setup_intel.py` のセットアップ | `ROOT.parent`（Strata checkout の親）を使う | `os.environ.get(...) or ...` のため未設定と同じ | `Path` に変換して mount root とする |
| `sycl/serve/strata-sycl.sh` の起動 | `dirname "$here"`（Strata checkout の親）を使う | Bash の `${STRATA_SYCL_ROOT:-...}` により未設定と同じ | `/work` のホスト側として `docker run -v` に渡す |

値の形式検証、空白除去、展開、存在確認はこの変数の読み取り箇所では行いません。セットアップのパス変換時には `MOUNT.resolve()` と比較し、相対値ならその時点の作業ディレクトリを基準に解決します。CLI 引数による `STRATA_SYCL_ROOT` の上書きはありません。`--models-dir` や `--data-dir` 等はパスの入力元になり得ますが、変数そのものの値を変更するものではありません。

## 有効になる条件

- 対象は `setup.sh --backend sycl` が使う `sycl/setup_intel.py` と、SYCL サーバー用の `sycl/serve/strata-sycl.sh` です。setup は Windows では SYCL を利用できないとして別途停止します（`sycl/setup_intel.py:98-105`）。
- セットアップ時に変数を設定した場合、変換対象となるモデル等のパスは解決後に mount root の配下である必要があります。root 外なら `sycl_path()` が `S.fail()` を呼び、対象パスと必要な `--models-dir / --data-dir` の案内を表示して終了コード 1 で setup を止めます（`sycl/setup_intel.py:108-116`, `setup.py:904-909`）。
- setup が選んだ `MOUNT` が標準の `ROOT.parent` と異なる場合、生成する設定の `env` に `STRATA_SYCL_ROOT` を保存します。同じ場所ならこのキーは保存せず、起動ラッパーの既定値が同じ親ディレクトリを選びます（`sycl/setup_intel.py:369-386`）。
- `STRATA_SYCL_ROOT` は起動ラッパー内で `/work` に mount するホスト側を決めるために使われます。ラッパーは `STRATA_SYCL_*` をエンジン用環境変数の転送対象から除外するため、この変数自体はコンテナ内エンジンには渡しません（`sycl/serve/strata-sycl.sh:19,29-38,42-48`）。

## 実行時の詳細

`sycl/setup_intel.py` はモジュール読み込み時に `MOUNT = Path(os.environ.get("STRATA_SYCL_ROOT") or ROOT.parent)` を評価します。この値を `sycl_path()` が各設定パスの `/work/` 以下の表記へ変換するのに使い、SYCL 用 config の `sycl_root` にも書きます。環境変数を setup の実行中に後から変更する処理はありません（`sycl/setup_intel.py:35-43,108-116,277-317,369-370`）。

SYCL サーバーがエンジンを起動するとき、`serve/server.py:child_env()` は親環境を複製した後、config の `env` の各項目を上書きします。したがって setup が保存した `STRATA_SYCL_ROOT` は起動ラッパーへ届き、config に保存されていなければサーバー起動時の親環境の値が使われます（`serve/server.py:3747-3760`）。`strata-sycl.sh` は値を `root` に読み、`-v "$root:/work"` としてコンテナを起動します。そこでコンテナ内の checkout は `/work/$(basename "$here")` として参照されます（`sycl/serve/strata-sycl.sh:18-20,42-48`）。

コードには、この変数専用の警告やエラーログはありません。setup のパス変換時に mount root 外を検出した場合は上記の `[X]` メッセージと終了があります。起動時の mount 値が不適切な場合に Docker やコンテナがどう失敗するかは外部実装の挙動なので、ここでは Strata の結果として断定しません。

## 根拠

- `sycl/setup_intel.py:35-43` — setup の root 定義と環境変数の読み取り。
- `sycl/setup_intel.py:108-116,277-317` — mount 配下へのパス変換と root 外の場合の停止。
- `sycl/setup_intel.py:369-386` — `sycl_root` の設定、既定 root と異なる場合の config `env` への保存。
- `serve/server.py:3747-3760` — config `env` の子プロセス環境への反映。
- `sycl/serve/strata-sycl.sh:18-20,29-48` — 起動時の既定値、SYCL 内部設定の除外、`/work` mount とコンテナ内 checkout。
- `docs/INTEL.md:45-50` — config の env がエンジンへ届くこと、およびモデル・pack・checkout を mount 対象の下に置く説明。
