# `strata components update --stop-model`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--stop-model` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる |

## 役割

更新対象があるとき、稼働中の Strata 管理モデルを更新のために停止してよいという明示的な許可を与える。特に、確認を行えないスクリプトや JSON 出力で使う。`strata update` にも同じフラグがあり、両コマンドは同じ更新処理を使う。

## 使い方

```sh
# 更新時に稼働モデルの停止を許可し、更新後に同じ設定で再起動する
strata components update --stop-model --start-again
```

このコマンドは更新を実行し、フィードの読み取りやダウンロード、コンポーネントのインストールを行い得る。`--stop-model` 単独ではスクリプトのモデル再起動を許可しない。更新後も起動する場合は `--start-again` を付ける。

## 値と既定値

値を取りません。省略時は停止許可が無効です。引数 parser は `action="store_true"` で定義し、別名や値の validation はありません。重複指定による追加の効果もありません（`terminal/strata_cli/update_cmd.py:77-79`）。

## 実行時の動作

`strata components update` と `strata update` の parser はそれぞれ `--stop-model` を登録し、どちらも同じ `update_cmd.run` に送ります（`terminal/strata_cli/update_cmd.py:59-79`、`terminal/strata_cli/cli.py:160-161,2210-2212`）。`run` は実更新のとき `ModelGate` を作り、このフラグを `allow_stop` に渡します（`terminal/strata_cli/update_cmd.py:366-368,414-417`）。

更新可能な変更があり、モデルが稼働中の場合、更新処理はダウンロード前に停止同意を確認します。`--stop-model` があると、その確認を省いて許可済みモデルを記録します（`terminal/strata_control/updater.py:2060-2074`、`terminal/strata_control/engine_update.py:300-325`）。実際の停止はダウンロード後、コンポーネントのステージングやテスト起動の直前です。停止に成功したモデルは更新後に `--start-again` または対話時の確認に従って再起動されます（`terminal/strata_control/updater.py:395-401`、`terminal/strata_control/engine_update.py:327-356,369-399`）。

相互作用:

- `--yes` は質問をすべて省く指定ですが、単独ではモデル停止を許可しません。非対話時に稼働モデルがあれば、`--stop-model` がないと何も変更せず終了コード 7 になります（`terminal/strata_cli/update_cmd.py:67,77`、`terminal/strata_control/engine_update.py:310-317`）。
- `--start-again` は停止済みモデルを更新後に再起動します。指定しない場合、対話端末では再起動を質問し、質問できない実行ではモデルを停止状態のままにして手動起動方法を表示・報告します（`terminal/strata_control/engine_update.py:369-399`）。
- `--check` はフィードを確認して返る経路で、モデル停止ゲートを呼びません（`terminal/strata_cli/update_cmd.py:357-363`）。更新対象がない場合もモデルゲートは呼ばれないため、このフラグの効果はありません（`terminal/strata_control/updater.py:2063-2065`）。

## 適用条件と副作用

停止対象は Strata が管理する稼働モデルです。`--stop-model` があっても、Strata が起動していない `strata serve` や他プログラムが保持する server は自動停止されず、終了コード 7 で更新を拒否します（`terminal/strata_control/engine_update.py:182-202,301-307`）。

モデルは新しいエンジンをダウンロードしている間は稼働を続け、その後に停止されます。停止に失敗した場合は更新を進めず、停止処理が何も変更していない保証もありません。停止後、GPU の解放を最大 120 秒待ちます。解放されない場合も終了コード 7 で後続の更新を拒みます（`terminal/strata_control/engine_update.py:290-295,327-367`）。停止処理はモデル runtime を停止し、該当する場合は Cloudflare tunnel も閉じます（`terminal/strata_control/engine_update.py:210-218`）。

## 出力とエラー

稼働モデルがあり、停止許可がない非対話実行、停止不能な server、停止失敗、停止後の GPU 解放待ちタイムアウトでは終了コード 7 になります。更新が成功しても、再起動が必要なモデルの再起動に失敗した場合は終了コード 8 になります。更新自体が失敗した場合は更新処理の終了コードが返り、停止済みモデルの再起動処理も試みられます（`terminal/strata_control/engine_update.py:33-34,301-367,369-425`）。

人が対話確認できない経路では、モデルの確認・進捗は通常文の代わりにイベントとして出力されます。`--output json` / `jsonl` の失敗は JSON エラーとして出力されます（`terminal/strata_cli/update_cmd.py:303-312,400-417`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:59-79` — 両コマンドの parser 定義と `--stop-model` の型。
- `terminal/strata_cli/update_cmd.py:303-321,357-373,400-417` — 実更新経路、停止ゲートへの値の転送、対話・機械出力時の扱い。
- `terminal/strata_control/updater.py:395-401,2060-2074` — 停止同意を確認する時点と、同意後に停止を実行する時点。
- `terminal/strata_control/engine_update.py:182-202,210-218,285-367,369-425` — 稼働モデルの識別、停止と副作用、失敗・再起動の扱い。
