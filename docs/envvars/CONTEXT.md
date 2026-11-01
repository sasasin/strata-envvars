# `CONTEXT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

`CONTEXT` は Docker entrypoint が読み取る環境変数です。空でない値を `strata launch --context <値>` に渡し、起動時に使うコンテキスト長を指定します。Strata の C++/CUDA/HIP/SYCL engine や Python server が `CONTEXT` を直接読む箇所は確認できませんでした。値の解釈と検証は起動後の Strata CLI が行います。

## 値と判定

| 環境変数の状態 | entrypoint の処理 |
| --- | --- |
| 未設定 | `--context` を渡さない。 |
| 空文字 | 未設定と同じ。`[ -n "${CONTEXT:-}" ]` が偽になり、`--context` を渡さない。 |
| 非空文字列 | 内容を変換せず、1 個の引数として `--context` に渡す。entrypoint 自身は値域や形式を検証しない。 |

CLI の `--context` は `strata_cli.launch.cmd._context()` から `settings.parse_context()` に渡されます。パーサーは前後空白を除去し、小文字化した後、内部の空白・`_`・`,` を除去します。`数字`、`数字k`、`数字m` の形式（小数可。単位は大文字小文字を区別しない）を受け付け、k は 1024、m は 1024² 倍して token 数へ変換し、`round()` の後 `int` にします。変換結果が 1024 未満ならエラーです。負数、符号付き数、末尾に単位以外の文字がある値など、正規表現に合わない文字列もエラーです。ここには上限検査はなく、モデルや setup が後段で個別に検査します。

## 有効になる条件

- 値を使うのは Docker image の既定起動経路です。entrypoint は `launch --no-tui --access lan --port ...` を組み立て、`CONTEXT` が空でなければ `--context` を追加します。コンテナ内で別コマンド（例: `strata ...` や `sh`）を指定して entrypoint の server 起動経路を外れる場合、この転送は行われません。
- Compose の NVIDIA / AMD / Intel 設定は `${CONTEXT:-32k}` をコンテナ環境へ設定するため、ホスト側の `CONTEXT` が未設定または空なら `32k` が CLI に渡ります。直接 `docker run` する場合は Compose の既定値は適用されません。
- entrypoint は既定名 `docker` の保存 preset があれば `--preset docker` を常に付けます。非空の `CONTEXT` は preset 読み込み後に適用され、既存 preset の context を上書きします。未設定または空の場合、context は preset に保存済みならそれを使います。preset がなく context も指定されない場合、Strata CLI の通常の選択・既定処理になります。
- この値は Docker entrypoint の起動時に shell が評価します。Strata が `CONTEXT` をキャッシュしたり、server のリクエストごとに再読したりする処理ではありません。起動後に親環境を変更しても、すでに作られた CLI 引数は変わりません。

## 実行時の詳細

非空値は `--context` として Strata CLI の引数 parser に届きます。CLI は値を token 数へ変換し、指定された context を launch settings に入れます。モデル初期化では `strata_cli.launch.runner` が context を setup.py の `--context` として渡します。DeepSeek-V4.1-Flash 経路では setup が 8K〜1M の範囲を検査し、範囲外なら説明付きで失敗します。一般の CLI の parse 段階では 1024 token 未満や形式不正の値が argparse のエラーになります。Docker entrypoint は launch の非ゼロ終了を `strata launch stopped with code ...` として stderr に出し、同じコードでコンテナを終了します。

Strata の Docker 設定表は `CONTEXT` の目安として `32k`、`64k`、`128k`、`256k` または数値を記載し、既定を「収まる最大」と説明しています。一方、Compose ファイルは `32k` を明示的な既定値として設定します。直接の Docker 起動で値を省いた場合に preset がなければ、CLI の通常のモデル/context 推奨処理に委ねられるため、両者は起動方法ごとに区別が必要です。

## 根拠

- `docker/entrypoint.sh:1-3,53-56` は既定のコンテナ起動と、別コマンド実行時の分岐を示します。
- `docker/entrypoint.sh:169-174,189-195,242-249` は起動引数、空でない場合だけの `CONTEXT` 転送、preset の選択と保存を示します。
- `docker/entrypoint.sh:279-290` は組み立てた CLI を起動し、非ゼロ終了をログに出してコンテナを終了する経路です。
- `strata_cli/launch/cmd.py:48-52,94` と `strata_cli/launch/settings.py:65-75` は CLI の受け口、文字列形式、変換、最小値判定を示します。
- `strata_cli/launch/cmd.py:205-210,232-233` は preset を基礎に読み込み、明示的な context をその上に適用する順序を示します。
- `strata_cli/launch/runner.py:900-910` は設定された context を setup.py の `--context` へ転送します。
- `setup.py:8533-8537` は DeepSeek-V4.1-Flash の default と 8K〜1M の検証・警告を示します。
- `docker/compose/docker-compose.nvidia.yml:16-20`（AMD / Intel も各 compose ファイルの 18 行目）は Compose の `32k` 既定を示します。`docs/DOCKER.md:108-123,267-275` は Docker 設定の説明と旧 image からの対応を記載します。
- 候補一覧 `docs/envvars/000_envvers.md` にある名前について、Strata ソース全体を `CONTEXT` で検索した結果、実際の環境変数読み取りは `docker/entrypoint.sh:193` のみでした。その他のコード上の `CONTEXT` は context 概念や文字列の一部であり、環境変数の読み取りではありません。
