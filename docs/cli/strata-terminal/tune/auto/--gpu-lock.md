# `strata tune auto --gpu-lock`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--gpu-lock` |
| 別名 | なし |
| 値 | lock ファイルのパス文字列。型変換やパス形式の validation はない |

## 役割

共有マシンで複数の Strata tuning が同じ lock ファイルを使うよう指定し、各エンジン実行が重ならないようにします。ロックは tuning 全体ではなく、候補設定を測る個々のエンジン実行ごとに取得・解放されます。GPU を直接識別する値ではなく、同じファイルを使うプロセス間で協調する advisory lock です。

## 使い方

```sh
strata tune auto 'モデル名または設定' --gpu-lock /var/lock/strata-gpu.lock
```

`--gpu-lock` を指定しない場合は `STRATA_TUNE_GPU_LOCK` の値が使われます。既定値も環境変数もない場合、lock は使われません。

## 値と既定値

- `--gpu-lock` は値を 1 個取ります。`argparse` の文字列値として受理され、そのまま `FileLock` に渡されます。存在確認、絶対パスの要求、空白除去などの option 固有 validation はありません（`terminal/strata_cli/tune_commands.py:43-44,185-189`）。
- コマンドラインで省略したときの parser 既定値は `os.environ.get("STRATA_TUNE_GPU_LOCK")` です。したがって、CLI 引数を指定すると環境変数の値を上書きします（`terminal/strata_cli/tune_commands.py:43-44`）。
- 空文字列を明示するか、空の環境変数を使うと値は falsy となり、ロックなしになります（`terminal/strata_cli/tune_commands.py:185-187`）。同じ option を複数回渡した場合の専用処理はなく、通常の `argparse` の値保持に従います。

## 実行時の動作

通常実行では `_lock_factory` が値の有無を確認し、値があれば `FileLock` を生成する factory を `WorkerSession` に渡します。`WorkerSession.engine()` は各エンジン実行の開始時に lock context を取得し、実行 context を抜けると解放します（`terminal/strata_cli/tune_commands.py:185-189,371-376`; `terminal/strata_control/tune_session.py:527-533`）。

`FileLock` は親ディレクトリを作成し、指定ファイルを `a+` で開きます。POSIX のメインスレッドでは `fcntl.flock(LOCK_EX)`、それ以外の経路では非ブロッキング取得を繰り返し、Windows では `msvcrt.locking` を使います。ロックの既定待機上限は 5400 秒です。待機時は human 出力で stderr にロックパスを含むメッセージを出します（`terminal/strata_control/tune_session.py:215-229,231-277`）。

`--plan` は preview を出して `WorkerSession` を作る前に戻るため、このモードではロックファイルを開かず、取得も試みません（`terminal/strata_cli/tune_commands.py:349-353,355-376`）。

## 適用条件と副作用

- 共有する全プロセスが同じ lock ファイルパスを使う場合に、その間で排他が働きます。別パスを指定するプロセスやこの lock を使わないプロセスは調停されません。これは Strata のファイルロック実装から分かる範囲であり、GPU 単位の検出・ロックではありません（`terminal/strata_control/tune_session.py:215-229,241-248,257-277`）。
- 親ディレクトリがなければ作成され、lock ファイルがなければ `a+` で作成されます。lock ファイル自体は削除されません。取得した OS ロックは終了時に解除し、ファイルハンドルを閉じます（`terminal/strata_control/tune_session.py:224-229,279-293`）。
- POSIX のメインスレッドではカーネルの blocking lock、他の経路では最大 2 秒間隔の polling を使います。いずれも既定 5400 秒で timeout します（`terminal/strata_control/tune_session.py:231-277`）。
- `strata presets recheck` にも同じ option 名と環境変数既定値がありますが、別 parser / command scope です。この文書は索引に示された `strata tune auto` の scope のみを扱います（`terminal/strata_cli/tune_commands.py:88-96`）。

## 出力とエラー

ロック取得まで待つ場合、人向け進捗は stderr に出ます。ロックを 5400 秒以内に取得できないと `StartFailed("TIMEOUT", ...)` になります。tuner はこれを測定失敗として記録し、基準設定の測定に失敗した場合は `base_failed` / `start_failed` の結果になります。最終終了コードは通常 6 で、人向け結果は stdout に出力されます。JSON 出力では結果オブジェクトが stdout に出力されます（`terminal/strata_control/tune_session.py:250-252,271-277`; `terminal/strata_control/autotune.py:338-354,415-427`; `terminal/strata_cli/tune_commands.py:421-425`）。

指定パスの親ディレクトリ作成やファイル open が失敗した場合は `OSError` となります。option 用の事前エラー整形は確認できません（`terminal/strata_control/tune_session.py:224-229`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:21-50` — `strata tune auto` parser と `--gpu-lock` の環境変数既定値。
- `terminal/strata_cli/tune_commands.py:185-189,349-376` — 値がない場合の無効化、lock factory の生成、preview と通常実行の分岐、session への引き渡し。
- `terminal/strata_control/tune_session.py:215-293,527-533` — ファイル作成・OS 別排他 lock・待機上限・解除、および各エンジン実行での取得。
- `terminal/strata_control/autotune.py:338-354,403-427` — lock 取得失敗を測定結果に変換する処理と基準測定失敗の扱い。
- `terminal/strata_cli/tune_commands.py:421-425` — 最終結果の human / JSON 出力と終了コード。
