# `--gpu-lock`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。調査時の作業状態: `## main...origin/main`（変更なし）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| オプション | `--gpu-lock` |
| 別名 | なし |
| 値 | lock ファイルのパス（文字列） |

## 役割

再チェック中に起動する各 engine の実行を、指定ファイルの排他 lock で直列化します。共有 GPU 機で、同じ lock ファイルを使う別プロセスと engine 実行の重なりを避けたい場合に使います。GPU デバイスの指定や予約そのものを行うオプションではありません。`strata tune auto` にも同じ表記の別 parser がありますが、この文書の対象は `strata presets recheck` です（parser: `terminal/strata_cli/tune_commands.py:21-45,55-96`）。

## 使い方

```sh
# 再チェック中の engine 実行を /tmp/strata-gpu.lock で共有ロックする
strata presets recheck <preset> <profile-or-config.json> --gpu-lock /tmp/strata-gpu.lock
```

`<preset>` と `<profile-or-config.json>` は実際の preset 識別子と、preset が属する profile 名または run configuration に置き換えます。コマンドと位置引数の登録は `terminal/strata_cli/tune_commands.py:88-96` にあります。

## 値と既定値

- 値は必須のパス文字列です。parser に `type`、選択肢、存在確認などの値検証はありません。パスは `FileLock` にそのまま渡されます（`terminal/strata_cli/tune_commands.py:88-96,185-189`）。
- 省略時は環境変数 `STRATA_TUNE_GPU_LOCK` の値が既定値になります。環境変数が未設定なら `None` となり lock は使いません。明示した CLI 値は parser の既定値を置き換えます（`terminal/strata_cli/tune_commands.py:91,185-189`）。
- CLI または環境変数の値が空文字列なら `_lock_factory` の falsy 判定で lock は無効になります。相対パスを絶対化する処理はなく、実行プロセスの作業ディレクトリから解決されます（`terminal/strata_cli/tune_commands.py:185-189`）。
- `STRATA_TUNE_GPU_LOCK` は `strata tune auto` 側の parser にも設定されていますが、別コマンドの scope です。この文書では環境変数の全仕様は扱いません（`terminal/strata_cli/tune_commands.py:43-45,88-96`）。

## 実行時の動作

`_recheck` は値から lock factory を作り、`WorkerSession` に渡します。各 engine 実行の開始時に lock を取得し、worker/engine の開始と測定、停止処理を含む `engine` コンテキストが終わるまで保持します。再チェックが複数回 engine を起動する場合は、その各実行で個別に取得します（`terminal/strata_cli/tune_commands.py:643-645`; `terminal/strata_control/tune_session.py:527-534,594-611`）。

`FileLock` は親ディレクトリを作成し、指定ファイルを追記モードで開いて OS の排他 advisory lock を取得します。ファイル自体は lock 解放時に削除されません。Unix 系では main thread からは最初に非ブロッキング取得を試し、競合時は blocking lock を待ちます。それ以外の経路と Windows では非ブロッキング取得を最大 2 秒間隔で繰り返します。待機上限は 5400 秒です（`terminal/strata_control/tune_session.py:215-229,231-277,279-292`）。

## 適用条件と副作用

- 同一の lock ファイルを使い、互換する OS lock を取得するプロセス間でのみ競合が調停されます。オプションを省略し、環境変数も設定しなければ、この調停はありません（`terminal/strata_cli/tune_commands.py:185-189`; `terminal/strata_control/tune_session.py:215-229`）。
- lock ファイルの親ディレクトリがなければ作成し、lock ファイルを追記モードで開きます。親ディレクトリ作成やファイル open の失敗は `OSError` となり、CLI の失敗経路へ進みます（`terminal/strata_control/tune_session.py:224-229`; `terminal/strata_cli/tune_commands.py:527-530`）。
- lock 取得待ちが 5400 秒を超えると `StartFailed`（`TIMEOUT`）になります。再チェック側はこれを測定失敗として扱い、再チェック結果を `retune` として記録して通常の結果出力へ進みます（`terminal/strata_control/tune_session.py:231-252,257-277`; `terminal/strata_control/autotune.py:959-975`; `terminal/strata_cli/tune_commands.py:652-661`）。
- 人間向け実行では競合 lock 待ちを stderr に通知します。`--output json` ではログ出力関数が無効になり、JSON 結果が stdout に出ます（`terminal/strata_cli/tune_commands.py:639,643-650`; `terminal/strata_control/tune_session.py:243-245,271-277`）。

## 根拠

- `terminal/strata_cli/cli.py:514-515` — Terminal CLI に tuning と presets の parser を登録。
- `terminal/strata_cli/tune_commands.py:88-96` — `strata presets recheck` の parser、位置引数、`--gpu-lock` の環境変数既定値。
- `terminal/strata_cli/tune_commands.py:185-189,615-645` — 空値での無効化、FileLock factory、recheck から `WorkerSession` への lock 渡し。
- `terminal/strata_control/tune_session.py:215-292,527-534` — ファイル lock の取得・待機・解放、および各 engine run での適用範囲。
- `terminal/strata_control/autotune.py:959-975` — lock timeout を含む `StartFailed` を recheck 結果へ変換する処理。
- `terminal/strata_cli/tune_commands.py:527-530,652-661` — OS エラーの CLI 失敗処理、結果記録と出力。
