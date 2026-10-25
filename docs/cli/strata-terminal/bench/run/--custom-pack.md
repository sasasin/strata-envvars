# `--custom-pack`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--custom-pack` |
| 別名 | なし |
| 値 | 任意の文字列 `TEXT`。値の形式・長さの検証はない |

## 役割

標準ベンチマーク結果に、利用者が準備済みパックまたはカスタム expert profile の説明を記録します。ベンチマークの workload や engine 設定を変更するオプションではなく、結果の provenance（申告情報）です。

## 使い方

```sh
strata bench run --url http://127.0.0.1:8000 --custom-pack 'expert profile: my prepared pack'
```

`--profile` または `--url` のどちらかを指定する必要があります。通常のサブコマンド既定 suite は `standard-v1` です。コマンドは実際にサーバーへベンチマーク要求を送るため、この例はそのサーバーが利用可能な環境で実行してください。

## 値と既定値

- `TEXT` は1つの引数値として受け取ります。省略時は `None`（未申告）です。
- `argparse` の文字列値であり、列挙値やパスとしての検証、空文字列の拒否、前後空白の除去はありません。値を省略した場合は parser が引数エラーにします。
- 同じオプションを複数回指定した場合の専用処理はありません。通常の `argparse` の単一値引数として最後に解析された値が namespace に入ります。

## 実行時の動作

標準 suite では `a.custom_pack` が `declared` に入り、`bench_standard.run()` に渡されます。結果の `model.custom_pack` にこの文字列がそのまま保存されます。値はモデルファイルや server から検出・検証されるものではなく、利用者の申告です。

未指定の場合、結果 JSON の `model.custom_pack` は `null` となり、`missing` マップに `/model/custom_pack` と「操作者が custom pack または expert profile を申告していない」旨の理由が記録されます。この欠落だけで `run.status` を nonconforming にする分岐はありません。

このオプションは `standard-v1` 向けです。parser 上は `strata bench run` 共通の位置に宣言されていますが、`--suite` に serving suite を選んだ実行経路では値が `bench.run()` へ渡されず、結果にも反映されません。serving suite の選択肢と既定値は parser で定義されています。

## 適用条件と副作用

標準 suite の結果のモデル情報にのみ影響します。オプション値自体はネットワーク通信、ファイル操作、engine 起動を行いません。ただしベンチマーク実行では server に接続し、結果ディレクトリに `results.json` 等を書き込みます。この注記は標準結果 JSON に保存され、標準 suite の Markdown レポート本文には個別表示されません。

## 出力とエラー

標準 suite の実行が成功すると `results.json` の `model.custom_pack` に値を記録します。`--output json` の場合も CLI の標準出力は `ok`、結果パス、status、quality、summaries を含む実行サマリーであり、このフィールド自体は結果ファイル側にあります。人向け出力は整形済みベンチサマリーと結果パスです。

値に対する独自 validation error はありません。ベンチ実行中の server/API エラー、報告書 validation エラー、ファイル操作エラー等は通常の `strata bench run` の失敗経路となり、エラーコードとメッセージを返します。結果の実行状態が失敗相当の場合は終了コード `6` です。

## 根拠

- `strata_cli/cli.py:293-300` — `bench run` parser、必須の `--profile` / `--url`、`standard-v1` 既定値。
- `strata_cli/cli.py:322-334` — 標準 suite の option group と `--custom-pack TEXT` 宣言。help は「準備済みパックまたはカスタム expert profile の説明」と定義。
- `strata_cli/cli.py:1183-1188` — `standard-v1` だけが `_bench_standard()` へ分岐する。
- `strata_cli/cli.py:1237-1252` — 標準 suite 用の validation。`--custom-pack` に関する検証はなく、固定 workload 用 option と load timeout の検証を行う。
- `strata_cli/cli.py:1273-1278` — raw command と申告情報を準備し、`a.custom_pack` を `declared` へ渡す。
- `strata_cli/cli.py:1302-1305` — `bench_standard.run()` 呼び出しへ `declared` を渡す。
- `strata_cli/bench_standard.py:818-823` — `declared` を `facts.model()` へ渡す。
- `strata_cli/bench_facts.py:422-442` — `declared.custom_pack` を model block に格納し、未指定時は `/model/custom_pack` の欠落理由を登録。
- `strata_cli/bench_standard.py:928-960` — `model` block を結果へ格納し、null 値の理由を `missing` に記録、結果 JSON と Markdown を新規作成。
- `strata_cli/bench_standard.py:1188-1193` — Markdown の Model and configuration 欄。表示する model 値に `custom_pack` は含まれない。
- `strata_cli/cli.py:1312-1328` — 結果出力と終了コード（完了なら `0`、失敗状態なら `6`）。
- `strata_cli/cli.py:527-532`, `2166-2188` — CLI の一般エラー表示と `ValueError` / `OSError` / `ClientError` の捕捉。

確認範囲は上記 commit の checkout にある Terminal CLI parser と標準ベンチ実装です。実行は行っていません。serving suite については、共通 parser から option を受理しても、その値が実行関数へ渡されないことをソースで確認しました。
