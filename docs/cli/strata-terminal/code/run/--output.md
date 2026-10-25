# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata code run` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `jsonl` のみ |

## 役割

`strata code run` の機械可読出力モードを指定します。現行 parser は `jsonl` だけを許可し、既定値も `jsonl` です。ただし現行 dispatcher は coding harness を実行せず未導入エラーを返します。そのため、この revision で成功時の JSONL イベント列が出力される動作は確認できません。

## 使い方

```sh
strata code run --prompt-file task.md --policy policy.json --output jsonl
```

`--prompt-file` と `--policy` は必須です。現行ソースの dispatcher では、このコマンドは harness 未導入エラーで終了コード `5` になります。

## 値と既定値

- 値は必須で、選択肢は `jsonl` のみです。指定を省略しても `jsonl` が使われます。
- `human`、`json` など選択肢外の値は parser に拒否されます。`argparse` の選択肢検証により usage とエラーが stderr に出て、終了コード `2` で終了します。
- 同じオプションを複数回指定した場合は、`argparse` の通常の `store` 動作により最後の値が残ります。値がすべて `jsonl` なら結果は同一です。

## 実行時の動作

parser は `--output jsonl` を受理しますが、`_run` の `code` 分岐は共有 Desktop harness が未導入としてエラーを返し、`a.output` が `json` または `jsonl` の場合は machine 出力を選びます。`_error` は stdout に `schema_version: 1`、`ok: false`、`error`（終了コードとメッセージ）を含む JSON オブジェクトを1行で出力します。これは現行の失敗経路で確認できる出力であり、成功時の JSONL イベント形式を示すものではありません。

`--quiet` は `code run` にも登録されていますが、`output` が `jsonl` であるため `main` は quiet 用の人間向け出力捕捉を行わず `_run` に進みます。`--output` は `code run` の parser に登録されたオプションで、ほかのコマンドの同名オプションとはスコープが異なります。

`--json` は `code run` の別名として登録されていません。共通の `--json` 登録対象には `code_sessions` は含まれますが `code_run` は含まれないため、`code run --json` は未認識引数の parser エラーになります。

## 適用条件と副作用

このオプション自体は出力先ファイルを作成・上書きせず、値を `jsonl` に限定します。現行の `code` dispatcher は `run` を含む `code` コマンド全体を「共有 Desktop harness component is not installed」として終了コード `5` で返すため、prompt の処理や成功イベント出力には到達しません。

## 出力とエラー

- `--output` を省略、または `--output jsonl` とした場合、現行 dispatcher の未導入エラーが stdout に JSON 1行で出て、終了コード `5` になります。
- `--output` を欠落させると値不足の parser エラー、選択肢外の値を渡すと choices エラーになります。どちらも `argparse` による usage/error で終了コード `2` です。
- 成功時の出力、イベントの種類・順序、ストリーム終端規則は、この revision の CLI 実装からは確認できません。

## 根拠

- `strata_cli/cli.py:494-504` — `code run` parser、`--output` の choices/default、必須引数と `--quiet`。
- `strata_cli/cli.py:508-515` — 共通 `--json` alias の登録対象に `code_sessions` はあるが `code_run` はない。
- `strata_cli/cli.py:527-532` — machine error の JSON 形式と終了コードの返却。
- `strata_cli/cli.py:2153-2165` — `code` コマンドを harness 未導入エラーにする dispatcher 分岐。
- `strata_cli/cli.py:2217-2237` — parser の呼び出しと、JSON/JSONL 出力時に quiet 捕捉を行わず `_run` へ進む条件。
- `tests/terminal/test_terminal.py:608-615` — 既存テストに記録された `code run --output jsonl` の終了コード `5` と JSON エラー確認（調査ではテストを実行していません）。
- `docs/TERMINAL.md:275-277` — Terminal CLI の現在の `strata code` 制約に関する補足資料。

調査時点で共有 harness が提供する成功経路の実装をこの CLI checkout から確認できなかったため、成功時の JSONL スキーマや出力順序は記載していません。CLI の `--help` は実行していません。`main` は parser 構築より前にユーザー既定値を引き継ぐ処理を呼ぶため、調査時の副作用を避け、parser 定義を根拠としました。
