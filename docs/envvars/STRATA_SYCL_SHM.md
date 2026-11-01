# `STRATA_SYCL_SHM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

この変数は `sycl/serve/strata-sycl.sh` が `docker run` にホストの `/dev/shm` を bind mount するか決めます。既定ではホストとコンテナで `/dev/shm` を共有し、`0` のとき mount を付けません。SYCL engine がこの変数を読む実装は見つかりませんでした。このスクリプトは `STRATA_SYCL_*` をコンテナへ転送対象にせず、この変数を mount の選択だけに使います。

主な用途は、ホストの server が画像 embeddings ファイルを `/dev/shm` に書き、コンテナ内 engine が `GENI` 要求で同じパスを読む画像入力です。

## 値と判定

スクリプトは `${STRATA_SYCL_SHM:-1}` を文字列 `0` と比較します。Bash の `:-` により未設定と空文字はいずれも `1` に置き換わります。文字列全体を数値変換せず、厳密に `0` と一致するときだけ mount を省略します。

| 環境値 | `/dev/shm` の mount 条件（ホストに `/dev/shm` がある場合） |
|---|---|
| 未設定 | 共有する（既定値 `1`） |
| 空文字 | 共有する（`:-1` による既定値） |
| `0` | 共有しない |
| その他（例: `1`, `00`, `false`） | 共有する |

値の範囲検査、警告、無効値 fallback のログはありません。`0` 以外の値はすべて共有側になります。

## 有効になる条件

- `sycl/serve/strata-sycl.sh` を起動したときに評価されます。環境変数を読む CLI 引数や設定ファイル上の別設定はありません。
- 値が `0` 以外で、かつホスト側の `/dev/shm` がディレクトリとして存在するときだけ `docker run` に `-v /dev/shm:/dev/shm` を渡します。ホストに `/dev/shm` がなければ、値にかかわらず mount は付きません。
- 起動後の再評価や cache はありません。子のコンテナへ `STRATA_SYCL_SHM` 自体は渡されず、mount 指定にだけ作用します（スクリプトの転送対象ループは `STRATA_SYCL_*` を除外します）。
- `STRATA_SYCL_SHM=0` はサーバーモードやモデル状態を直接切り替えません。ただしホストとコンテナの `/dev/shm` が別になるため、ホスト上の server がそこへ置いた画像 embeddings をコンテナ内 engine が同じパスから読めなくなる場合があります。画像を使わない要求にはこの受け渡し経路は関係しません。

## 実行時の詳細

`serve/server.py` は Linux で、ホスト `/dev/shm` に書き込み可能で空き容量が `2 * embeddings の byte 数 + 16 MiB` を超えると、画像 embeddings をそのディレクトリに置きます。条件を満たさない場合は encoder 側のディレクトリを使います（`serve/server.py:177-191`）。Intel server の `GENI` 行はこのファイルパスを engine に渡します（`serve/server.py:5305-5315`、`src/program/generate.cpp:13859-13866`）。

共有 mount がなく、ホスト側で選ばれた embeddings パスがコンテナから見えない場合、engine はファイルを開けず、serve protocol の stdout に `ERR cannot open <path>` を返してその要求を続行しません（`src/program/generate.cpp:14001-14009,14071-14079`）。これは `STRATA_SYCL_SHM=0` 専用の警告ではありません。Intel server は選ばれたパスが `/dev/shm/` 以外の場合に一度だけ stderr/log へ `/dev/shm has no room for this picture...` の警告を出しますが、これは容量不足などで server 側が `/dev/shm` を選ばなかった場合の検出であり、この環境変数の値を読んだ結果ではありません（`sycl/serve/server_intel.py:50-65`）。

この変数自体について、スクリプトのコメントと既存の Intel 文書は既定共有・`0` で private `/dev/shm` という説明で一致しています（`sycl/serve/strata-sycl.sh:10-16`、`docs/INTEL.md:305-307`）。ただし、実装上は `0` 以外を真偽値として解釈するのではなく、文字列 `0` だけを除外します。

## 根拠

- `sycl/serve/strata-sycl.sh:10-16`: 用途、既定値、値の転送対象についてのスクリプト説明。
- `sycl/serve/strata-sycl.sh:29-45`: `STRATA_SYCL_*` の除外と `/dev/shm` mount の条件、Docker への引き渡し。
- `serve/server.py:177-191,5305-5315`: embeddings ファイルの配置条件と画像要求での書き込み。
- `sycl/serve/server_intel.py:50-65,350-355`: Intel server の `/dev/shm` パス警告と初期化。
- `src/program/generate.cpp:13859-13866,14001-14009,14071-14079`: `GENI` の受け付け、embeddings ファイルの open、open failure 時の応答。
- `docs/INTEL.md:305-307`: 既存文書の説明。
