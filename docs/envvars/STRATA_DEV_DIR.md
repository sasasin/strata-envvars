# `STRATA_DEV_DIR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。Strata 同梱 Docker entrypoint を対象とし、外部ライブラリや GPU driver の挙動は対象外。

## 役割

Docker entrypoint の GPU デバイス事前確認で、デバイスファイルを探すディレクトリを指定します。CUDA、HIP、SYCL backend のカードがコンテナ内から利用可能か、モデル準備に入る前に確認します。ソース全体で確認できるこの変数の参照は Docker entrypoint のチェックだけです。entrypoint は環境変数を明示的に加工して engine に渡しませんが、通常のプロセス環境として子プロセスに継承される可能性はあります。Strata の他のソースに、この変数を使う処理は見つかりませんでした。デバイスをマウントする機能でもありません。

## 値と判定

| 値 | 使用するディレクトリ |
|---|---|
| 未設定 | `/dev` |
| 空文字 | `/dev` |
| 空でない文字列 | その文字列をそのままディレクトリの接頭辞として使用 |

実装はシェルの `${STRATA_DEV_DIR:-/dev}` を使います。このため未設定と空文字は同じ扱いです。パスの存在確認や正規化、末尾 `/` の除去はせず、backend ごとのファイル検査に進みます。読み取りは通常起動時の GPU 確認箇所で一度行われます。

## 有効になる条件

entrypoint が通常の `run` / `serve` 起動経路を進み、`strata components engine --output json` の結果に `"usable": true` が含まれた後に適用されます。引数が `run` / `serve` 以外（例: `sh` や `strata ...`）の場合、entrypoint は先にコマンドを `exec` するため、この確認も変数の読み取りも行いません。engine が usable でない場合も、別のエラーを出して終了するので、この変数によるデバイス確認には進みません。

検査されるパスは backend ごとに固定です。

| backend | 確認するパス |
|---|---|
| `cuda` | `${STRATA_DEV_DIR:-/dev}/nvidia[0-9]*` に一致する項目、または `${STRATA_DEV_DIR:-/dev}/dxg` |
| `hip` | `${STRATA_DEV_DIR:-/dev}/kfd` |
| `sycl` | `${STRATA_DEV_DIR:-/dev}/dri/renderD*` に一致する項目 |

他の backend 名には `case` の検査分岐がないため、ここではデバイスパスを検査しません。

## 実行時の詳細

起動スクリプトは engine 情報から backend 名を取り出し、`dev="${STRATA_DEV_DIR:-/dev}"` として検査に使います。CUDA は `nvidia` に数字が続く名前の項目または `dxg` の存在、HIP は `kfd`、SYCL は `dri/renderD` 以下の項目を `ls` / `test -e` で確認します。変数の値そのものを `ls` に渡すのではなく、固定名をその下で探します。

対象が見つからない場合は stderr に backend に応じた `[X]` エラーを出し、entrypoint は終了コード `3` で終了します。CUDA のエラーは `--gpus all` を、HIP は `/dev/kfd` と `/dev/dri` の device 指定および group 指定を、SYCL は `/dev/dri` の device 指定を案内します。見つかった場合、この事前確認は通過し、その後の起動処理へ進みます。この確認はファイル名の存在を検査するもので、Strata がデバイスをマウントしたり、その後の engine 初期化成功まで保証したりするものではありません。

## 根拠

- `docker/entrypoint.sh:41-44` — `run` / `serve` 以外のコマンドを先に `exec` する分岐。
- `docker/entrypoint.sh:124-138` — engine の usable 判定と、失敗時の終了。
- `docker/entrypoint.sh:140-148` — backend の取得、既定値 `/dev`、各 backend のパス確認と失敗時のメッセージ・終了コード。
- `Dockerfile:97-108`、`docker/Dockerfile:87-89`、`docker/Dockerfile:133` — entrypoint が Strata Docker image に組み込まれて起動される設定。
- `docs/DOCKER.md:50-69, 237-244` — NVIDIA / AMD / Intel で渡すデバイスの説明。環境変数 `STRATA_DEV_DIR` 自体の説明ではなく、entrypoint のチェック対象となるデバイス指定との照合に参照。
