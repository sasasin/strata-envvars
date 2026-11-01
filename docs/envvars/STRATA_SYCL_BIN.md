# `STRATA_SYCL_BIN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリ・GPU driver の環境変数動作は対象外。

## 役割

Intel SYCL 用の serve 起動スクリプトが、コンテナ内で実行する Strata engine の実行ファイルを選びます。既定はリポジトリ相対の `build-sycl-aot/strata` です。加えて serve server は、`effort_position: "end"` を使える engine か調べるとき、この変数から実際の engine binary のパスを解決します。CUDA/HIP engine 自身の設定値ではなく、engine 起動前のパス選択用です。

## 値と判定

| 読み取り箇所 | 未設定 | 空文字 | 設定値 |
|---|---|---|---|
| `sycl/serve/strata-sycl.sh` の起動 | `build-sycl-aot/strata` | Bash の `${VAR:-default}` により `build-sycl-aot/strata` | 指定文字列を engine path として使う |
| `serve/server.py` の `engine_binary()` | config の値、なければ親 process 環境、なければ `build-sycl-aot/strata` | Python の `or` 判定により空値を飛ばし、次の候補へ進む | config の `env` 値が truthy ならそれを優先。そうでなければ親 process 環境の値 |

shell 側は値を数値や真偽値として parse せず、文字列をパスとして展開します。相対 path は `cd $repo_in` 後のコンテナ内リポジトリを基準に解決されます。形式検証、存在確認、範囲制限、CLI 引数による上書きはこの shell にありません。server 側の engine binary 探索は launcher 名が `strata-sycl.sh` の場合だけ行い、launcher のリポジトリ root から `rel` を結合します。候補ファイルが存在すればその binary を返し、なければ launcher 自体を返します。

## 有効になる条件

- shell での engine 選択は `sycl/serve/strata-sycl.sh` が起動されたときに適用されます。通常の serve server は設定された launcher を `--serve` と引数付きで子 process として起動します。
- server の binary 探索は設定された `exe` の basename が `strata-sycl.sh` の場合に限られます。また `effort_position` が既定の `start` なら binary 探索を呼ばず、`end` の場合に feature check で使います。
- `sycl/setup_intel.py` は選択した engine が `build-sycl-aot/strata` と異なる場合に、その checkout 相対 path を config の `env.STRATA_SYCL_BIN` に設定します。既定 binary と同じならこの項目は書きません。
- serve server の `child_env()` は親 process 環境を複製し、その後 config の `env` 項目を上書きします。したがって launcher の実行時は config の設定が同名の親環境値より優先されます。server の事前 binary 探索では逆に config 値を最初に見て、truthy でなければ親環境値へ進みます。

## 実行時の詳細

launcher は `STRATA_SYCL_*` を launcher 自身の設定として扱い、Docker に渡す環境変数一覧から除外します。一方、最終コマンド文字列では `${STRATA_SYCL_BIN:-build-sycl-aot/strata}` を `exec` するため、この変数はコンテナ内の engine path に使われます。つまり launcher 自身が値を消費し、engine に同名変数を転送する処理ではありません。setup が非既定 path を選んだ場合は、その値を server config の `env` に保存し、server が子 launcher の環境へ渡します。

値は起動時の shell 展開と、server の `effort_position` 判定時に読み取られます。server の binary check は解決した path を開いて `--tail-role-token` の byte 列を検索します。ファイルを開けない、option がない、または system token の encode 結果が 1 token でない場合、標準出力に `effort_position "end" needs engine 0.1.39 or newer (--tail-role-token): the reasoning effort stays at the top of the prompt` と出し、追加引数を返しません。条件を満たせば有効化ログを出して `--tail-role-token <id>` を返します。path が launcher が起動するファイルと異なると、feature check の結果もその異なる binary に基づきます。

launcher の選択先が実行できない場合、shell の `exec` が失敗し、`set -e` により script は失敗します。Strata の server は子 process 起動時の `OSError` を捕捉しますが、engine path の失敗時に表示される具体的な OS エラー文言は環境に依存します。ここで確認できるのは Strata の起動先指定と server の fallback までであり、Docker や engine binary 内部の処理は説明対象外です。

## 根拠

- `sycl/serve/strata-sycl.sh:17-21,28-39,42-48`: shell 実行時の設定、`STRATA_SYCL_*` の転送除外、default 展開、Docker 内の engine 起動。
- `serve/server.py:3128-3139`: launcher の判定、config → 親環境 → default の binary path 解決、ファイルがない場合の fallback。
- `serve/server.py:3142-3164`: `effort_position` が `end` のときの binary feature check、ログと返却引数。
- `serve/server.py:1048-1080`: 子 engine の起動と `env` の受け渡し、起動失敗の捕捉。
- `serve/server.py:3747-3760`: 子環境の生成と config `env` による上書き。
- `sycl/setup_intel.py:369-386`: SYCL backend / launcher の設定と、非既定 engine path の config 保存。
- `docs/INTEL_ARC.md:105-106`: top-level build 構成では `-S sycl` または `STRATA_SYCL_BIN` を使うという案内。実際の動作根拠は上記コード。
