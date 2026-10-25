# `--gpu-lock`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、未コミット変更はありません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--gpu-lock PATH` |
| 別名 | なし |
| 値 | ロックファイルのパス（文字列） |

## 役割

各測定 engine の実行を、同じロックファイルを使う別プロセスと直列化するための任意のファイルロックです。共有 GPU 機などで複数の tuning / measurement が同時に engine を動かすのを避けたい場合に使用できます。これは協調的な advisory lock であり、ロックを使わない別プロセスの GPU 利用を防止するものではありません。

## 使い方

```sh
strata tune auto my-profile --gpu-lock /var/lock/strata-gpu.lock
```

`my-profile` は既存 profile 名、または調整対象の run configuration（JSON）です。`auto` は各構成を測定するため worker engine を起動します（`strata_cli/tune_commands.py:20-26,174-190`）。

## 値と既定値

- 値を1つ取ります。parser は `argparse` の文字列として受理し、パスの存在・書き込み権限などを事前検証しません（`strata_cli/tune_commands.py:39-40`）。
- 相対パスはプロセスの作業ディレクトリ基準です。ロック取得時に親ディレクトリを作成し、ファイルを `a+` で開くため、必要に応じて親ディレクトリとロックファイルが作成されます（`strata_control/tune_session.py:196-207`）。
- 省略時の既定値は環境変数 `STRATA_TUNE_GPU_LOCK` の値です。変数が未設定なら `None`、空文字列ならロックなしになります。明示値は argparse の値となり、環境変数の既定値を置き換えます（`strata_cli/tune_commands.py:39-40,132-136`）。環境変数の説明は [`STRATA_TUNE_GPU_LOCK`](../../../../STRATA_TUNE_GPU_LOCK.md) を参照してください。
- CLI 値の空文字列もロックを無効にします。`auto` parser では複数回指定時の特別な処理はなく、argparse の通常の単一値引数です。

## 実行時の動作

- `_lock_factory()` は `gpu_lock` が偽値なら lock を設定せず、値があればそのパスで `FileLock` を作ります（`strata_cli/tune_commands.py:132-136`）。
- `WorkerSession.engine()` は各 engine run ごとに lock を取得し、その後 `pre_start` の静穏・メモリ確認を行い、worker を起動して計測し、worker を停止してから lock を解放します。従って待ち時間だけでなく engine の起動・計測・停止中もロックを保持します（`strata_control/tune_session.py:443-450,477-509,511-522`）。
- Unix のメインスレッドでは `flock(LOCK_EX)` を使い、他の経路では2秒間隔の取得試行を行います。Windows では `msvcrt.locking` を使います。競合時は最初に `waiting for the lock <path>` を進捗ログへ出します（`strata_control/tune_session.py:205-210,212-258`）。
- 待機上限は実装既定の5400秒です。上限を超えると `StartFailed("TIMEOUT", ...)` となり、その run は `TIMEOUT` 結果として tuning に記録されます（`strata_control/tune_session.py:196-200,231-254`; `strata_control/autotune.py:322-337`）。この上限を変更する `--gpu-lock` の値形式はありません。
- `--no-quiet-check` は quiet check を無効にしますが、指定された lock 自体を無効にしません。lock は `WorkerSession.engine()` の入口で quiet check より先に取得されます（`strata_cli/tune_commands.py:41,194-197`; `strata_control/tune_session.py:443-450`）。

## 適用条件と副作用

- `--gpu-lock` または環境変数の値が空でない場合に有効です。lock は測定 run 単位で取得・解放され、preset 保存など tuning 全体の処理を囲むものではありません（`strata_control/tune_session.py:443-450`）。
- lock ファイルは `a+` で開かれ、ロック用の親ディレクトリも作られます。通常の計測ログや一時 run config とは別に、このパスへファイルシステムの副作用があります（`strata_control/tune_session.py:205-207,463-468`）。
- ファイルロックは同じファイルを開いて同じロック方式で協調するプロセス間でのみ機能します。Strata 外の engine 利用者がこの lock を取得しなければ、その実行は直列化されません。
- OS ごとのロック実装はソースで確認しましたが、全 OS・ファイルシステムでの advisory lock の互換性やネットワークファイルシステム上の挙動はこの調査では検証していません。

## 出力とエラー

- 競合で待つ場合、通常の進捗 callback を通じて lock パス付きの待機メッセージが出ます。`--output json` では人間向け進捗行は stderr に出さず、最後に JSON 結果を stdout に出します（`strata_cli/tune_commands.py:178-179,205-215,257-261`）。
- lock の待機 timeout は測定 run の失敗状態として扱われます。ファイルを開けない場合や親ディレクトリを作れない場合に対する専用の parser validation / lock-specific error message は確認できませんでした（`strata_control/tune_session.py:205-207`; `strata_control/autotune.py:322-328`）。そのような権限・パス異常の最終的な CLI 表示はソース上で確認できる範囲を超えるため、ここでは断定しません。

## 根拠

- `strata_cli/tune_commands.py:20-46` — `auto` parser、既定値、環境変数、他の関連オプション。
- `strata_cli/tune_commands.py:132-136,174-197,205-219,257-261` — lock factory、auto 実行への引き渡し、進捗・終了処理。
- `strata_control/tune_session.py:196-273,443-450` — lock ファイル作成、OS別排他取得・待機・解放、各 run の取得位置。
- `strata_control/tune_session.py:463-522` — worker 起動、計測、停止と run 終了までの lock 保持範囲。
- `strata_control/autotune.py:303-337` — run の失敗状態への変換と trial 記録。
- 索引上の scope: [`docs/cli/README.md`](../../../README.md) の `strata tune auto` 節では `strata-terminal/tune/auto/--gpu-lock.md` に掲載されています。
