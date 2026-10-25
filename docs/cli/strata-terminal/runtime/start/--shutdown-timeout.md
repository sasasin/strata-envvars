# `--shutdown-timeout`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime start` |
| オプション | `--shutdown-timeout` |
| 別名 | なし |
| 値 | 秒数の浮動小数点数。有限値で `0..300`（両端を含む） |

## 役割

`strata runtime start` が起動するバックグラウンド server を停止するとき、実行中の推論呼び出しを drain する最大時間を指定します。設定値は起動時に owner host と server に渡され、`runtime stop` や `--die-with-pid` による終了時の停止処理に使われます。起動待ち時間を指定する `--wait` とは別の設定です。

## 使い方

```sh
strata runtime start --profile local --shutdown-timeout 45.5
```

## 値と既定値

- 値は必須で、parser は `float` に変換します。省略時は `30` 秒です。短縮別名はありません（`strata_cli/cli.py:203-212`）。
- CLI の実行経路では `strata_control.management._seconds` が有限値かつ `0 <= 値 <= 300` であることを検証します。`NaN`、正負の無限大、範囲外の値は拒否されます。`0` も受理されます（`strata_control/management.py:113-117,202-205`）。
- parser の `float` 変換に失敗する値は argparse の引数エラーです。数値に変換できても上記範囲に入らない値は `ProfileError` になります。

## 実行時の動作

1. `strata_cli.cli._runtime` は parser の値（未指定なら `30`）を management 層へ渡します（`strata_cli/cli.py:1331-1356`）。
2. start の実行経路では値を検証し、journal に記録する `shutdown_timeout_s` と `runtime.start` 呼び出しの引数に含めます。`--plan` の場合は launch plan に `shutdown_timeout` として表示しますが、起動しません（`strata_control/management.py:202-230`）。
3. runtime は値を owner host の子プロセス引数として渡します。owner host は値を保持し、起動する server の argv に `--shutdown-timeout` として追加します（`strata_control/runtime.py:518-530,559-574,744-753,847-853`）。
4. server の停止時には graceful drain を開始し、設定秒数だけ待ちます。期限までに処理が終わらない場合、server はその server が所有するリクエストをキャンセルし、最大 5 秒追加で drain を待った後、drain 未完了として終了コード `8` を返します（`serve/server.py:8672-8687,8706-8713`）。
5. owner host 自身は子 server の終了を `shutdown_timeout + 8` 秒待ちます。それでも終了しなければ子プロセスツリーを kill し、`server_stop_deadline_expired`・終了コード `8` を返します（`strata_control/runtime.py:990-1012`）。

## 適用条件と副作用

- この文書の対象はバックグラウンド管理サービスである `strata runtime start` です。値は server の停止処理に適用され、通常の起動待ち時間や profile の設定ファイルは変更しません。
- `strata serve --shutdown-timeout` にも同名 option がありますが、別コマンド・別 parser の設定です。`serve` 側の既定値、validation、foreground 動作は [`strata serve` の option 文書](../../serve/--shutdown-timeout.md)を参照してください。索引でも command scope ごとに分離されています（`docs/cli/README.md:38-49,388-400`）。
- `runtime start --plan` は設定値を含む計画を返すだけで、owner host / server を起動しません（`strata_control/management.py:207-219`）。
- 停止が値の期限内に終わらない場合、未完了の owned request はキャンセルされます。さらに owner host の待機期限も超えると server プロセスツリーが強制終了されます（`serve/server.py:8682-8687`; `strata_control/runtime.py:1000-1007`）。

## 出力とエラー

- 成功時の通常出力は profile の状態や接続先などで、`--output json` なら JSON を stdout に出します（`strata_cli/cli.py:1331-1373`）。
- 非有限値または範囲外の値は `shutdown timeout must be finite seconds in 0..300` の validation error となります。通常出力では `strata: ...` を stderr、JSON 出力ではエラー JSON を stdout に出し、終了コードは `2` です（`strata_control/management.py:113-117`; `strata_cli/cli.py:527-532,2166-2173`）。
- server 側の drain 期限切れは lifecycle 通知に `drained: false`、キャンセル数、終了コード `8` を含めます。owner host が設定秒数に 8 秒を加えた待機期限を超えた場合は `server_stop_deadline_expired` を返します（`serve/server.py:8708-8713`; `strata_control/runtime.py:1000-1012`）。

## 根拠

- `strata_cli/cli.py:203-212` — `runtime start` parser、必須の `--profile`、`--shutdown-timeout` の float 型と既定値。
- `strata_cli/cli.py:1331-1373` — option 値の management への転送と human/JSON の結果出力。
- `strata_control/management.py:113-117,202-230` — finite seconds の範囲検証、plan 表示、実行時の記録と呼び出し。
- `strata_control/runtime.py:518-574,744-753,847-853` — owner host 起動引数への転送と managed server 引数への伝播。
- `strata_control/runtime.py:990-1012` — 停止時の owner host 待機、強制終了、失敗結果。
- `serve/server.py:8672-8713` — graceful drain、期限時の owned request キャンセル、終了状態・終了コード。
- `docs/cli/README.md:388-400` — `strata runtime start` scope と本 option の索引リンク。`docs/cli/README.md:38-49` には別 scope の `strata serve --shutdown-timeout` もある。
