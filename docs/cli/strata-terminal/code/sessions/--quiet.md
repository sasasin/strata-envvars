# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata code sessions list` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない boolean flag。指定すると `True`。 |

## 役割

人向けの情報出力を抑えるための共通オプションです。`sessions` parser にも登録されています。ただし、調査対象 revision の `strata code` は共有 Desktop harness が未導入として実行を拒否するため、この checkout では成功時の session 一覧表示に対する効果を確認できません。

## 使い方

```sh
strata code sessions list --quiet
```

`strata code` parser にも `--quiet` があるため、サブコマンドより前に `strata code --quiet sessions list` と置く形式も parser 上は受理されます。

## 値と既定値

値は不要です。指定時に真となり、省略時は偽です。同じ flag を繰り返しても真のままです。`sessions` の one-shot parser 群への登録では `default=argparse.SUPPRESS` が指定されており、親の `strata code` parser で設定された値を子 parser の既定値で上書きしない構成です。値を付けた形式はこの flag の構文ではなく、未知引数として parser エラーになります。

## 実行時の動作

`strata code sessions` は位置引数 `action` に `list` のみを受け付け、出力形式は `--output human`（既定）または `--output json` です。`--json` は `--output json` の alias です。

人向け出力モードで `--quiet` が真の場合、CLI の共通処理は `_run()` の標準出力を一時捕捉します。処理が失敗し、捕捉した標準出力があれば stderr に再掲し、捕捉量が上限を超えていた場合は省略通知も stderr に出します。JSON または JSONL 出力ではこの quiet 捕捉処理を通らず、機械可読出力を保持します。

ただし、現行ソースの `_run()` は `code` コマンドを共有 Desktop harness 未導入として即時にエラーにします。従ってこの revision の `sessions list` は、`--quiet` の値にかかわらず成功して session を列挙しません。

## 適用条件と副作用

この option 自体にファイル、ネットワーク、プロセス、session データを変更する副作用はありません。人向け出力時の標準出力抑制は `main()` の共通処理によるものです。JSON 出力と、stdout ではなく stderr に直接書かれるエラーには抑制が及びません。

## 出力とエラー

- 現行の `strata code` 実行分岐は「shared Desktop harness component is not installed; coding sessions are unavailable」というエラーを返し、終了コード `5` です。
- 既定の human 出力では `_error()` が `strata: ...` を stderr に出します。`--quiet` は stderr を捕捉しないため、このエラーは表示されます。
- `--json` または `--output json` を指定した場合は、エラーオブジェクトを JSON で stdout に出します。`--quiet` を併用しても JSON は抑制されません。
- `action` に `list` 以外を指定する、または flag に値を渡すなど parser 構文に合わない入力は argparse の usage/error 経路となります。調査では help を含む CLI を実行していません。

## 根拠

- parser 定義: `strata_cli/cli.py:494-515`。`code` 親 parser と `sessions` を含む one-shot parser 群に `--quiet` を登録し、`sessions` の action と出力形式も定義しています。
- quiet の適用と JSON 例外: `strata_cli/cli.py:2232-2247`。JSON 出力時は `_run()` に直行し、人向け quiet 時は stdout のみを捕捉します。
- `code` の実行分岐: `strata_cli/cli.py:2162-2164`。共有 Desktop harness が未導入としてエラーコード `5` を返します。
- エラーの出力先: `strata_cli/cli.py:527-532`。human エラーは stderr、machine エラーは JSON stdout に出力します。

確認範囲は上記 commit の checkout に含まれる `strata_cli/cli.py` です。共有 Desktop harness が導入された配布構成での `sessions list` 実装と、その成功時出力への `--quiet` の効果は、この checkout のソースから確認できません。
