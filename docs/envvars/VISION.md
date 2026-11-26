# `VISION`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata Docker イメージの通常起動で、写真入力の設定を選びます。entrypoint はこの値を `strata launch --vision` の引数へ変換します。`VISION` 自体は Strata の Python 起動処理やエンジンで直接読み直されず、モデル設定を通じて起動設定へ反映されます（`tools/docker/entrypoint.sh:184-225`、`terminal/strata_cli/launch/cmd.py:93-96,215-220,250-251`）。

Compose の NVIDIA / AMD / Intel 定義では `${VISION:-off}` をコンテナに渡すため、ホスト側の値が未設定または空なら `off` です。一方、Compose を使わずコンテナへ `VISION` を渡さない場合は entrypoint が `--vision` を付けず、写真設定は既存 preset の値、またはモデル・エンジンに応じた Strata の既定判定になります（`tools/docker/compose/docker-compose.nvidia.yml:16-23`、`tools/docker/compose/docker-compose.amd.yml:16-22`、`tools/docker/compose/docker-compose.intel.yml:15-22`、`tools/docker/entrypoint.sh:219-225,268-275`、`terminal/strata_cli/launch/settings.py:135`）。

## 値と判定

Docker entrypoint は値が空でない場合だけ処理します。`tr 'A-Z' 'a-z'` で ASCII 大文字を小文字にし、前後の空白は除去せず、変換後の文字列全体を `case` で照合します（`tools/docker/entrypoint.sh:219-224`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Compose の各 backend 定義 | ホスト側が unset または空なら `off` がコンテナに設定される | `off`, `no`, `false`, `0` → `off`; `on`, `yes`, `true`, `1` → `on`; `gpu` → `gpu`; `cpu` → `cpu` | 上記以外は entrypoint がエラー終了 |
| Compose を介さない Docker 通常起動 | unset または空文字なら `--vision` を渡さず、既存 preset の設定を保つ。初回など preset に値がなければ Strata がモデル・エンジンから既定値を決める | 大文字小文字を問わず上記と同じ。大文字は小文字化される | ` ON `、`0anything`、`false ` など空白を含む値・追加文字列は一致せずエラー |

Compose 定義がない起動経路で環境変数を直接読んだときの `VISION` による数値変換はありません。たとえば `VISION=0` は文字列一致で `off`、`VISION=0anything` は無効です。entrypoint のエラー文は `[X] VISION=<入力値> is not one of off, on, gpu, cpu.` で、終了コードは `2` です（`tools/docker/entrypoint.sh:54,219-224`）。

## 有効になる条件

- この読み取りは Docker entrypoint の通常起動経路に限られます。`docker run image strata ...` や `docker run image sh` のように別コマンドを指定すると、entrypoint は設定処理より先にコマンドを `exec` するため `VISION` を変換しません（`tools/docker/entrypoint.sh:5-7,68-70`）。
- 値が空でない通常起動では `--vision` が設定され、CLI は preset を読み込んだ後に指定フラグの値で `s.vision` を上書きします。従って環境変数からの設定は保存済み preset の写真設定より優先されます（`tools/docker/entrypoint.sh:219-225,268-275`、`terminal/strata_cli/launch/cmd.py:215-220,250-251`）。
- Compose は既定の `off` も明示的に渡すので、通常の Compose 起動では preset に写真設定があっても `off` が上書き値になります。Compose 外で `VISION` を unset / 空にした場合は上書きフラグがなく、preset があればその設定が残ります（`tools/docker/compose/docker-compose.nvidia.yml:22`、`tools/docker/entrypoint.sh:219-225,268-275`）。
- 選択モデルが画像入力を扱えないと Strata launch は警告 `"<モデル名> cannot read pictures yet, so pictures are off."` を追加し、実効設定を `off` にします（`terminal/strata_cli/launch/cmd.py:368-400`）。モデルやエンジンに写真リーダーがない場合、設定未指定時の既定判定は `off` になり、その一部では `The engine installed here has no picture reader, so pictures are off.` と理由を通知します（`terminal/strata_cli/launch/cmd.py:396-400`、`terminal/strata_cli/launch/catalog.py:662-692`）。
- `on` は Strata launch 内で setup に渡す `yes` へ変換されます。`gpu` / `cpu` は選択を保持して渡されます。実際の読取方式は Strata の reader/model 判定と setup に委ねられ、環境変数が単独で GPU backend や reader の有無を変更するわけではありません（`terminal/strata_cli/launch/runner.py:1313-1331,1351-1363`）。

## 実行時の詳細

entrypoint はコンテナ起動ごとに現在の `VISION` を評価し、値があれば launch 引数を構築します。環境変数値を `VISION` 用に static cache する処理はなく、起動後の環境変更を再読するループもありません（`tools/docker/entrypoint.sh:219-225,297-310`）。Compose はホスト側からコンテナ環境へ値を設定します（`tools/docker/compose/docker-compose.nvidia.yml:16-23`ほか）。

設定値があると `have=1` となり、preset が存在すれば `--preset <名前> --save-preset <名前>`、なければ `--save-preset <名前>` が起動引数に加わります。よって `VISION` 由来の選択はその起動で使われ、通常起動では同じ名前の preset に保存されます（`tools/docker/entrypoint.sh:219-225,268-275`）。launch のモデル設定では画像非対応モデルに対する前述の警告・`off` 化が行われます。setup 用引数では `off` は `no`、`on` は `yes` に変換されます（`terminal/strata_cli/launch/cmd.py:393-400`、`terminal/strata_cli/launch/runner.py:1322-1331,1351-1363`）。

## ログと測定値

無効な値では entrypoint が stderr に `[X] VISION=<入力値> is not one of off, on, gpu, cpu.` を出してコード `2` で終了します（`tools/docker/entrypoint.sh:54,219-224`）。対応しないモデルで写真を要求した場合の警告と設定変更は「有効になる条件」に記したとおりです（`terminal/strata_cli/launch/cmd.py:393-400`）。この変数による測定値は該当なしです。

## 根拠

- 候補一覧の `VISION` は Docker 起動処理で実読取される環境変数です。全参照のうち、Compose 定義は値の転送、entrypoint の行 16 は説明コメント、行 219-224 が読み取り・検証・CLI 引数化です（`tools/docker/compose/docker-compose.*.yml:21-22`、`tools/docker/entrypoint.sh:16,219-225`）。
- CLI の有効値、preset 読み込み後の上書き、モデル非対応時の警告と fallback（`terminal/strata_cli/launch/cmd.py:93-96,215-220,250-251,393-400`）。
- 画像設定の未指定状態、setup 引数への変換、モデルおよび reader 状態を使う既定値（`terminal/strata_cli/launch/settings.py:135`、`terminal/strata_cli/launch/runner.py:1313-1363`、`terminal/strata_cli/launch/catalog.py:662-692`）。
