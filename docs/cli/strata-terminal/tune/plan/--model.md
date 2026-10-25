# `--model`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune plan` |
| オプション | `--model` |
| 別名 | なし |
| 値 | 必須の文字列。選択肢・形式・空でないことの検証は parser に定義されていない |

## 役割

計画が対象とするモデルの識別子を、生成される tuning plan に記録します。`--model` の値は plan の `model` 欄にそのまま渡されます。モデルを検索・解決したり、モデルファイルを読み込んだりする処理には使われません。根拠: `strata_cli/cli.py:398-412`, `strata_cli/cli.py:1715-1721`, `strata_control/tuning.py:762-767`。

## 使い方

```sh
strata tune plan --engine /path/to/strata --backend cuda --model example-model
```

`--engine` と `--backend` も必須です。`--model` は `strata tune run` にも別途定義されていますが、この文書の対象は `strata tune plan` の parser です。根拠: `strata_cli/cli.py:398-412`, `strata_cli/cli.py:414-419`。

## 値と既定値

値は1つの文字列で、省略できません。parser は `required=True` のみを指定しており、choices や追加の文字列 validation はありません。したがって CLI 側ではモデル名の実在性や表記を確認しません。既定値はありません。根拠: `strata_cli/cli.py:402`。

## 実行時の動作

CLI はこの文字列を `tuning.plan_tuning` の `model` 引数に渡し、返される plan に格納します。plan 生成は計測を行いません。エンジンの flag 一覧を得るため、指定したエンジンを `--help` 付きで起動し、stdout と stderr の出力からフラグを読み取ります。起動できない場合やフラグを抽出できない場合は一覧を未知として扱い、backend ごとの静的 dimension 表で計画します。根拠: `strata_cli/cli.py:1715-1723`, `strata_control/tuning.py:205-224`, `strata_control/tuning.py:723-768`。

この parser には `--model-path` がありません。plan の content identity に使う model file は `None` となり、モデル digest・サイズ・digest 方式は未確定です。従って `--model` の文字列だけでは、異なる重みを区別する content identity にはなりません。一方、engine binary の identity はファイルから計算されます。根拠: `strata_cli/cli.py:398-412`, `strata_cli/cli.py:1717-1721`, `strata_control/tuning.py:753-767`, `strata_control/tune_history.py:99-118`。

`--backend` は `metal`、`cuda`、`hip`、`sycl`、`cpu` から選択されます。探索項目は backend とエンジンの flag 一覧に基づいて含める・除外する判断がされ、`--model` による項目変更はありません。根拠: `strata_cli/cli.py:400-404`, `strata_control/tuning.py:151-174`。

## 適用条件と副作用

このオプションは `strata tune plan` にのみ適用されます。通常の成功経路ではモデルの起動・計測はせず、active profile や tuning 状態ファイルも変更しません。エンジンの `--help` プロセスを起動し、engine file identity を確認するためファイルを読みます。エンジン flag を取得できないときはその旨を plan に記録して静的表へ fallback します。根拠: `strata_cli/cli.py:1715-1738`, `strata_control/tuning.py:205-224`, `strata_control/tuning.py:734-760`。

## 出力とエラー

成功時は人間向け出力に engine、backend、objective、上限、探索項目、除外理由を表示して終了コード `0` を返します。`--output json` では plan を含む JSON を出力します。plan は表示用の提案で、適用は別操作です。根拠: `strata_cli/cli.py:1722-1739`, `strata_cli/cli.py:535-542`。

`--model` を省略すると argparse が usage/error を出して終了コード `2` になります。`--backend` の値が choices 外の場合も同様です。エンジン指定を `component:strata-engine` にしたとき、対応する engine component が見つからなければ `ProfileError`（終了コード `5`）となり、JSON mode では `ok: false` と error 情報を返します。根拠: `strata_cli/cli.py:398-412`, `strata_cli/cli.py:1621-1629`, `strata_cli/cli.py:2166-2173`。

## 根拠

- parser と必須値: `strata_cli/cli.py:398-412`
- 値の引き渡し、出力: `strata_cli/cli.py:1715-1739`
- エンジン flag の取得と fallback 条件: `strata_control/tuning.py:205-224`, `strata_control/tuning.py:723-768`
- plan の model 欄と content identity: `strata_control/tuning.py:753-767`, `strata_control/tune_history.py:99-118`
- 共通エラー出力: `strata_cli/cli.py:527-542`, `strata_cli/cli.py:2166-2188`
