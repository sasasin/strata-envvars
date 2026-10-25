# `strata tune apply --context`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の作業状態は `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune apply` |
| オプション | `--context` |
| 別名 | なし |
| 値 | 整数（`argparse` の `type=int`）。既定値は `None` |

## 役割

現行 parser は `--context` を整数値のオプションとして受け付けますが、`strata tune apply` の処理では値を読み取りません。したがって、指定しても適用対象のコンテキストや sweep の識別条件、設定ファイルの内容は変わりません。`strata tune run --context` は sweep 計画へ値を渡す別のオプションです。

## 使い方

```sh
strata tune apply <job-id> --context 8192
```

`<job-id>` は完了済み sweep の ID です。この例の `--context 8192` は整数として受理されますが、apply の結果には反映されません。コンテキストを指定して sweep を作成する場合は `strata tune run --context <整数>` を使います。

## 値と既定値

- 値は `int` に変換されます。省略時は `None` です。
- 整数への変換ができない値は parser で拒否されます。0 や負数に対する独自の範囲検証は、この引数定義にはありません。
- 値が整数として受理されても、apply 処理は `a.context` を参照しないため、値の大小による処理差はありません。

## 実行時の動作

`strata_cli/cli.py` の parser 定義は `--context` を `type=int, default=None` として登録します（`strata_cli/cli.py:461-470`）。ディスパッチ先の `_tune_apply` は job、設定ファイル、モデルと engine の identity を調べ、`tune_apply.apply_recommendation` を呼びますが、引数として `a.context` を渡しません（`strata_cli/cli.py:1850-1905`）。同関数の引数にも context はありません（`strata_control/tune_apply.py:306-310`）。

適用可否の context は、コマンドラインの `--context` ではなく、job の計画に記録された値から identity を再構成するときに使われます（`strata_cli/cli.py:1868-1879`）。sweep の recommendation が設定ファイルの `args` に反映されるかどうかは別途判定され、既存の推奨フラグを置換し、なければ追加します（`strata_control/tune_apply.py:120-166`）。この処理に `--context` は関与しません。

比較のため、同じ `cli.py` の `strata tune run --context` は `context=a.context` として sweep 計画へ渡しています（`strata_cli/cli.py:451-452, 1763-1768`）。

## 適用条件と副作用

`--context` 自体には適用条件や副作用がありません。オプションを付けても、apply が参照する job、設定ファイル、identity の照合条件は変わりません。

オプションにかかわらず apply コマンド本体は設定を変更し得ます。job が完了済みで推奨があり、重大な測定中 drift がなく、identity 等の照合を通過し、設定に変更が生じる場合に apply されます（`strata_control/tune_apply.py:227-289`）。この CLI は `verify=None` を渡すため、候補設定を実モデルで起動・生成確認せず、前の設定を state directory に保存してから JSON 設定を atomic write します（`strata_cli/cli.py:1900-1903`; `strata_control/tune_apply.py:306-370`）。

## 出力とエラー

`--context` の整数変換に失敗した場合は parser が拒否します。整数として受理された値について、context 固有の警告・エラー・出力はありません。

apply 本体では job が見つからない、設定ファイルがない、sweep の model digest がない、identity を再構成できない場合などにエラー経路へ進みます。また、推奨なし、未完了 job、identity 不一致、変更不要などは `ApplyError` として拒否されます（`strata_cli/cli.py:1859-1898`; `strata_control/tune_apply.py:240-283, 317-320`）。通常出力は設定パス、変更差分、digest の先頭、および rollback ID です。`--output json` では成功 JSON、エラー時は `ok:false` の JSON を出力します（`strata_cli/cli.py:1907-1920, 527-541`）。これらの出力・失敗経路も `--context` の値では変わりません。

## 根拠

- 索引上の配置と scope: `docs/cli/README.md:769-778`（`strata tune apply` 配下に `--context` を掲載）。
- parser 定義: `strata_cli/cli.py:461-470`。
- `tune apply` の dispatcher: `strata_cli/cli.py:1708-1713`。
- apply での context を含む identity 再構成と、`apply_recommendation` 呼び出し: `strata_cli/cli.py:1868-1905`。
- `apply_recommendation` の引数、拒否条件、設定書き換えと記録: `strata_control/tune_apply.py:227-289, 306-370`。
- 対照となる `tune run --context` の parser と利用: `strata_cli/cli.py:451-452, 1763-1768`。
