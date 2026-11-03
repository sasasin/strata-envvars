# `PARALLEL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`PARALLEL` は Strata の Docker entrypoint が読み取るコンテナ設定です。空でなければ `strata launch --parallel N` に渡し、同時に応答を進めるリクエスト数を設定します。engine 起動後にこの環境変数を読むのではなく、launch が選んだ値を実行設定・server profile に記録し、server が engine の `--batch` または DeepSeek 用 `--parallel` 引数へ変換します（`docker/entrypoint.sh:169-195,243-248,274-285`; `strata_cli/launch/cmd.py:212-217,239-246`; `strata_cli/launch/runner.py:1737-1760`; `serve/server.py:3563-3565,3581-3626`）。

この環境変数を明示的に読む箇所は `docker/entrypoint.sh:194` です。Compose の NVIDIA/AMD/Intel 定義はホスト側の値をコンテナ内へ渡します（`docker/compose/docker-compose.nvidia.yml:16-21`, `docker/compose/docker-compose.amd.yml:15-20`, `docker/compose/docker-compose.intel.yml:15-20`）。通常の `strata` CLI や `serve/server.py` は `PARALLEL` を直接参照しません。`serve/server.py` にある `STRATA_PARALLEL_SOLO` などは別の変数です。

## 値と判定

| コンテナ内の値 | entrypoint の処理 | 結果 |
|---|---|---|
| 未設定または空文字 | `-n "${PARALLEL:-}"` が偽 | `--parallel` を付けずに起動。指定済みプリセット値があれば読み込み、なければモデル・カードに応じた既定処理へ進む |
| 文字列 `auto`（小文字、完全一致） | 空でなくても第2条件が偽 | `--parallel` を付けず、上と同じ既定処理へ進む |
| その他 | 値をそのまま `--parallel "$PARALLEL"` として追加 | `strata launch` の整数・範囲検証に渡す |

entrypoint は `auto` 以外の大文字小文字変換や前後空白の除去をしません（`docker/entrypoint.sh:194`）。launch 側は Python `int()` で整数化し、1〜8 の範囲に限ります。したがって `1`〜`8` は有効、`0`・負数・`9` 以上は範囲外、数値でない値（例: `true`, `AUTO`, `2x`）は数値エラーです。`int()` が受け入れる整数表記は通ります。空文字は launch に渡らないため、値エラーにはなりません（`strata_cli/launch/cmd.py:65-72,100`）。無効値は launch の引数検証でエラーとなり起動しません。Docker entrypoint は launch の非 0 終了を `strata launch stopped with code ...` と stderr に出し、コンテナを終了します（`docker/entrypoint.sh:285-292`）。

## 有効になる条件

- **Docker 経由**: entrypoint が通常のコンテナ起動経路（引数なし、`run`、`serve`）で実行される場合に設定を変換します。`docker run IMAGE strata ...` や `docker run IMAGE sh` のような別コマンドは早期に `exec` され、`PARALLEL` を `launch` 引数へ変換しません（`docker/entrypoint.sh:53-56`）。Compose は NVIDIA、AMD、Intel の各定義で値を転送します（上記 compose 行）。
- **既存プリセット**: `settings_from_args()` は先に指定プリセットを読み、CLI フラグがあればその上に適用します。entrypoint が値を `--parallel` に変換した場合はプリセットの値を上書きし、設定があるとプリセットを保存します。空／未設定／`auto` の場合は `--parallel` を渡さず、保存済み設定をそのまま使います（`docker/entrypoint.sh:190-195,243-248`; `strata_cli/launch/cmd.py:212-217,245-246`）。
- **モデルとカード**: 明示値のない通常モデルでは launch の既定はカードの VRAM に合わせて fit されます。実装上の目安は 20 GB 未満で 1、20 GB から 2、24 GB から 3、32 GB から 4（境界比較には 0.5 GB の許容差）です。利用可能 GPU がない場合など fit を決められなければ `None` です。DeepSeek-V4.1-Flash はこの fit を使わず、明示指定がなければ一度に 1 件ずつです（`strata_cli/launch/settings.py:65-75,125`; `strata_cli/launch/runner.py:1786-1793`）。
- **既存 engine 設定**: 通常 engine の config に既に `--batch` / `--slots` があると server は `parallel` を重ねません。all-cards split engine は例外で、`--batch` の値を 1〜8 の lane 数として更新します（`serve/server.py:3574-3593`）。

## 実行時の詳細

entrypoint はコンテナ起動時に値を一度シェル展開し、`strata launch` の引数へ渡します。プロセス起動後の環境変数変更を再読込する処理はありません。Compose では `${PARALLEL:-}` をコンテナ環境へ渡しますが、デフォルト値は空です（`docker/entrypoint.sh:194,274-285`; `docker/compose/docker-compose.nvidia.yml:20`, `docker/compose/docker-compose.amd.yml:19`, `docker/compose/docker-compose.intel.yml:19`）。

launch は `--parallel` をプリセット上の parallel 値に反映し、GPU やモデルの設定とともに実行 config を作ります。`1` は有効な明示値ですが、一件ずつの動作なので server は追加の並列 engine 引数を生成しません（`strata_cli/launch/cmd.py:65-72,245-246`; `serve/server.py:3581-3602`）。2〜8 は通常モデルで `--batch N`、DeepSeek では `--parallel N` として engine に渡されます。DeepSeek の旧 engine がその引数を受け付けないと判定された場合は渡さず、一件ずつになる旨の `[strata]` メッセージを出します（`serve/server.py:3603-3619`）。

通常モデルの明示値が 8 を超えることは Docker entrypoint 経由では launch の 1〜8 検証で拒否されます。server 側の `parallel_args()` には別経路で大きな設定値を受けた場合の上限通知や split engine 用処理もありますが、Docker の `PARALLEL` からその値域には到達しません（`strata_cli/launch/cmd.py:65-72`; `serve/server.py:3616-3626`）。

## 根拠

- Docker での読み取りと引数への変換: `docker/entrypoint.sh:9-16,169-195`
- Compose からコンテナへの受け渡し: `docker/compose/docker-compose.nvidia.yml:16-21`, `docker/compose/docker-compose.amd.yml:15-20`, `docker/compose/docker-compose.intel.yml:15-20`
- launch 引数の parse、プリセットとの優先順位: `strata_cli/launch/cmd.py:65-72,100,212-217,239-246`
- プリセット／profile への保存とカード fit、DeepSeek の既定: `strata_cli/launch/runner.py:1737-1760,1786-1793`; `strata_cli/launch/settings.py:65-75,125`
- server から engine 引数への反映と既存 batch 設定との関係: `serve/server.py:3563-3565,3574-3626`
- Docker 起動失敗の観測経路: `docker/entrypoint.sh:285-292`
