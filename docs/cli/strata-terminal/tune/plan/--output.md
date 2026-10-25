# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune plan` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

計画表示の出力形式を選びます。`human` は読みやすい複数行の要約、`json` は `plan` を含む JSON オブジェクトを標準出力に出します。調査した parser にはファイル出力先を指定する機能はありません。

## 使い方

```sh
strata tune plan --engine /path/to/strata-engine --backend cpu --model example --output json
```

`--engine`、`--backend`、`--model` は必須です。例では出力ファイルを指定せず、結果を標準出力へ出します。

## 値と既定値

- 有効値は `human` と `json` のみで、既定値は `human` です。
- `--output` は値を一つ取ります。値は `choices` によって検証されるため、別の値は argparse が拒否します。
- 同じオプションの複数指定時の特別な処理はありません。argparse の通常の単一値引数として扱われ、後に指定した値が残ります。

## 実行時の動作

コマンド本体は `a.output == "json"` で machine 出力を選びます。`json` の場合、計画生成後に `_success({"plan": plan.to_dict()}, machine=True)` を呼び、標準出力へ `schema_version: 1`、`ok: true`、`plan` を含む JSON を1行出力します。`human` の場合は engine、backend、objective、repeats、探索上限、探索対象と除外理由を標準出力へ表示します。計画の結果を適用する操作はこのコマンドでは行いません。

このオプションは計画の探索条件や計算内容を変更しません。値はエラー出力の形式にも使われ、`json` では捕捉されたエラーを JSON 形式にします。

## 適用条件と副作用

`strata tune plan` の表示形式だけに適用されます。オプション自体によるファイル作成・上書き・削除やネットワーク処理はありません。計画作成では指定 engine のフラグ情報を調べ、読めない場合は静的テーブルを使ったことを計画に記録します。したがって、engine ファイルへのアクセスなど計画生成そのものに伴う処理はありますが、`--output` の値による違いではありません。

## 出力とエラー

- `human` は概要と探索対象・除外理由を標準出力に表示し、成功時は終了コード `0` です。
- `json` は成功時に `_success` が JSON を標準出力へ出し、終了コード `0` を返します。
- 未対応値や値の欠落など parser エラーは argparse の usage/error 経路で標準エラーに表示され、終了コード `2` になります。
- 実行時の `ValueError` は既定で終了コード `2`、`OSError` は `6` で `_error` に渡されます。`json` 選択時は `_error` が `schema_version: 1`、`ok: false`、`error` を含む JSON を出力し、それ以外は `strata: ...` を標準エラーへ出します。個別の engine 状態などで追加の失敗経路がある場合は、それぞれの例外元に従います。

## 根拠

- parser、値の選択肢と既定値、必須引数: `strata_cli/cli.py:395-412`。
- machine 出力判定、計画生成と `--output` による表示分岐: `strata_cli/cli.py:1632-1642`、`strata_cli/cli.py:1715-1739`。
- engine path の解決: `strata_cli/cli.py:1621-1629`。
- JSON 成功・失敗の stdout/stderr と戻り値: `strata_cli/cli.py:527-542`。
- argparse から dispatcher への接続、標準的な例外出力: `strata_cli/cli.py:2217-2231`、`strata_cli/cli.py:2156-2158`、`strata_cli/cli.py:2166-2193`。
- 計画生成が計測を行わず、engine flag inventory と hold / dimensions を計画へ反映する箇所: `strata_control/tuning.py:723-768`。

索引との照合では、対象の `--output` は `strata tune plan` 配下に掲載されています。一方、同じ parser にある `--trials`（`strata_cli/cli.py:405`）は索引の同コマンド節に見当たりません。索引はこの依頼の編集対象外のため変更していません。
