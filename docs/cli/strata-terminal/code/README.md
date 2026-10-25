# `strata code`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata code` とそのサブコマンド |
| 主な実装 | `strata_cli/cli.py` |

## 役割と現在の状態

`strata code` は Desktop と共有する coding harness の CLI として parser に登録されています。しかし、この revision では、help 表示や parser による引数拒否を除く実行呼び出しは harness の処理へ進まず、`strata code`、`strata code run`、`strata code sessions list` のいずれも「shared Desktop harness component is not installed; coding sessions are unavailable」と報告して終了コード `5` で終了します。したがって現時点で、コマンドからコーディングセッションを開始・再開したり、セッションを列挙したりすることはできません。

## parser が受け付ける形式

```sh
# コマンドのヘルプ
strata code --help

# scripted turn の形式（現行実装では harness 未導入エラーで終了）
strata code run --prompt-file ./prompt.txt --policy POLICY

# sessions 一覧の形式（現行実装では harness 未導入エラーで終了）
strata code sessions list
```

`code` の階層には `--workspace`、`--resume`、`--quiet` があり、`run` には必須の `--prompt-file` と `--policy`、`--output jsonl`、`--quiet` があります。`sessions` は位置引数 `action` に `list` のみを受け付け、`--output human|json` と `--json` を利用できます。これらは parser 上の受理形式です。現行の dispatcher は処理を実行せずにエラーを返すため、workspace・resume・policy の値の意味やセッションへの効果はこのソースから確認できません。

## 実行時の動作と出力

- help 表示や parser による引数拒否を除き、`strata code` 以下の実行呼び出しは同じ未導入エラーに到達します。prompt の読み込み、policy 適用、session の照会や変更、外部プロセス起動などの実行処理は、このコマンド経路にはありません。
- 通常出力は stderr の `strata: the shared Desktop harness component is not installed; coding sessions are unavailable` です。終了コードは `5` です。
- `run` の既定 `--output` は `jsonl` です。`sessions --output json` または `sessions --json` も機械可読出力を選び、エラーは標準出力に `schema_version: 1`、`ok: false`、`error.code: 5`、`error.message` を持つ JSON として出ます。`run` は `--output` の選択肢が `jsonl` だけです。
- `--quiet` は人間向けの標準出力を抑える共通処理に渡りますが、このエラーは stderr に出るため、エラー自体は抑止されません。機械可読出力時は quiet による捕捉処理を通りません。
- 機能を実行した際のファイル・ネットワーク・プロセスへの副作用は確認できません。ここで確認できる副作用はエラー出力だけです。

## 注意点と関連文書

parser にサブコマンドが存在することは、その機能が利用可能であることを意味しません。Terminal から coding app を Strata server に接続する用途では、別コマンドの [`strata connect`](../launch/README.md) が案内されています。Terminal CLI 全体の現状は Strata の `docs/TERMINAL.md:275-277` にも記載されています。

個別 parser option の索引は [`docs/cli/README.md`](../../README.md) の `strata-terminal` 節を参照してください。`code run` と `code sessions` の概要・オプション文書は、それぞれ [run](run/README.md) と [sessions](sessions/README.md) にあります。

## 根拠

- Strata `strata_cli/cli.py:494-507` — `code`、`run`、`sessions` の parser と引数定義。
- Strata `strata_cli/cli.py:527-532` — エラーの出力先・形式と返却コード。
- Strata `strata_cli/cli.py:2162-2165` — `code` 配下すべてを未導入エラーにする dispatcher。
- Strata `strata_cli/cli.py:2223-2248` — 引数 parse 後の JSON / quiet 出力処理。
- Strata `docs/TERMINAL.md:275-277` — この revision における `strata code` の制限と `strata connect` の案内。
