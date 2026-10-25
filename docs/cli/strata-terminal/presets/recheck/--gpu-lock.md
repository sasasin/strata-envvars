# `--gpu-lock`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| オプション | `--gpu-lock PATH` |
| 別名 | なし |
| 値 | ロックファイルのパス（文字列）。parser に型・書式・存在確認の指定はない |

## 役割

測定中に Strata の engine を起動する各区間で、指定ファイルに対する協調的な排他ロックを保持します。共有 GPU 環境で、同じロックファイルを使う Strata の他の調整処理と engine 実行を重ねないための指定です。GPU 自体を固定したり、ロックに参加しないプロセスを停止したりする機能ではありません。

## 使い方

```sh
strata presets recheck PRESET PROFILE --gpu-lock /var/lock/strata-gpu.lock
```

`PRESET` は保存済み preset、`PROFILE` はその preset が属する profile 名または run configuration（JSON）です。ユーザーが書き込み可能で、共有する実行同士が同一のパスを指定する場所を選びます。

## 値と既定値

- `--gpu-lock` は値を1つ取ります。値は `argparse` の通常の文字列で受理され、絶対パス・相対パス、ファイル名やディレクトリの書き込み可否を parser では検証しません。相対パスはプロセスの作業ディレクトリ基準で扱われます。
- 省略時は環境変数 `STRATA_TUNE_GPU_LOCK` の値が既定値になります。環境変数も未設定、または空文字列ならロックは作られません。明示した CLI 値は parser の値として環境変数の既定値を置き換えます。
- ロック取得の待ち時間は CLI から変更できず、実装上 5400 秒です。値の境界検査や複数回指定時の特別な処理はありません（同じ引数の反復は `argparse` の通常動作です）。

## 実行時の動作

`recheck` は保存済み設定で短い測定を行い、条件によってプロンプト速度の再測定や、engine 更新後の標準設定との比較測定も行います。`WorkerSession.engine` は各 engine 起動を開始する前にロックを取得し、engine セッションを抜けるときに解放します。したがってロックは recheck 全体や preset 読み書きの間ではなく、個々の engine 実行ごとに保持されます。

パスの親ディレクトリは必要なら作成され、ロックファイルは追記モードで開かれます。ファイル内容を書き換えたり、終了後にファイルを削除したりする処理はありません。POSIX のメインスレッドでは `flock` の排他ロックを使い、他の実行スレッドおよび Windows では2秒間隔の再試行を使います。Windows は `msvcrt` の1バイト範囲ロックです。ロックは advisory なので、同じパス・互換するロック方式で取得する処理だけが待ち合わせます。

## 適用条件と副作用

- `--gpu-lock` が空でない場合にだけ有効です。preset の状態確認や実行結果の記録自体はこのロックで保護されません。
- 値に対応する親ディレクトリがなければ作成し、ロックファイルがなければ空のファイルを作成します。ディレクトリ作成・ファイル作成・open に必要な権限が必要です。作成したファイルはロック解放後も残ります。
- ロックを使わない Strata 起動、別のロックファイルを使う処理、同じ advisory lock に参加しない GPU アプリケーションは排除しません。
- `strata tune auto` にも同名の `--gpu-lock` がありますが、別の parser スコープ・文書です。この文書の対象は `strata presets recheck` のみです。

## 出力とエラー

ロックが使用中なら待機し、通常の人向け出力では待ち始めた時点で stderr に `waiting for the lock PATH` を表示します。5400秒以内に解放されない場合、ロック取得処理は `TIMEOUT` の `StartFailed` になります。recheck はこれを測定失敗として扱い、`retune` 判定と理由を記録・出力しますが、preset を自動で再調整しません。この経路は通常の recheck 結果として返るため、コマンド自体は成功形式の出力（通常出力または `--output json`）を返します。

親ディレクトリ作成やファイル open などで `OSError` が起きた場合は preset コマンドのエラー処理に渡り、人向けでは stderr に `strata: ...`、JSON モードでは `ok: false` のエラー JSON を出して終了コード2になります。parser に値を渡さない場合は `argparse` が usage と引数不足エラーを表示します。

## 根拠

- `strata_cli/tune_commands.py:82`–`90` — `presets recheck` parser、位置引数およびオプション群。
- `strata_cli/tune_commands.py:132`–`136` — 値が空の場合はロックなし、非空の場合に `FileLock` を生成。
- `strata_cli/tune_commands.py:411`–`447` — preset と対象の読込、`WorkerSession` への lock 注入、測定結果・判定の保存と出力。
- `strata_cli/tune_commands.py:342`–`347` — `recheck` 分岐と `PresetError` / `OSError` / `ValueError` のエラー処理。
- `strata_control/tune_session.py:196`–`209` — ロックの既定待ち時間、親ディレクトリ作成、追記 open、OS別取得経路。
- `strata_control/tune_session.py:212`–`236` — POSIX メインスレッドの排他 `flock` と待機 timeout。
- `strata_control/tune_session.py:238`–`273` — polling 取得、Windows の `msvcrt`、解放とファイル close。
- `strata_control/tune_session.py:443`–`449` — 各 engine セッションの前にロックを取得。
- `strata_control/autotune.py:885`–`951` — recheck 中の測定回数・条件、`StartFailed` の測定結果化、`retune` / `keep` / `inconclusive` 判定。
- `strata_cli/tune_commands.py:39`–`40` — 同名オプションが `strata tune auto` にもあり、環境変数を既定値にする別スコープの定義。
