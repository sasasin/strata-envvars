# `--workspace`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata code` |
| オプション | `--workspace` |
| 別名 | なし |
| 値 | 任意の文字列。parser に型変換・選択肢・既定値の指定はない（省略時 `None`）。 |

## 役割

`strata code` の共有 Desktop harness 用 parser に workspace の値を渡すオプションとして宣言されています。ただし、現行実装では `strata code` の全呼び出しが harness 未導入エラーで終了し、`--workspace` の値を読み取る処理はありません。そのため、現在は値を受理するだけで workspace の選択や検証には使われません（`strata_cli/cli.py:494-498,2162-2164`）。

## 使い方

```sh
strata code --workspace ./project
```

この構文は parser に受理されますが、現行実装では coding session は開始されません。後述のエラーが返ります。

## 値と既定値

- 値は必須の文字列です。`argparse` の `add_argument("--workspace")` には `type`、`choices`、`required`、`default` が指定されていないため、省略時の値は `None` です（`strata_cli/cli.py:494-498`）。
- ディレクトリの存在・形式・空文字列を検査する Strata 側の処理は確認できません。parser に値を指定しなければ起動時処理へ進みますが、指定値はそこで参照されません（`strata_cli/cli.py:2162-2164`）。
- 同じ `strata code` parser に対する重複指定の独自処理はありません。

## 実行時の動作

`--workspace` は `code` parser 自身に登録され、その後に `run` と `sessions` の subparser が定義されています。従ってこのオプションのスコープは `strata code` であり、例えば `strata code --workspace ./project run ...` のように subcommand より前に置きます。`run` の parser には `--prompt-file`、`--policy` 等が定義されていますが、`--workspace` は定義されていません（`strata_cli/cli.py:494-507`）。

parser 後の dispatch は `a.command == "code"` に対し、subcommand や `a.workspace` の値を調べずに固定エラーを返します（`strata_cli/cli.py:2162-2164`）。従って、値が有効なパスかどうかにかかわらず workspace は選択されず、セッション再開や `run` / `sessions` の処理も実行されません。`--resume` も同じ parser にありますが、この経路では参照されません（`strata_cli/cli.py:495-498,2162-2164`）。

## 適用条件と副作用

このオプションによるファイルアクセス、作成、上書き、削除、ネットワーク接続、子プロセス起動は現行 dispatch では発生しません。`strata code` が常にエラーで早期終了するためです（`strata_cli/cli.py:2162-2164`）。

## 出力とエラー

parser を通過した `strata code` 呼び出しは終了コード `5` を返します。出力先と形式は、サブコマンドの `--output` によって異なります。

```text
strata: the shared Desktop harness component is not installed; coding sessions are unavailable
```

この分岐は `_error(..., 5, machine)` を呼びます。`strata code` 単独では JSON 用 `output` 属性がないため、通常の `strata: ...` 形式を stderr に出します。`code run` は既定 `jsonl`、`code sessions` は既定 `human` で、`--output json` を選んだ場合も `_error` は JSON エラーを stdout に出力します（parser: `strata_cli/cli.py:499-507`、出力実装: `strata_cli/cli.py:527-532,2162-2164`）。`--workspace` に値を付けず実行するなど parser が引数を解釈できない場合は、dispatch より前に `argparse` の usage/error 経路となり、終了コード `2` です（`strata_cli/cli.py:2223-2231`）。

## 根拠

- parser 定義、`run` / `sessions` とのスコープ: `strata_cli/cli.py:494-507`
- エラー表示と戻り値: `strata_cli/cli.py:527-532`
- 全 `code` 呼び出しに対する固定 dispatch: `strata_cli/cli.py:2162-2164`
- 引数解析と parser エラー経路: `strata_cli/cli.py:2223-2231`
- 現行利用可否の補足記述: `docs/TERMINAL.md:275-277`
