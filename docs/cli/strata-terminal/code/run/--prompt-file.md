# `--prompt-file`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata code run` |
| オプション | `--prompt-file` |
| 別名 | なし |
| 値 | 必須。値は文字列として受け取る。パス形式やファイル内容の検証はこの parser では行わない。 |

## 役割

スクリプト形式の coding harness turn に渡す prompt ファイルを指定するための引数です。parser 上は必須ですが、この revision の `strata code` は共有 Desktop harness component が未導入のため、prompt を処理する実行機能は利用できません。

## 使い方

```sh
strata code run --prompt-file ./task.md --policy review --output jsonl
```

`--policy` も同じ `run` parser で必須です。実際には、必要な引数をそろえても本 revision では harness 不在エラーになります。

## 値と既定値

- 値は必須です。省略すると `argparse` の引数エラーになり、コマンド本体には進みません。
- parser は `type`、choices、default を指定していないため、受け取った文字列に対する CLI 側の型・範囲検証や既定値はありません。
- shell から空文字列を明示した場合（例: `--prompt-file ""`）も parser は文字列として受理しますが、実行処理がないため、その値を使うファイル処理はありません。
- 複数回指定した場合は `argparse` の既定の `store` 動作で最後の値が parser の結果になります。どの値が使われるかという実行時の意味は、harness が未導入のため確認できません。

## 実行時の動作

`strata code run` の parser は `--prompt-file` を必須の値付き引数として登録します。`main()` は引数を解析した後、`code` コマンドを `_run()` に渡しますが、`_run()` の `code` 分岐は常に「共有 Desktop harness component が未導入」として終了コード 5 を返します。この経路は `--prompt-file` の値を開いたり読み込んだりせず、harness へ転送もしません。

`--policy` も必須で、`--output` は `jsonl` のみを受け付け、既定値も `jsonl` です。JSONL 出力モードでは、harness 不在の失敗は stdout に schema version 1 の JSON error object として出力されます。現行ソースで `--prompt-file` の値に基づく別の動作や option 間の相互作用は確認できません。

## 適用条件と副作用

parser は `strata code run` のスコープに限られます。prompt ファイルへのアクセス、変更、ネットワーク要求、子プロセス起動は、この revision の `code` 実行経路では確認できません。Desktop との共有 harness/session API は将来の統合事項として記録されていますが、その API に渡す値の仕様は本調査では確認できません。

## 出力とエラー

- `--prompt-file` を省略する、または値を伴わず指定する場合、`argparse` が usage と引数エラーを stderr に出し、終了コード 2 で終了します。
- 必須引数をそろえた場合、共有 Desktop harness component 不在のエラーを返し、終了コード 5 で終了します。既定の `--output jsonl` では `_error()` が JSON error object を stdout に出力します。

## 根拠

- `strata_cli/cli.py:494-504` — `code` / `run` の parser 階層、必須の `--prompt-file` と `--policy`、`--output` の選択肢・既定値、`--quiet`。
- `strata_cli/cli.py:2119-2165` — `_run()` のコマンド分岐。`code` は prompt 値を参照せず、harness 不在として終了コード 5 を返す。
- `strata_cli/cli.py:527-533` — JSON 出力時の error object と戻り値。
- `strata_cli/cli.py:2217-2237` — `argparse` による引数解析、余分な引数の扱い、JSONL モードを含む dispatch。
- `tests/terminal/test_terminal.py:608-615` — 必須引数を与えた `code run` が現状終了コード 5 と JSON error を返すことを確認する既存テスト（この調査ではテストを実行していない）。
- `docs/TERMINAL.md:275-277` — 利用者向け資料も `strata code` を harness 不在で利用不可として説明。
- `docs/TERMINAL_IMPLEMENTATION_STATUS.md:21`、`docs/DEVELOPER_INTEGRATION_HANDOFF.md:59` — harness API の統合が未完了であることと、想定される連携境界。
