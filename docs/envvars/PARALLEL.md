# `PARALLEL`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`PARALLEL` は Strata の Docker entrypoint が読むコンテナ設定で、同時に decode するリクエスト数を `strata launch --parallel N` に渡す。Strata の engine や server がこの環境変数名を直接読むわけではない。Compose の NVIDIA / AMD / Intel 定義はホスト側の `PARALLEL` をコンテナへ渡し、entrypoint が CLI 引数へ変換する（`docker/compose/docker-compose.nvidia.yml:16-21`、`docker/compose/docker-compose.amd.yml:15-20`、`docker/compose/docker-compose.intel.yml:15-20`、`docker/entrypoint.sh:165-190`）。

設定された `2..8` は launcher の preset に parallel 数を保存し、server が engine 起動引数 `--batch N` に変換する。複数リクエストが batch slots で同時に decode され、空き slot がなければ他のリクエストは待つ（`strata_cli/launch/cmd.py:63-70,97`、`strata_cli/launch/runner.py:1797-1818`、`serve/server.py:3983-4010`）。`1` は serial のままで、同時 decode を有効にしない（`serve/server.py:3995-4003`）。

## 値と判定

| 条件 | unset / 空文字 | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Docker entrypoint 経由 | entrypoint は `--parallel` を付けない。preset に保存済みの値があればそれが使われ、値がなければ launcher のカード適合値を使う | 文字列をそのまま CLI に渡し、launcher が Python `int()` で変換した結果が `1..8` なら受理。`1` は serial、`2..8` は slots 数 | 小文字の `auto` だけは entrypoint が引数を付けずに省略扱いにする。その他の文字列は launcher が整数変換し、整数化後 `1..8` の範囲検査を通らなければ CLI エラー |

entrypoint は値の空判定に shell の `-n` を使い、値が空でなく、かつ大文字小文字を区別した完全一致で `auto` でないときだけ `--parallel "$PARALLEL"` を追加する。したがって `PARALLEL=''` と未設定は同じ分岐、`PARALLEL=auto` は省略、`PARALLEL=AUTO` は整数変換エラーになる（`docker/entrypoint.sh:190`）。値を trim・小文字化・数値化するのはこの shell ではなく launcher の `_parallel()` であり、Python `int()` が受理する整数表記を `1..8` に制限する。例として `2`、`+2`、`02`、前後に空白のある ` 2 ` は受理され、`0`、`9`、`2.0`、`true` は拒否される（`strata_cli/launch/cmd.py:63-70,97`）。

## 有効になる条件

- この環境変数を読むのは Docker entrypoint 経由の起動だけ。Compose 定義は `PARALLEL` をコンテナへ渡すが、Docker を介さずに `strata launch` を実行した場合、この名前を読む箇所はない（`docker/compose/docker-compose.nvidia.yml:16-21`、`docker/compose/docker-compose.amd.yml:15-20`、`docker/compose/docker-compose.intel.yml:15-20`、`docker/entrypoint.sh:190`）。
- `unset` / 空文字 / `auto` のときは `--preset docker` を使って既存 preset を読み込む。preset に前回の parallel 値があれば保持されるため、自動フィットへ戻す指定ではない。値のない新規 preset では launcher が使用可能な GPU の VRAM から値を選び、使用可能 GPU がない場合はこの parallel override を作らない（`docker/entrypoint.sh:239-247`、`strata_cli/launch/cmd.py:206-212`、`strata_cli/launch/runner.py:1797-1805,1837-1841`）。
- 自動フィットの目安は VRAM 32 GB 以上で 4、24 GB 以上で 3、20 GB 以上で 2、それ未満で 1。閾値判定には 0.5 GB の余裕があり、明示値を制限する clamp ではない（`strata_cli/launch/settings.py:36-46`）。
- 明示値がカードの推奨数を上回っても起動は拒否されず、launcher は警告を出す。GPU 構成やモデルが変わって値が収まらない場合は engine 起動失敗の可能性があり、`PARALLEL` 自体が VRAM を確保したり実行可能性を保証したりはしない（`strata_cli/launch/settings.py:199-212`）。
- engine の設定 `args` に `--batch` または `--slots` が既にあれば server は parallel config から追加の `--batch` を作らない。all-cards split engine では launcher が parallel 値を lane 数として扱い、profile との競合を避ける（`serve/server.py:3983-3992`、`strata_cli/launch/runner.py:1737-1755,1803-1805`）。
- `STRATA_PARALLEL_SOLO=0` は slot cache があるときに、単独になった request を solo path へ戻さない条件として server が別途読む。これは slot 数を選ぶ `PARALLEL` の値を変更しない（`serve/server.py:2134-2142`）。

