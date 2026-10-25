# `strata code --resume`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の状態は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata code` |
| オプション | `--resume` |
| 別名 | なし |
| 値 | 必須の文字列1個。型・形式・選択肢の検証はありません。 |

## 役割

parser は `--resume` に文字列を受け取る形を定義しています。しかし `strata code` の処理では値を実際に使う箇所がなく、セッション再開の動作は確認できません。`strata code` 自体も shared Desktop harness が未導入として終了するため、現在このオプションで利用可能な効果はありません（`strata_cli/cli.py:494-498, 2162-2164`）。同じ `--resume` でも `strata models move` は別 parser の独立した真偽値オプションです（`strata_cli/cli.py:163-164`）。

## 使い方

parser が受理する形式は次のとおりです。

```sh
strata code --resume SESSION_ID
```

これは構文の例であり、`SESSION_ID` の書式やセッション再開を保証するものではありません。現行 dispatch は常に利用不可エラーを返します。

## 値と既定値

- 値を1つ取ります。省略時は `argparse` の既定値 `None` です（`strata_cli/cli.py:496`）。
- `type`、`choices`、独自 validation の指定がないため、CLI 層では値の形式を検証しません（`strata_cli/cli.py:494-498`）。
- 空文字列など値の境界や意味を検査する後続処理はありません。実際の処理に使われていないため、セッション ID の仕様はこの checkout から確認できません。

## 実行時の動作

`--resume` は `strata code` parser に置かれており、`run` / `sessions` の各サブコマンド parser ではなく親コマンドの引数です（`strata_cli/cli.py:494-507`）。ただし、`_run()` は `a.command == "code"` のとき、`code_command` や `a.resume` を分岐条件にせず、shared Desktop harness 未導入のエラーを返します（`strata_cli/cli.py:2119-2165`）。

この parser には `--workspace` と `--quiet` もありますが、同じ dispatch では値を使いません。`code run` と `code sessions` の parser 宣言があっても、現行 checkout の `_run()` から個別処理へ到達する経路は確認できません（`strata_cli/cli.py:495-507, 2162-2164`）。

## 適用条件と副作用

`strata code` の呼び出しは harness の有無を判定する処理へ進まず、固定の利用不可エラーで終了します。したがって `--resume` によるファイル変更、ネットワーク通信、子プロセス起動、セッション状態の読込は確認できません（`strata_cli/cli.py:2162-2164`）。

## 出力とエラー

- 通常の人間向け出力では、標準エラーに `strata: the shared Desktop harness component is not installed; coding sessions are unavailable` を出し、終了コード `5` を返します（`strata_cli/cli.py:527-532, 2162-2164`）。
- `output` が `json` または `jsonl` の場合は標準出力に `schema_version: 1`、`ok: false`、`error.code: 5` とメッセージを含む JSON を出します。`strata code run` は `--output jsonl`、`strata code sessions` は `--output human|json` を定義しています（`strata_cli/cli.py:499-507, 527-532, 2162-2164`）。
- parser が認識しない引数は `main()` の引数解析で usage とエラーになり、通常は argparse の終了コード `2` です（`strata_cli/cli.py:2223-2231`）。

## 根拠

- parser 定義・値の受理: `strata_cli/cli.py:494-507`
- 同名だが別スコープの `strata models move --resume`: `strata_cli/cli.py:163-164, 668-705`
- `code` の dispatch と固定エラー: `strata_cli/cli.py:2119-2165`
- エラー出力形式・終了コード: `strata_cli/cli.py:527-532`
- 引数解析の失敗経路: `strata_cli/cli.py:2223-2231`
- 調査時の revision / checkout 状態: `git rev-parse HEAD` は `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、`git status --short --branch` は `## main...origin/main`。

調査範囲はこの commit の Terminal CLI ソースです。Release 配布物や別 revision の挙動は照合していません。`--resume` の実行時参照は `strata_cli` 内で見つからず、CLI help は実行していません。
