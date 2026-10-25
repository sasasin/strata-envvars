# `--policy`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata code run` |
| オプション | `--policy` |
| 別名 | なし |
| 値 | 必須の文字列。選択肢や形式の定義はない |

## 役割

parser は `--policy` を必須引数として定義しています。しかし、この checkout の CLI 実装では値の内容を検証したり、実行処理へ渡したりしていません。したがって、この revision の Strata ソースだけから policy が表す規則や選べる値を特定することはできません。

## 使い方

parser 上の構文は次のとおりです。`--prompt-file` も必須です。

```sh
strata code run --prompt-file ./prompt.txt --policy '<文字列>'
```

## 値と既定値

値は必須で、`argparse` の `add_argument("--policy", required=True)` によって受理されます。`type`、`choices`、`default`、追加の validator は指定されていません。そのため、parser が特定の文字列形式や許容範囲を保証することはなく、省略時は通常の引数 parser エラーになります。空文字列も値として渡せます。同じオプションを複数回指定した場合は通常の `argparse` の単一値引数として最後の値が残りますが、いずれの値にも CLI 内での policy 意味論は定義されていません。

## 実行時の動作

引数解析後、`_run()` は `a.command == "code"` の場合、`code_command` や `a.policy` を調べずに共有 Desktop harness が未導入である旨を返します。返される終了コードは 5 です。このため、`--policy` の値がこの checkout の実行結果に与える差は確認できず、policy による harness 実行は行われません。

`code run` の `--output` は `jsonl` のみを選べ、既定値も `jsonl` です。この失敗は `machine=True` で `_error()` に渡されるため、JSON のエラーオブジェクトが標準出力へ出力されます。人向け出力の場合の `_error()` は標準エラーを使いますが、このコマンドの parser では `--output human` は受理されません。

## 適用条件と副作用

この parser 定義が有効なのは `strata code run` のスコープです。実行時は `--policy` の値に関係なく harness 未導入エラーとなり、policy に基づく処理、prompt ファイルの読み込み、セッション実行はこの dispatch からは行われません。オプション固有のファイル・ネットワーク・プロセスへの副作用は確認できません。

## 出力とエラー

- `--policy` または必須の `--prompt-file` を省略すると、実行 dispatch の前に `argparse` が引数エラーを出します。
- 必須引数を満たして実行すると、標準出力に `{"schema_version": 1, "ok": false, "error": {"code": 5, "message": "the shared Desktop harness component is not installed; coding sessions are unavailable"}}` 相当の JSON が出力され、終了コード 5 になります。JSON のキー順・空白などの具体的な整形は `json.dumps` によります。

## 根拠

- `strata_cli/cli.py:494-504` — `code run` parser、`--policy` 必須指定、型・選択肢・既定値の指定がないこと、`--output jsonl` とその既定値。
- `strata_cli/cli.py:2119-2165` — `_run()` の dispatch。`code` 分岐では policy 値を参照せず、固定エラーと終了コード 5 を返す。
- `strata_cli/cli.py:527-532` — machine 出力時の JSON エラー形式と、human 出力時に標準エラーを使う処理。
- `strata_cli/cli.py:2223-2231` — `main()` による引数解析と、parser が認識しない引数のエラー処理。

調査は上記 commit の Strata checkout に含まれる Terminal CLI ソースに限定しました。安全な同一 revision の `--help` は実行していません。共有 Desktop harness 側の実装・policy schema はこの CLI dispatch から確認できず、policy の許容値や将来の harness 動作は未確認です。
