# `STRATA_TUNE_GPU_LOCK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`strata tune auto` と `strata presets recheck` が各測定用エンジンを動かす間、指定ファイルの排他ロックを保持するためのパスです。複数の Strata チューナーが同じロックファイルを指定した場合、そのエンジン実行が重ならないようにします。`tune auto` の計画表示（`--plan`）はエンジンを起動せず、ロックも取得しません。Strata はこの値をエンジンの設定・子プロセス環境へ渡していません。CLI parser が環境変数を `--gpu-lock` の既定値として読み、共通セッションへロック生成関数を渡します（`terminal/strata_cli/tune_commands.py:21-45,88-96,185-189,349-376`）。

## 値と判定

| CLI 経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `strata tune auto` / `strata presets recheck` | argparse の既定値は `None`。ロックなし | 空でない文字列。値全体をファイルパスとして使う | 空文字列 `""` はロックなし |

Python の `os.environ.get` で文字列を取得し、数値変換、真偽文字列の解釈、trim、大文字小文字変換、パス形式の事前検証はしません。空白だけの値も空ではないためパスとして使われます。`--gpu-lock PATH` を明示すると環境変数由来の既定値より CLI 値が優先されます。`--gpu-lock ""` を渡した場合は `_lock_factory` の falsy 判定によりロックが無効になります。対象の parser 定義は `terminal/strata_cli/tune_commands.py:21-45,88-96`、無効判定は同 `:185-189` です。

## 有効になる条件

- `strata tune auto` では、対象や設定の検証が通り、`--plan` を指定せず実際の測定に進むことが必要です。計画表示は `auto` 内で `WorkerSession` を作る前に返ります（`terminal/strata_cli/tune_commands.py:349-376`）。
- `strata presets recheck` では、preset・対象設定・環境同一性の検証を通過して測定に進む必要があります（`terminal/strata_cli/tune_commands.py:615-645`）。
- どちらも `--gpu-lock` を省略したときは環境変数値が使われます。CLI オプションを指定した場合はその値が使われます（`terminal/strata_cli/tune_commands.py:43-45,91-96`）。
- OS によってロック実装が分かれます。Windows は `msvcrt.locking`、それ以外は `fcntl.flock` を使用します。待ち方は非 Windows のメインスレッドでは blocking flock、それ以外では polling です（`terminal/strata_control/tune_session.py:224-229,231-277,279-292`）。
- この設定名を読む箇所は Python CLI の上記 2 箇所だけです。ビルド macro、GPU backend、モデル状態、サーバー通常起動による別の読み取りや適用はありません。

## 実行時の詳細

環境変数は `add_tune_auto` / `add_presets` が argparse parser に引数を登録するときに一度読み、parser の default に保存します。実行中にプロセス環境を変更しても、その parser にすでに設定された既定値には反映されません。実際に測定を始める際 `_lock_factory` は `gpu_lock` が空かを調べ、空でなければ `FileLock` を返します（`terminal/strata_cli/tune_commands.py:21-45,55-96,185-189,375-376,643-644`）。

`WorkerSession.engine` は各エンジン実行の直前にロックを取得し、エンジン起動・測定・停止と後処理を終えて context を抜けるまで保持します。親ディレクトリを作成し、ロックファイルを append モードで開きます（`terminal/strata_control/tune_session.py:224-229,527-570,598-611`）。既定の待ち上限は 5400 秒です。競合時、人間向け出力では `waiting for the lock <path>` を stderr に出します。メインスレッドの POSIX 経路は上限到達で `StartFailed("TIMEOUT", "the lock <path> was not free within 5400 s")`、polling 経路も期限切れで同じ status/reason を返します（`terminal/strata_control/tune_session.py:218-218,231-277`）。JSON モードでは `say` がログを抑制します（`terminal/strata_cli/tune_commands.py:314-315,358-360,639`）。

`strata tune auto` では `StartFailed` は測定 trial の失敗 status と reason に記録され、最初の基準測定で発生した場合は「現在の設定を測定できない」結果になり、終了コードは通常の失敗値 `6` になります（`terminal/strata_control/autotune.py:338-354,415-427`; `terminal/strata_cli/tune_commands.py:392-425`）。`recheck` ではロック失敗が `retune` verdict の理由に入り、結果を保存したうえで表示します（`terminal/strata_control/autotune.py:959-975`; `terminal/strata_cli/tune_commands.py:652-661`）。ファイルの作成・オープン自体に失敗した場合は `OSError` となります。`presets recheck` は `presets_command` 内で捕捉して `strata: <理由>` を stderr に出し、`tune auto` は CLI 共通の `OSError` ハンドラに渡します（`terminal/strata_control/tune_session.py:224-229`; `terminal/strata_cli/tune_commands.py:472-531`; `terminal/strata_cli/cli.py:2194-2259`）。

## ログと測定値

ロック競合時の人間向けログは `waiting for the lock <path>`、取得できないまま 5400 秒に達した場合の理由は `the lock <path> was not free within 5400 s` です。前者は人間向けログ関数経由で stderr に出て、JSON モードでは抑制されます。測定値について、この変数による性能変化を Strata の資料で確認できませんでした（`terminal/strata_control/tune_session.py:218-277`; `terminal/strata_cli/tune_commands.py:358-360,639`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:21-45,88-96` — parser での環境変数読み取りと `--gpu-lock` の既定値。
- `terminal/strata_cli/tune_commands.py:185-189,349-376,615-645` — 空値の判定、`auto` / `recheck` のセッションへの引き渡し。
- `terminal/strata_control/tune_session.py:215-292,527-570,598-611` — ロック作成、OS 別取得・解放、測定実行中の保持。
- `terminal/strata_control/autotune.py:338-354,415-427,959-975` — timeout を含むロック失敗の結果への反映。
- `terminal/strata_cli/tune_commands.py:358-360,392-425,639,652-661,472-531`; `terminal/strata_cli/cli.py:2194-2259` — ログ抑制、コマンド結果、失敗出力。
