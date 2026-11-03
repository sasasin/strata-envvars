# `--json`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--json` |
| 別名 | なし（`--output json` と同じ出力形式を選ぶ別指定） |
| 値 | 取らないフラグ。省略時 `false` |

## 役割

削除結果を人向けの文章ではなく、1 件の JSON オブジェクトとして標準出力へ出します。エンジンの削除対象や削除可否は変えません。

## 使い方

```sh
strata components engines --json
strata components remove FOLDER_NAME --json
```

`FOLDER_NAME` は説明用の置き換え文字列です。実行前に `strata components engines --json` などで対象を確認し、実在する削除対象外の folder 名へ置き換えてください。`remove` は導入済み engine を削除します。

## 値と既定値

このフラグは `argparse` の `store_true` で登録され、値を取りません。省略時は `false` で、共通の `--output` の既定値 `human` が使われます。`--json` を指定すると CLI の共通処理が `output` を `json` に設定します。`--output` は `human` / `json` / `jsonl` を受け付けます。

## 実行時の動作

`strata_cli/cli.py` は `update_parsers` に属する parser へ `--json` を後付けし、`components remove` もその対象に含めます。トップレベル処理が `--json` を検出すると `a.output = "json"` にし、`update_cmd.run()` は `output` が `json` または `jsonl` のとき機械可読出力として実行します (`strata_cli/cli.py:508-515, 2249-2254`; `strata_cli/update_cmd.py:233-239`)。

削除成功時は標準出力に `schema_version: 1` と `ok: true`、削除処理の返却情報を含む JSON を1行出します。返却情報には component/family、`status: "deleted"`、`changed: true`、folder、version、`freed_bytes` が含まれます。人向け出力にある「削除した容量」等の文章は出ません (`strata_cli/update_cmd.py:395-400`; `strata_control/engine_library.py:333-334`)。

## 適用条件と副作用

`--json` は出力形式だけを指定します。実際の削除では、対象エンジンを解決した後に削除可否を再確認し、使用中または実行中のエンジンは削除を拒否します。実行中の判定は対象 folder を使うプロセスの確認に基づきます。成功時は対象 folder を一時名へ rename してから削除し、Qwen engine の状態履歴や pin/previous 情報も必要に応じて更新します。モデルと設定、および別 family の engine は削除対象外です (`strata_control/engine_library.py:84-86, 167-176, 294-334`)。

`--json` と `--output jsonl` を同時に指定すると、one-shot 用 `--json` と `jsonl` の併用として CLI が終了コード 2 で拒否します (`strata_cli/cli.py:2249-2252`)。`--quiet` を併用しても JSON 出力は抑制されません。JSON 出力モードでは quiet による stdout 捕捉処理へ進まないためです (`strata_cli/cli.py:2253-2260`)。

## 出力とエラー

削除関数が `UpdateError` を返す失敗（対象なし・曖昧な指定・使用中・実行中など）は、`--json` 指定時には標準出力へ `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` 形式で出され、返却された終了コードで終了します。対象 folder の rename に失敗した場合は終了コード 6 となり、「何も変更していない」旨のエラーになります。通常の削除拒否は終了コード 2 です (`strata_control/engine_library.py:198-210, 294-316`; `strata_cli/update_cmd.py:237-243, 307-311`)。

引数の構文・選択肢の誤りはコマンド処理へ入る前に argparse が拒否します。`--json` 自身に値を付ける形式ではなく、`--json=true` のような指定は有効な使い方ではありません (`strata_cli/cli.py:2241-2248`; `strata_cli/update_cmd.py:508-515`)。

## 根拠

- `strata_cli/update_cmd.py:88-91` — `remove` parser と位置引数、共通 parser 登録。
- `strata_cli/cli.py:508-515` — `update_parsers` への `--json` / `--quiet` 後付け。
- `strata_cli/cli.py:2249-2260` — `--json` の `output=json` 化、jsonl との併用拒否、quiet 出力分岐。
- `strata_cli/update_cmd.py:233-243, 272-273, 395-400` — JSON 判定、remove dispatch、成功・失敗出力。
- `strata_control/engine_library.py:84-86, 167-176, 198-210, 294-334` — 実行中判定、削除不可条件、対象解決、ファイル削除と状態更新、返却値。
