# `--new-key`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--new-key` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。指定すると新しい API key を生成する |

## 役割

起動設定で使う API key を新しく作ります。共有アクセス時に通常再利用される既存 key をローテーションしたい場合に使います。生成した key は起動設定に設定され、成功時の通常出力では一部がマスクされます。

## 使い方

```sh
# 保存済み preset の key を更新し、起動中の同じ preset を再起動
strata launch --preset "Office" --new-key --restart

# LAN 共有用の新しい key を設定し、画面を開かず起動
strata launch --model q2_0 --access lan --new-key --no-tui
```

同じ設定でサーバーがすでに動いている場合、新しい key は起動設定の差分になるため、再起動には `--restart` が必要です。`--yes` だけでは再起動しません（`strata_cli/launch/cmd.py:132-135`、`strata_cli/launch/runner.py:1505-1538`）。

## 値と既定値

値は不要で、指定しない場合は `False` です。parser に型変換や値の validation はありません。実際にフラグが有効な起動経路へ進むと、`secrets.token_urlsafe(24)` の結果に `sk-strata-` を付けて key を作ります（`strata_cli/launch/cmd.py:125`、`strata_cli/launch/access.py:307-309`）。

## 実行時の動作

- `--preset` があれば preset を読み込み、他の起動フラグを上書きします。`--api-key` または `--api-key-env` の値が設定されていても、`--new-key` の処理が後に走るため新しい key に置き換わります。`--no-api-key` と同時に指定した場合も `--new-key` が後から `no_key=False` と key を設定するため、key なしの指定を打ち消します（`strata_cli/launch/cmd.py:197-203,252-269,721-729`）。
- `--new-key` がない場合、非ローカル共有で key が未設定かつ `--no-api-key` でないときは、以前の launch の key を優先して再利用し、なければ自動生成します。`--new-key` はこの後に適用されるため、その再利用・自動生成結果を差し替えます（`strata_cli/launch/cmd.py:341-350,721-729`、`strata_cli/launch/access.py:320-350`）。
- 新しい key は設定から launch 用 JSON に `api_key` として書かれ、mode `0600` を試みた一時ファイルから置き換えられます（`strata_cli/launch/runner.py:371-382,410-423,1235-1244`）。`--save-preset NAME` も指定して起動が成功すると key を含む設定を preset として保存します。既存 preset を指定しただけの場合、上書き保存はせず起動設定のみが変わります（`strata_cli/launch/cmd.py:788-792`、`strata_cli/launch/store.py:75-85`）。
- ローカルアクセスでもこのフラグを明示すれば key を設定します。反対にフラグなしのローカル起動では `apply_defaults` による自動 key 生成条件（`access != "local"`）に該当しません（`strata_cli/launch/cmd.py:341-350,726-729`）。
- `--plan` でも通常起動分岐を通れば key を生成して設定した上で計画表示へ進みますが、plan 分岐は `runner.run()` と preset 保存より前に終了します。そのため plan は生成値を永続化せず、key の値自体も計画出力には含めません（`strata_cli/launch/cmd.py:721-759,784-792`）。
- `--status`、`--show-key`、`--list-presets`、`--delete-preset`、`--stop` などの管理分岐は `--new-key` を処理する位置より先に終了するため、これらの管理操作で key は生成されません（`strata_cli/launch/cmd.py:643-678,721-729`）。

## 適用条件と副作用

このフラグ自体にアクセス方式の制限はありません。key が設定された run config でサーバーを起動すると、前の key を使っていたクライアントは新しい key に更新する必要があります。稼働中の同一 launch の選択内容比較では API key 自体を比較対象から除外しますが、代わりに key の SHA-256 先頭16桁の fingerprint を比較するため、ローテーションは異なる起動設定として扱われます。既存サーバーを止めるには `--restart` が必要で、指定しない非対話経路では `--restart` を促すエラーになります（`strata_cli/launch/runner.py:1435-1443,1505-1538`）。

key を含む preset ファイルおよび run config はユーザー設定領域に保存されます。通常出力は key をマスクして表示し、必要な場合は `strata launch --show-key` で確認できます（`strata_cli/launch/cmd.py:814-817`）。

## 出力とエラー

- 起動成功時、通常出力は key をマスクした値と `strata launch --show-key` の案内を表示します。`--output json` は key そのものを出さず、`api_key` を `"set"` または `null` として出力します（`strata_cli/launch/cmd.py:801-817`）。
- `--plan` は key の有無を表示しますが key 値は出力しません（`strata_cli/launch/cmd.py:733-759`）。
- 既存サーバーと異なる選択として判定され、`--restart` がなければ、対話画面がない経路では `--restart` または `strata launch --stop` を案内する失敗になります（終了コード 6。`strata_cli/launch/runner.py:1525-1538`）。
- key の生成自体に入力値由来の validation error はありません。起動側で発生する `LaunchError` は CLI がエラー文とそのコードで返します（`strata_cli/launch/cmd.py:636-641,784-787`）。

## 根拠

- `strata_cli/launch/cmd.py:119-126` — `strata launch` のアクセス/API key parser 定義。
- `strata_cli/launch/cmd.py:197-203,252-269` — preset と key 関連フラグから起動設定を構築する順序。
- `strata_cli/launch/cmd.py:341-350,721-729` — 共有時の既存 key 再利用・自動生成と `--new-key` による差し替え。
- `strata_cli/launch/access.py:307-350` — key の生成形式と再利用元の探索。
- `strata_cli/launch/runner.py:371-382,410-423,1235-1244` — key の run config への反映とファイル書き込み。
- `strata_cli/launch/runner.py:1435-1443,1505-1538` — 起動設定の識別と既存サーバーに対する再起動条件。
- `strata_cli/launch/cmd.py:801-817`、`strata_cli/launch/store.py:75-85` — 成功出力と preset 保存。
