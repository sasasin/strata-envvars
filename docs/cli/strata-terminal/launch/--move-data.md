# `--move-data`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--move-data` |
| 別名 | なし |
| 値 | 取らないフラグ（指定すると真） |

## 役割

`--data-dir` で新しいモデル保存先を指定するとき、既存の Strata モデルデータもその保存先へ移す意思を明示します。`strata launch` はフラグを setup 処理へ渡し、移動自体は `setup.py` が行います。既存データの移動を希望しない場合はこのフラグを付けず、新しい保存先を新規ダウンロード用として使います。

## 使い方

```sh
# 既存モデルを新しい保存先へ移す意思を明示して起動する
strata launch --family qwen --model q2_0 --data-dir ~/Strata-data-new --move-data
```

`--data-dir` を省くと、このフラグだけではデータ移動は行われません。

## 値と既定値

値は取りません。省略時は `False`、指定時は `True` となります。別名はなく、値の形式・範囲の検証はありません。引数を重ねて指定しても同じ真偽値のままです。`strata launch` の parser は `store_true` で登録しています（`terminal/strata_cli/launch/cmd.py:88-90`）。

## 実行時の動作

`strata launch` はまず `--data-dir` があるかを確認し、なければ `--move-data` が指定されていても移動意思を `False` とします。`--data-dir` があり、フラグを指定した場合は対話確認を省いて移動意思を setup runner に渡します（`terminal/strata_cli/launch/cmd.py:600-608,895-896`）。

runner は選択された `--data-dir` を setup 引数に加え、同時に `--move-data` と `--set-default-data-dir` も渡します。`--move-data` の転送条件は、移動意思が真で、かつ `LaunchSettings.data_dir` が明示されていることです。通常の準備経路では `setup.py` を子プロセスとして起動します（`terminal/strata_cli/launch/runner.py:1399-1405,1719-1730`）。

setup は指定先を解決し、利用できない指定先ならエラー経路へ進み、「何もダウンロード・変更せず、保存先として保存しなかった」と案内します。既存データ元を調べ、移動元と宛先が同じドライブの場合に `models`、`packs`、`mtp` を処理します。`models` はファイル単位で宛先へ統合し、同名の宛先ファイルは保持します。pack と MTP データは宛先に同じ項目がない場合に移します。移動後、モデル設定ファイル内のパスも、ファイルが移動済みの場合に更新します（`terminal/setup.py:7419-7434,7477-7501`）。

## 適用条件と副作用

- 同じ保存先を指定した場合や、移動元に対象データがない場合、移動対象はありません。
- 既存データが別ドライブにある場合はコピーせず、その場所で引き続き利用するデータとして扱います。同一ドライブのデータは移動し、別ドライブのデータは残ることがあります（`terminal/setup.py:7482-7485`）。
- `move_into` は rename/atomic replace を試みます。宛先が既にあるディレクトリは再帰的に統合し、宛先に同名ファイルがある場合は上書きしません。ファイル使用中などで移動できず元にデータが残る場合、setup は警告を出します（`terminal/setup.py:7349-7368,7487-7506`）。
- `--yes` は通常、確認を省いて既存データを保持する選択になりますが、明示した `--move-data` はその前に判定されるため移動意思として扱われます。`--plan` は `strata launch` 側でファイルを変更せず終了するため、フラグを付けてもその実行では移動しません（`terminal/strata_cli/launch/cmd.py:600-608,895-925`）。
- フラグなしで対話可能な通常実行では、同じドライブ上に移動可能なライブラリがあると選択を尋ねます。`--yes`、機械向け出力、`--plan`、`--no-tui`、キーボード入力のない実行では自動的に保持側となり、`--no-tui` などでは保持する旨を表示します（`terminal/strata_cli/launch/cmd.py:600-622`）。
- setup が既存モデルをそのまま再利用でき、`setup.py` の起動に進まない経路では、このオプションを使った移動処理も行われません（`terminal/strata_cli/launch/runner.py:1683-1707`）。

この文書は `strata launch` のオプション範囲を扱います。別の CLI 入口である setup 自身にも同名フラグがありますが、ここではその独立した parser の全仕様は扱いません（`terminal/setup.py:11510-11516`）。

## 出力とエラー

フラグなしの対話確認では、既存モデルを保持するか移すかを表示します。移動後も元にデータが残った場合は警告し、指定先へ移せた場合は完了メッセージを出します。指定先の検証失敗時は何も変更・ダウンロードせず、指定先を保存しなかった旨を示す失敗経路になります（`terminal/strata_cli/launch/cmd.py:616-622`; `terminal/setup.py:7431-7434,7468-7473,7502-7509`）。この調査では終了コードの値を当該失敗経路まで確定できる箇所は確認していません。

## 根拠

- `terminal/strata_cli/launch/cmd.py:88-90` — `strata launch` の parser 登録、フラグの説明。
- `terminal/strata_cli/launch/cmd.py:600-622,895-896` — `--data-dir` の有無、明示フラグ、`--yes`・機械実行・計画表示・対話確認の判断。
- `terminal/strata_cli/launch/runner.py:1399-1405,1719-1730` — setup 引数への転送と子プロセス起動。
- `terminal/setup.py:7342-7368,7419-7437,7451-7516` — 保存先検証、移動元の選別、移動・統合・設定保存。
- `terminal/strata_cli/launch/runner.py:1683-1707` — 既存モデル再利用や準備済みデータ採用で setup 起動を省く条件。
