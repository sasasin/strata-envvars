# `strata timeskip apply --workspace`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip apply <run_id>` |
| オプション | `--workspace` |
| 別名 | なし |
| 値 | ディレクトリパス（文字列）。省略可能 |

## 役割

記録済み Time-skip run の結果または baseline を適用するディレクトリを指定します。省略時は run が記録した workspace が使われます。これは `strata timeskip run --workspace` の必須オプションとは別の parser scope です。

## 使い方

```sh
strata timeskip apply RUN_ID --workspace ./review-copy --dry-run
```

`RUN_ID` は `strata timeskip list` などで確認した run ID です。まず `--dry-run` で変更予定を表示できます。

## 値と既定値

- parser は `--workspace` の値を文字列として受け取り、型変換・選択肢・存在確認を行いません。省略時の値は `None` です。
- 実行時に値があれば `Path(value)` に変換して適用先にし、なければ run データの `workspace` を適用先にします。相対パスはプロセスの現在ディレクトリを基準に解決されます。
- 重複指定時の argparse の扱いは通常の単一値引数で、最後に指定した値が namespace に残ります。

## 実行時の動作

- 通常の apply では、指定先（または記録済み workspace）のファイル inventory を run の baseline digest と比較します。比較対象から `.git`、`__pycache__`、`.strata` ディレクトリとシンボリックリンクは除外されます。内容が開始時から変化していれば上書きを拒否します。
- `--dry-run` と併用すると、書き込みはせず、変更予定ファイルと削除予定ファイルを報告します。
- apply を実行すると、指定先の現状を run store 配下の `rollback` にコピーしてから、選択された結果を反映します。途中で反映に失敗すると rollback copy から復元します。指定先は既存ディレクトリであることが必須とは parser 上定められていませんが、baseline と比較できる状態でなければ通常 apply は拒否されます。
- `--attempt N` を併用すると、保持された checkpoint ではなく番号 `N` の revision attempt を適用します。attempt の存在と保存先ディレクトリの存在が確認されます。
- `--restore` を併用すると、`--workspace` は baseline を戻す先になります。この経路は通常 apply の「開始時から変化していないか」という比較を行いません。コピー処理は既存の宛先ディレクトリを削除してから baseline をコピーするため、指定先の現状を置き換えます。通常 apply の `--dry-run` / `--attempt` の処理はこの restore 分岐では呼ばれません。

## 適用条件と副作用

`--workspace` は `timeskip apply` 専用です。同じ文字列のオプションは `timeskip run` にもありますが、そちらは必須で run の対象 workspace を指定します。

run の記録を読むため state store が必要です。`--state-dir` でその場所を指定できます。指定がなければ `STRATA_TIMESKIP_DIR`、それもなければプラットフォーム別 state base の `time-skip` が使われます。

通常 apply は変更ファイルをコピーし、baseline にあったが選択結果にはないファイルを削除します。`--restore` は指定先を baseline のコピーで置き換えるので、宛先を慎重に選んでください。

## 出力とエラー

- 既定の human 出力では、通常 apply は `applied ...` と rollback copy の場所を表示します。`--dry-run` は `would write` / `would remove` を表示します。restore は復元した checkpoint と宛先を表示します。
- run ID が見つからないなど `TimeSkipError` は stderr に `strata: ...` を出し、終了コード 2 になります。
- 通常 apply の宛先が baseline から変わっている場合は競合として拒否し、stderr に理由を出して終了コード 6 になります。apply が完了しなかった場合も終了コード 6 です。
- `--output json` を併用すると成功・明示エラーは JSON で出力されます。適用失敗の途中で rollback が行われた場合も、通常 apply の失敗結果として扱われます。

## 根拠

- parser 定義、option scope と既定値: `strata_cli/cli.py:380-393`
- `--workspace` を `Path` にして適用先を決める箇所、restore 分岐、競合・終了コード・人向け出力: `strata_cli/cli.py:1524-1555`
- run データから workspace と checkpoint を再構成する箇所: `strata_cli/cli.py:1605-1618`
- state directory の選択と store 初期化: `strata_cli/cli.py:1476-1485`
- baseline との inventory 比較、dry-run、rollback copy と適用、失敗時復元: `strata_control/time_skip.py:597-652`
- restore が宛先を baseline で置き換える処理: `strata_control/time_skip.py:654-664`、`strata_control/time_skip.py:271-285`
- inventory 対象から除外するディレクトリ、symlink の扱い: `strata_control/time_skip.py:241-261`
- 共通エラーの stderr / JSON 出力と終了コード: `strata_cli/cli.py:527-542`
