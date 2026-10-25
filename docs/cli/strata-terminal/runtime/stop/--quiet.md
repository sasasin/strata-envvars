# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime stop` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

人向けの通常出力を抑制します。`runtime stop` の停止動作や停止対象の選択には影響しません。

## 使い方

```sh
strata runtime stop --profile office --quiet
```

JSON 結果が必要な場合は `--output json`（または alias の `--json`）を指定します。JSON 出力は `--quiet` でも抑制されません。

## 値と既定値

フラグを付けると真になり、値は不要です。省略時は `quiet` 属性が設定されず、共通処理で偽として扱われます。runtime の one-shot parser 群には `--quiet` が共通に追加されています。

## 実行時の動作

人向け出力モードでは、CLI は stdout を一時捕捉して処理を実行します。終了コードが 0 なら捕捉した stdout を表示しません。`runtime stop` は通常、結果の状態を stdout に表示するため、成功時にはその行が隠れます。JSON 出力モードではこの捕捉を行わず、通常の JSON 結果を出力します。

このフラグは `runtime stop` の drain・停止処理には渡されません。停止コマンドは引き続き runtime 管理層を通じて対象インスタンスを停止します。

## 適用条件と副作用

`--quiet` 自体は出力の扱いだけを変え、ファイルやプロセスを変更しません。実際の停止操作には通常どおり副作用があります。停止対象は `--profile` で指定し、停止を待つ上限は `--wait` で指定します。

quiet 時にコマンドが失敗し、処理が stdout に人向け結果を出していた場合、その捕捉内容は stderr に再掲されます。stderr に直接書かれたエラーはそのまま表示されます。捕捉内容が上限を超えた場合は、省略を示すメッセージも stderr に出ます。

## 出力とエラー

- 成功した人向け実行: 捕捉した stdout を表示しません。
- 失敗した人向け実行: 捕捉した stdout を stderr に移して表示します。実行時エラーの終了コードは通常の処理結果を維持します。
- `--output json` / `--json`: JSON 出力を抑制しません。
- 引数の型・選択肢・停止待ち時間など、`--quiet` 以外の検証やエラー条件は変わりません。

## 根拠

- 索引 `docs/cli/README.md:427-439` — `strata runtime stop` の階層と `--quiet` 文書リンク。
- `strata_cli/cli.py:226-232` — `runtime stop` parser のオプション定義。
- `strata_cli/cli.py:508-515` — runtime の one-shot parser 群へ `--quiet` と `--json` を追加する処理。`--quiet` は値なしの `store_true`。
- `strata_cli/cli.py:1330-1373` — runtime 結果の JSON / 人向け表示、終了コードの処理。停止結果の人向け表示はこの経路で stdout に出る。
- `strata_cli/cli.py:2232-2247` — JSON モードでは quiet 捕捉を迂回し、人向け quiet モードでは stdout を捕捉し、失敗時に stderr へ再掲する共通処理。
- `strata_control/management.py:271-291` — stop wait の検証、任意の owner / instance 照合、停止処理の呼び出し。
- `strata_control/runtime.py:602-640` — 停止計画と停止 RPC、成功後の所有ホスト待機。
