# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定時は真、未指定時は偽 |

## 役割

rollback の結果を機械処理向け JSON で出力します。`--json` はこのコマンドの parser に後から共通登録される一回実行コマンド用フラグで、内部では `--output json` に相当します。rollback 自体の対象や処理は変えません。

## 使い方

```sh
strata components rollback --json
```

同じ出力形式は `--output json` でも指定できます。

## 値と既定値

値を取らない `argparse` の `store_true` フラグです。未指定時は `False`、指定時は `True` です。`--json yes` のように値を続ける指定は余分な引数として拒否されます。

この parser には `--output` もあり、選択肢は `human`、`json`、`jsonl`、既定値は `human` です。`--json` を指定すると `output` が `json` に設定されます。`--json` と `--output jsonl` を同時に指定すると「`--json` は one-shot only」というエラーになり、終了コード 2 の JSON エラーを返します。

## 実行時の動作

CLI は共通の update parser 群に `--json` を追加し、解析後に `output=json` へ変換します。rollback の実行経路は `updater.rollback_engine()` を呼び出し、JSON 成功時は `schema_version: 1`、`ok: true` と rollback 結果（`component`、`status`、`from`、`to`、`folder`、`presets_marked`）を含むオブジェクトを標準出力へ1行で出します。

JSON モードは進捗・待機イベントの人間向け表示を抑制します。処理は保存済みの previous engine の manifest と全ファイルを検証し、次回起動時にその engine が選ばれるよう pin を保存します。以前の engine が残っていれば previous の参照を入れ替え、必要なときは現行 engine version を再試行対象から除外する skipped 状態に記録します。変更履歴を保存し、engine identity が変わった場合は tuning preset に再確認マークを付けます。rollback は feed の取得や engine のダウンロードを行いません。

`--json` は共通オプション `--wait` の動作にも影響します。engine が稼働中で `--wait` が省略または 0 以下なら、JSON モードは対話確認を行わず Busy エラーを返します。正の `--wait SECONDS` を指定すると、その秒数内で停止するまで待機します。

## 適用条件と副作用

previous engine が保存されていない場合、または既に previous engine が有効な場合は rollback できません。previous engine の完全検証に失敗した場合や、現在の PC に適合しない場合も拒否されます。成功時は次回 engine 選択状態と update state/history を変更します。現在の実行中プロセスを直接切り替える処理ではありません。

rollback 分岐では `--backend` がハードウェア情報に反映され、previous engine が現在の PC に適合するかの解決に使われます。一方、`--force`、`--feed`、`--model-config` は parser では受理されますが、rollback 分岐の実処理には適用されません。

## 出力と失敗

成功時、`--json` は `{"schema_version":1,"ok":true,...}` の JSON を標準出力に出し、終了コード 0 を返します。rollback の `UpdateError` は `ok: false` と `error.code` / `error.message` を含む JSON を出力します。代表的な失敗は次のとおりです。

- previous engine がない、またはすでに rollback 済み: 終了コード 2。
- previous engine を完全検証できない、または現在の PC に適合しない: 終了コード 5。
- 待機時間内に稼働 engine が停止しない: Busy による終了コード 7。
- `--json` と `--output jsonl` の併用: rollback 実行前に終了コード 2。

機械出力時は失敗 JSON を標準出力へ出します。rollback 処理中の Ctrl+C は `KeyboardInterrupt` として終了コード 130 の JSON エラーになります。

## 根拠

- `strata_cli/update_cmd.py:30-40,57-59` は rollback parser が共通 option 群を使い、`--output` の値と既定値を定義することを示します。
- `strata_cli/cli.py:508-515` は `--json` と `--quiet` を update parser 群へ追加します。`strata_cli/cli.py:2223-2236` は引数変換、JSONL との併用拒否、後続 dispatch を示します。
- `strata_cli/cli.py:2135-2137` は `strata components rollback` を `update_cmd.run()` に振り分けます。
- `strata_cli/update_cmd.py:62-84,163-196,225-234` はイベント抑制、成功・失敗 JSON、終了コード処理を示します。`strata_cli/update_cmd.py:174-188` は rollback が `--wait` 等の context を組み立て `rollback_engine()` を呼ぶ箇所です。
- `strata_cli/update_cmd.py:237-252` と `strata_control/updater.py:300-312` は機械出力時に対話確認せず、待機時間後に Busy となる条件を示します。
- `strata_control/updater.py:1033-1078` は previous engine の検証、pin・active・previous・skipped・history の更新、tuning preset マーク、失敗経路を示します。
- `strata_cli/update_cmd.py:174-188` と `strata_control/updater.py:1050-1066` は `--backend` を含む hardware 情報が previous engine の解決・適合確認に使われることを示します。`--force` 等の他の共通 option が rollback で参照されないことは `strata_cli/update_cmd.py:182-188` と `strata_control/updater.py:1033-1078` で確認できます。

確認範囲は上記 revision のソース checkout です。同一 revision の実行 CLI help や Release artifact は使用していません。索引の `strata components rollback` 配下にある `--json` のリンクと parser 定義は一致しています。
