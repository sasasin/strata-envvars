# `--port`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--port` |
| 別名 | なし |
| 値 | `N`（1〜65535 の整数） |

## 役割

`strata launch` が起動するサーバーの待受ポートを指定します。`--access` が `local`、`lan`、`cloudflare`、`tailscale` のどれでも、このポート番号が run config、接続 URL、既存 launch とのポート競合判定に使われます。

## 使い方

```sh
strata launch --model iq3_xxs --port 8081 --no-tui
```

## 値と既定値

- 値は整数で、`1`〜`65535` が受理されます。`--port` の省略時は `8080` です。parser は `_port` を型変換関数として登録し、既定値は `LaunchSettings.port` に設定されています（`strata_cli/launch/cmd.py:55-62,119-123`、`strata_cli/launch/settings.py:32,77-99`）。
- 数字に変換できない値は「port number ではない」、範囲外は「port does not exist」とする `argparse.ArgumentTypeError` になります。空文字列も整数変換に失敗します（`strata_cli/launch/cmd.py:55-62`）。
- 1〜1023 は範囲内として受理されますが、実行環境によって管理者権限が必要になる旨の警告を出します（`strata_cli/launch/settings.py:155-165`）。
- `--port` を複数回指定した場合は `argparse` の通常の `store` 動作となり、最後に指定した値が残ります。独自の重複指定処理はありません（`strata_cli/launch/cmd.py:122`）。

## 実行時の動作

- `--preset NAME` と併用した場合、保存 preset を読み込んだ後に CLI の値を上書きするため、指定したポートがその起動の設定になります（`strata_cli/launch/cmd.py:197-203,252-255`）。`--save-preset NAME` を付けなければ、preset 起動時の変更は保存されず、既存 preset の使用記録のみ更新されます（`strata_cli/launch/cmd.py:788-792`）。
- 起動設定から作る private run config の `port` と、launch profile の `port` override に値を反映します（`strata_cli/launch/runner.py:371-376,1235-1244,1246-1263`）。
- 成功時の URL はこのポートを含みます。LAN ではローカルアドレス、Tailscale では tailnet のアドレスにも同じポートが付加され、Cloudflare tunnel の起動にもポートを渡します（`strata_cli/launch/access.py:285-296`、`strata_cli/launch/runner.py:1674-1694`）。
- 同じポートを使う別の `strata launch` サーバーがある場合は競合対象です。異なるポートなら並行起動できますが、GPU メモリー不足で新しい起動に失敗する可能性を通知します。同一ポートで設定が異なり `--restart` がなければ起動を拒否し、`--restart` があれば先行する Strata launch サーバーを止めてから起動します。同じ設定・ポートで既に稼働中なら再起動せず、そのサーバーを再利用します（`strata_cli/launch/runner.py:1505-1538,1546-1557`）。

## 適用条件と副作用

- 起動前に `127.0.0.1:N` へ接続を試み、接続できると「別プログラムが使用中」として起動を拒否します。この検査で使用中と判定されなければサーバー起動へ進みます（`strata_cli/launch/runner.py:1560-1574,1632-1646`）。
- ポートが空いていてもサーバー自体が起動できない場合があります。起動失敗時は当該 launch の runtime を停止・cleanup し、失敗を返します（`strata_cli/launch/runner.py:1596-1603,1648-1658`）。
- `--access` は待受 host と公開範囲も決めます。したがって `--port` は番号を選びますが、ポートだけで LAN やインターネットからの到達可否は決まりません（`strata_cli/launch/runner.py:371-380`）。共有アクセスで API key を使わない場合の警告は `check_access` が別途生成します（`strata_cli/launch/settings.py:173-191`）。

## 出力とエラー

- 不正な整数や範囲外の値は parser の型変換段階で拒否されます。実行時設定の検証エラーは human 出力では `stderr` に `strata: ...` と表示され、JSON 出力では `ok: false` とエラー情報を JSON で出力します。どちらも CLI が終了コード `2` を返す経路です（`strata_cli/launch/cmd.py:55-62,630-641,721-725`）。
- 1024 未満の値に関する注意は警告として設定検査結果に含まれます（`strata_cli/launch/settings.py:155-165`）。
- 別プログラムがポートを使用中と事前検査で判定された場合、`LaunchError` と終了コード `6` になります。起動中にサーバー側でポート使用中エラーが出た場合も、ログからポート競合を説明する経路があります（`strata_cli/launch/runner.py:1632-1646,2130-2138`）。

## 根拠

- `strata_cli/launch/cmd.py:55-62,119-123,197-203,252-255` — parser、範囲検査、preset と CLI 値の適用。
- `strata_cli/launch/settings.py:32,77-99,155-191` — 既定値、port の再検査と低番号の警告、access との組み合わせ。
- `strata_cli/launch/runner.py:371-380,1235-1263,1505-1557,1560-1646,1674-1694,2130-2138` — run config・profile への反映、稼働中 server の判定、起動前検査・失敗処理、Cloudflare tunnel と起動エラー。
- `strata_cli/launch/access.py:285-296` — 接続 URL への port の反映。
