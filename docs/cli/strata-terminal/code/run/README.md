# `strata code run`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata code run` |
| 主な実装 | `strata_cli/cli.py` |

## 役割

parser 上は、共有 Desktop harness に対する scripted turn を実行するコマンドです。ただし、調査対象 revision では共有 harness component が未導入として扱われ、実行要求は常にエラー終了します。prompt、policy、workspace、resume を使った turn 処理や成功経路はこの CLI ソースでは確認できません。

## 使い方

```sh
strata code run --prompt-file ./task.txt --policy ask
```

これは parser が受理する引数の形を示す例です。この revision では実行できず、標準エラーに shared Desktop harness component が未導入で coding sessions を利用できない旨を出して終了コード `5` で終了します。

`--workspace` と `--resume` は `code` 側の引数として定義されているため、指定する場合は `run` より前に置きます。`--quiet` は `code` と `run` の両方に定義されています。現行の未導入エラー分岐では、これらの値を使った処理はありません。

```sh
strata code --workspace ./project --resume SESSION_ID run --prompt-file ./task.txt --policy ask
```

## 実行モードと動作

- `code run` parser は `--prompt-file` と `--policy` を必須として受け取り、`--output` は `jsonl` のみを選択でき、既定値も `jsonl` です。`--quiet` は人間向け情報出力を抑える指定として登録されています。
- `--policy` は文字列引数として定義されているだけで、選択肢・値検証・既定値は定義されていません。`--prompt-file` のファイル読込や値の検査も、このコマンドの現行実行経路にはありません。
- `strata code` の処理分岐は、サブコマンドにかかわらず harness component 未導入のエラーを返します。`--output jsonl` が既定値のため失敗は JSON 形式で stdout に出力され、payload は `schema_version: 1`、`ok: false`、エラーコード `5` とメッセージを含みます。
- CLI の概要文書も、この版では `strata code` は利用できず終了コード `5` になると説明しています。Strata サーバーに接続する coding app の案内先として `strata connect` を挙げています。

## 注意点

parser 定義は将来の scripted harness turn を示す形ですが、この checkout ではその処理本体が利用可能な CLI 経路につながっていません。`--policy` の仕様、prompt file の形式、workspace/resume の挙動、セッション作成やファイル変更などの副作用は確認できないため、ここでは記述していません。配布済み Release の CLI は別途照合していません。

## 関連文書

- [`strata code` コマンド概要](../README.md)
- [CLI 文書索引](../../../README.md) — `strata-terminal` のコマンド階層と option scope
- Strata の利用者向け説明 `docs/TERMINAL.md` — `strata code` の現行制限と `strata connect` の案内

## 根拠

- `strata_cli/cli.py:494-504` — `code` / `run` parser、親・子 parser の引数、必須指定、`--output` の choices と既定値。
- `strata_cli/cli.py:2119-2165` — `_run` が `code` コマンドに対して component 未導入エラーを返す分岐。
- `strata_cli/cli.py:527-532,2232-2248` — エラーの JSON / stderr 出力、終了コードの返却、quiet 時の処理。
- `docs/TERMINAL.md:275-277` — Terminal CLI の現行制限と `strata connect` への案内。
