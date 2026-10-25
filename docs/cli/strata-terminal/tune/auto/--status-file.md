# `--status-file`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--status-file` |
| 別名 | なし |
| 値 | JSON の進捗状態を書き込むファイルパス（文字列） |

## 役割

チューニングの進捗と完了結果を JSON ファイルに出力します。デスクトップアプリが別プロセスから進捗を読む用途を含みます。省略時はファイル出力を行いません。この値自体はチューニング設定や測定内容を変えません。

## 使い方

```sh
strata tune auto my-profile --status-file /tmp/strata-tune-status.json
```

`my-profile` は保存済みプロファイル名、または run configuration の JSON ファイルです。`strata tune auto` はその設定を測定し、結果に応じてプリセットを保存するコマンドです（`strata_cli/tune_commands.py:20-25, 174-181`）。

## 値と既定値

- parser は値を取る引数として登録し、型変換・`choices`・パス検査を指定していません。既定値は `None` です（`strata_cli/tune_commands.py:44`）。
- 値はファイルパスとして扱われます。相対パスを絶対化する処理はなく、通常のプロセス作業ディレクトリからの相対パスです（`strata_cli/tune_commands.py:149-155`）。
- 空文字列は parser では拒否されませんが、書込 helper が falsy なパスを無視するため、ファイルは作成・更新されません（`strata_cli/tune_commands.py:149-152`）。
- 重複指定時の parser 上の特別処理はありません。`argparse` の通常の単一値引数として扱われます。

## 実行時の動作

進捗 callback のたびに進捗データを状態辞書へ反映し、`minutes_left` と人向け `text` を加えて書き込みます。測定側の進捗データには `stage`、`message`、経過秒、完了済み・予定 run 数、推定残り秒、測定速度が含まれます（`strata_cli/tune_commands.py:202-215`; `strata_control/autotune.py:221-229`）。チューニングが終了すると `state: done`、結果、`stage: done` を書き込みます（`strata_cli/tune_commands.py:235-261`）。初期状態はメモリ上に作られますが、最初の進捗 callback が来るまでファイルへは書かれません（同: `202-215`）。

書込 helper は JSON（UTF-8、非 ASCII 文字をそのまま出力）を `<指定パス>.tmp` に書き、その後 atomic replace で指定パスへ置き換えます。既存の指定先ファイルは置き換わります。replace 実装は Windows で読み手がファイルを開いていることによる `PermissionError` を最大 5 秒再試行し、それ以外のエラーは送出します（`strata_cli/tune_commands.py:149-157`; `strata_control/atomic.py:18-35`）。

## 適用条件と副作用

- `--status-file` は `strata tune auto` 固有です。索引には同名の別スコープ `strata presets recheck` もありますが、そちらの parser・進捗処理は別です。本書では対象を `tune auto` に限定します（`docs/cli/README.md:802-824`; `strata_cli/tune_commands.py:82-90`）。
- 指定先の親ディレクトリは自動作成されません。`.tmp` への書き込みまたは置換で `OSError` が起きると helper が例外を握りつぶすため、status ファイルが更新されなくても CLI はこの理由だけでは失敗しません（`strata_cli/tune_commands.py:149-157`）。
- `strata launch` の tuning 経路は自分で status ファイルを選び、このオプションを子 CLI に渡して定期的に読みます。起動前にそのファイルを削除しようとしますが、これは `strata launch` 側の処理であり、直接 `strata tune auto` を呼ぶときの挙動ではありません（`strata_cli/launch/runner.py:1350-1377`）。
- `--output json` は最終結果を標準出力へ JSON で出す指定で、status ファイルとは独立です。JSON 出力モードでは進捗行を stderr に出さず、status ファイルには引き続き進捗を書きます（`strata_cli/tune_commands.py:178-179, 205-215, 255-261`）。

## 出力とエラー

オプション自身に対する値検証エラーは定義されていません。対象設定の読込や `--goal` の解析に失敗した場合、および engine が見つからない場合は、チューニング開始前に `_fail` からエラーを返します。この経路では status ファイルへの書き込みは行われないため、既存ファイルはそのまま残ります（`strata_cli/tune_commands.py:174-190`; `_fail` は同: `103-108`）。

通常の完了では最終状態を status ファイルに書いた後、`--output json` なら結果 JSON を stdout に出し、human 出力なら結果文を stdout に出します。終了コードは `improved` / `default_confirmed` が `0`、キャンセルが `130`、その他の outcome が `6` です（`strata_cli/tune_commands.py:255-261`）。進捗ファイルが書けない場合の警告・終了コード変更はありません（同: `149-157`）。

## 根拠

- parser 定義、既定値、説明: `strata_cli/tune_commands.py:20-46`
- status JSON の作成・置換と書込失敗の扱い: `strata_cli/tune_commands.py:149-157`
- `auto` における進捗・最終状態・結果出力: `strata_cli/tune_commands.py:174-261`
- progress payload の項目: `strata_control/autotune.py:221-229`
- Windows の replace 再試行: `strata_control/atomic.py:18-35`
- `strata launch` からの利用例と status 読取: `strata_cli/launch/runner.py:1350-1377`
- 索引上のコマンド階層: `docs/cli/README.md:802-824`

調査は上記 commit の checkout にあるソースを対象としました。Release 配布物や他 OS での実動作は確認していません。
