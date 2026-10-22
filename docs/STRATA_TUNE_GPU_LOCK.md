# `STRATA_TUNE_GPU_LOCK`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

`strata tune auto` と `strata presets recheck` が起動する測定用 engine worker の実行を、指定したファイルの排他 advisory lock で直列化します。同じロックファイルを使う別のチューナーと測定の同時実行を避ける用途です。推論 engine 自体の設定値ではありません。

## 値と判定

環境変数の文字列を数値や真偽値に変換せず、`--gpu-lock` の既定パスとして使います。

| 入力 | 挙動 |
|---|---|
| 未設定 | argparse の値は `None`。ロックを作らず、測定 worker はこのロック機構を使わない |
| 空文字 | 値は `""`。`_lock_factory()` の偽値判定でロックを作らない |
| 空でない文字列 | その文字列をロックファイルのパスとして使う |
| `--gpu-lock PATH` を指定 | 環境変数の既定値を CLI の値で置き換える |
| `--gpu-lock ""` を指定 | 環境変数に値があっても空文字が渡り、ロックを作らない |

パスの妥当性確認や正規化、範囲指定はありません。相対パスはプロセスの作業ディレクトリ基準です。

## 有効になる条件

この変数を読むのは Strata の Python CLI です。`tune auto` と `presets recheck` の各 `--gpu-lock` オプションの argparse 既定値に使われます。他のサブコマンドでは読みません。環境変数を engine worker に転送して engine 側で解釈する処理もありません。

## 実行時の詳細

パスが truthy なら `_lock_factory()` が `FileLock` を返し、`WorkerSession.engine()` は各測定 worker の起動前に lock context に入ります。ロックは worker の起動、準備完了待ち、測定、終了処理まで保持され、その context を抜けると解放されます。親ディレクトリを作成し、ロックファイルを append モードで開きます。

Unix のメインスレッドでは `fcntl.flock(LOCK_EX)` で待ち、その他の経路では 2 秒間隔で排他ロックを試します。Windows は `msvcrt.locking()` を使います。既定の待機上限は 5400 秒です。競合すると stderr 側のログ関数に `waiting for the lock <path>` を一度出し、上限を過ぎると `StartFailed`（`TIMEOUT`）になります。Unix のメインスレッド経路では signal timer、それ以外の経路では期限を繰り返し確認します。

値は CLI の引数解析時に環境から取得されます。プロセス実行中に環境変数を変えても、既に解析済みの引数は変わりません。

## 文書との照合

`docs/DETAILS.md` にこの変数または `--gpu-lock` の説明は見つかりませんでした。ここでは測定値や性能上の効果は述べず、実装から確認できる排他と待機の挙動のみを記載しています。

## 根拠

- `strata_cli/tune_commands.py:20-40,82-90`: `tune auto` と `presets recheck` の CLI オプションと環境変数既定値。
- `strata_cli/tune_commands.py:132-136,174-219,411-429`: 空値の扱い、`FileLock` の選択、両コマンドから worker session への受け渡し。
- `strata_control/tune_session.py:196-210,212-258,260-270`: ファイル作成、OS ごとの排他ロック、待機、timeout、解放。
- `strata_control/tune_session.py:443-460,477-510,510-520`: 各 engine worker の開始前に lock を取得し、worker 終了時に context を抜ける処理。
