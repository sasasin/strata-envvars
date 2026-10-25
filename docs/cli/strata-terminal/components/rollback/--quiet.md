# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

成功時の人間向け標準出力を抑制します。ロールバックそのものの処理や状態変更を省略するオプションではありません。

## 使い方

```sh
strata components rollback --quiet
```

## 値と既定値

値は指定しません。指定すると `quiet=True` になります。省略時は parser が `quiet` 属性を作らず、CLI の `getattr(a, "quiet", False)` により無効として扱われます。繰り返し指定による別の動作はありません。

## 実行時の動作

`components rollback` parser は共通引数を登録した後、one-shot コマンド群とともに `--quiet` を `action="store_true"` で追加します。メイン処理は `--quiet` が有効で出力形式が `human` のとき、コマンドの標準出力を一時捕捉し、終了コードが 0 なら表示しません。終了コードが非 0 で捕捉した標準出力があれば、それを標準エラーへ再出力します。ロールバックのエラー自体も `update_cmd.run` が標準エラーへ出すため、quiet でも見えます。

`--output json`、`--output jsonl`、または alias の `--json` を使う場合、機械可読出力を保つため quiet による捕捉を行いません。JSON の成功・失敗レコードや JSONL イベントは引き続き標準出力に出ます。ロールバック中に稼働中エンジンの終了待ちが発生した場合、human 形式の待機メッセージも quiet では抑制されます。

## 適用条件と副作用

このフラグ自体の効果は出力制御に限られ、rollback の適用条件を変えません。コマンドは前回の更新が保持した engine を検証し、engine が稼働中なら `--wait` の指定に従って待機または失敗します。成功時には engine の pin、active/previous 状態、履歴を更新し、必要に応じて tuning preset に再確認マークを付けます。ダウンロードは行いません。

## 出力とエラー

- 既定の `human` 形式では、成功時のロールバック結果・preset 状態・再試行案内の標準出力を抑制します。
- 失敗時はエラーが標準エラーに表示されます。ロールバック先がない、すでにその版である場合は終了コード 2、保持された版が検証不能またはこの PC に適合しない場合は 5 です。稼働中 engine による拒否は `Busy`（終了コード 7）です。
- JSON/JSONL では `--quiet` でも機械可読出力を抑制しません。

## 根拠

- `strata_cli/update_cmd.py:30-39` は共通 parser 引数と `--output` の既定値を定義し、`strata_cli/update_cmd.py:57-59` で rollback parser に共通引数を登録します。
- `strata_cli/cli.py:508-516` は one-shot parser 群（`update_parsers` を含む）に `--quiet` と `--json` を追加します。
- `strata_cli/cli.py:2217-2248` は引数解析後の quiet 分岐、stdout 捕捉、非ゼロ終了時の再出力を実装します。`strata_cli/cli.py:2236-2237` では json/jsonl の場合に quiet 捕捉を迂回します。
- `strata_cli/cli.py:2135-2137` は `strata components rollback` を `update_cmd.run` に委譲します。
- `strata_cli/update_cmd.py:167-172,185-196,225-234` は rollback の human/JSON 成功出力、エラー出力と終了コードの伝播を示します。`strata_cli/update_cmd.py:237-252` は稼働中 engine に対する対話待機条件です。
- `strata_control/updater.py:300-310` は engine が稼働中の場合の待機イベントと Busy 失敗を定義します。`strata_control/updater.py:1033-1078` は rollback の検証、状態変更、preset mark、成功結果を実装します。