## 実行時の詳細

Compose が環境値を渡し、entrypoint がコンテナ起動のたびに値を評価して `strata launch --no-tui ... --preset docker` の引数を組み立てる。`PARALLEL` が `auto` 以外の非空値なら `--parallel` が preset より優先される CLI 設定となり、他の設定とともに preset を保存する。未設定・空・`auto` では引数がなく、preset に保存された値は `settings_from_args()` が読み込んで維持する（`docker/entrypoint.sh:165-190,239-247`、`strata_cli/launch/cmd.py:206-212,237-244`）。

launcher は明示値を profile の `parallel` override として設定する。省略時は、既存 preset が持つ値を使うか、新規起動なら利用可能な GPU の VRAM に基づく値を profile に設定する（`strata_cli/launch/runner.py:1797-1818,1837-1841`）。server は起動時に profile override を runtime config に適用し、`parallel_args()` が `2` 以上を engine の `--batch N` に変換する。`1` または未設定は追加引数なしで serial のまま。リクエストが slots 数を超えたとき、空きができるまで待つ構成になる（`strata_control/calibration.py:125-139`、`serve/server.py:3983-4010`）。環境変数は起動時の shell が読むため、起動後に環境値を変更しても稼働中 server の設定には反映されない。

## ログと測定値

無効な値は `strata launch` の argparse エラーになる。整数でない場合の実装文言は `'<value>' is not a number of requests. Use 1 to 8, or leave it out to fit your card.`、範囲外の場合は `<n> requests at once is outside what the engine can do. Use 1 to 8.`。entrypoint は起動コマンドの非ゼロ終了を検出すると phase を failed にし、`strata launch stopped with code <rc> (the lines above say why). The container ends. Fix that and start it again: finished steps are not repeated, and an interrupted download continues where it stopped.` と出す（`strata_cli/launch/cmd.py:63-70`、`docker/entrypoint.sh:281-288`）。

明示値がカードの推奨値を超えると、launcher は `<n> requests at once is more than a <vram> GB card usually holds (it fits <fitted>).` と警告し、「It can still start; the engine keeps less of the model in graphics memory, so each answer is slower.」と続ける（`strata_cli/launch/settings.py:199-212`）。この文書では `PARALLEL` の値に対する性能測定値は記載しない。Docker 変数の説明にあたる `docs/DETAILS.md` の `parallel` 行は config の既定 `1` と batch slots の役割を記載し、Docker 向けの値域と既定説明は `docs/DOCKER.md` にある（`docs/DETAILS.md:503`、`docs/DOCKER.md:113-121`）。

## 根拠

- `docker/entrypoint.sh:15-16,165-190,239-247,249-288`
- `docker/compose/docker-compose.nvidia.yml:16-21`; `docker/compose/docker-compose.amd.yml:15-20`; `docker/compose/docker-compose.intel.yml:15-20`
- `strata_cli/launch/cmd.py:63-70,97,206-212,237-244`
- `strata_cli/launch/settings.py:36-46,199-212`
- `strata_cli/launch/runner.py:1737-1755,1797-1818,1837-1841`
- `strata_control/calibration.py:125-139`
- `serve/server.py:2134-2142,3983-4010`
- `docs/DETAILS.md:503`; `docs/DOCKER.md:113-121`
