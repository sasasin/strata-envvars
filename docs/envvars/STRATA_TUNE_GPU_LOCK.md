# `STRATA_TUNE_GPU_LOCK`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`strata tune auto` と `strata presets recheck` が起動する各測定用 engine の実行中に保持するファイルロックのパスを指定します。複数のチューナーが同じ GPU を使うマシンで、同じロックファイルを指定すると測定 run を順番にできます。この変数は Strata のチューニング CLI が読みます。通常の推論起動には使われません。

## 値と判定

| 入力 | 動作 |
|---|---|
| 未設定 | `--gpu-lock` の既定値は `None`。ロックを作らず、通常どおり測定 run を行う |
| 環境変数が空文字 | 既定値は `""`。Python の偽値判定でロックを作らない |
| 環境変数に非空文字列を設定 | その文字列をロックファイルのパスとして使用する |
| `--gpu-lock PATH` を指定 | 環境変数にかかわらず CLI 引数の `PATH` を使用する |
| `--gpu-lock ""` を指定 | 空文字が優先され、ロックを作らない |

値は数値や真偽値として parse されず、trim・正規化もされません。相対パスは起動時の作業ディレクトリから解決されます。パスの親ディレクトリは必要に応じて作成され、ファイルは append モードで開かれます。

根拠: `strata_cli/tune_commands.py:39-40,85`, `strata_cli/tune_commands.py:132-136`, `strata_control/tune_session.py:196-207`。

## 有効になる条件

- `strata tune auto` の測定と `strata presets recheck` の再測定で使われます。各コマンドには環境変数を既定値とする `--gpu-lock` があり、CLI 引数が優先します。
- 対象処理で `_lock_factory()` が非空のパスを受け取った場合だけロックが有効です。変数が未設定または空文字の場合は無効です。
- `strata presets` の list/show/apply 等、通常の `serve.server` 起動、その他の実行経路はこの設定を参照しません。
- 同じパスを指定したプロセス間で協調する advisory lock です。異なるパスを指定したプロセスや、このファイルロックを使わないプロセスを制御する処理はありません。

根拠: `strata_cli/tune_commands.py:20-41,49-90,132-136,217-219,412-430`; CLI parser の登録は `strata_cli/cli.py:486-487`。

## 実行時の詳細

環境値は CLI parser の構築時に `os.environ.get()` で読み取られ、parse された引数の既定値になります。auto/recheck 処理はその値から `FileLock` factory を作り、`WorkerSession` に渡します。設定された場合、`WorkerSession.engine()` は engine worker の準備や起動より前にロックを取得し、測定用 engine の終了後に解放します。したがって、同じ Python CLI プロセスの実行中に環境変数を変更しても、既に parse された引数は変わりません。再評価用の static cache はありません。

Unix のメインスレッドでは `flock(LOCK_EX)` で待ち、その他の経路では 2 秒間隔でロックを再試行します。Windows は `msvcrt.locking` を使って再試行します。どの経路も既定の待ち上限は 5400 秒です。待機に入ると人間向け出力では `waiting for the lock <path>` が記録され、上限超過時は `TIMEOUT` の `StartFailed`（`the lock <path> was not free within 5400 s`）になります。auto の測定ではその失敗は run 結果に記録され、recheck では測定失敗として扱われ、保存済み設定を再調整する判定になります。JSON 出力時は CLI が進捗ログを stderr に出さないため、この待機メッセージは表示されません。

根拠: `strata_control/tune_session.py:199-210,212-258,260-273,443-450`; auto の失敗結果化は `strata_control/autotune.py:303-338`、recheck は `strata_control/autotune.py:907-923`。JSON モードのログ抑止は `strata_cli/tune_commands.py:178-179,205-208,427`。

## 根拠

- 変数を読む全箇所: `strata_cli/tune_commands.py:39,85`。リポジトリ全体の完全一致検索でもこの 2 箇所以外に参照はありません。
- 引数の優先順位とロック生成: `strata_cli/tune_commands.py:39-40,85,132-136`。
- auto/recheck から worker session への受け渡し: `strata_cli/tune_commands.py:217-219,412-430`。
- ロック取得タイミングと測定用 worker の実行: `strata_control/tune_session.py:443-479`。
- ファイルロックの OS 別実装、待機上限、ログと timeout: `strata_control/tune_session.py:196-273`。
- timeout の呼び出し側での扱い: `strata_control/autotune.py:322-338,907-923`。
