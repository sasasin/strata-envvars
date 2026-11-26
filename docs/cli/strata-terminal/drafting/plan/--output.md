# `--output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。調査時の作業ツリーは `main...origin/main` で、`git status --short --branch` に未コミット変更の表示はなかった。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting plan` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human`、`json`、`jsonl` |

## 役割

ドラフター取得計画の表示形式を選びます。`human` は人向けの文章、`json` と `jsonl` は機械向けの JSON オブジェクトを標準出力に出します。このコマンドの JSONL 指定でも計画は複数行イベントではなく単一 JSON オブジェクトです。

## 使い方

```sh
# 人向けの計画を表示
strata drafting plan --output human

# スクリプト向けに計画を JSON で取得
strata drafting plan --config ./run-config.json --output json

# jsonl も plan では単一の JSON オブジェクトを返す
strata drafting plan --family qwen --model IQ3_S --output jsonl
```

## 値と既定値

- 値は `human`、`json`、`jsonl` のいずれかで、省略時は `human` です。parser は選択肢以外を拒否します。`terminal/strata_cli/drafting_cmd.py:19-38`
- `--output` は `plan` と `fetch` の両方の parser に登録されていますが、この文書の対象である `plan` は計画を表示するだけです。`fetch` での進捗出力の違いは別コマンドの scope です。`terminal/strata_cli/drafting_cmd.py:22-38`

## 実行時の動作

parser は共通の `drafting plan` オプションとして `--output` を受け取り、実行時に `human` かどうかで表示分岐します。`json` と `jsonl` はともに machine 出力として扱われます。`terminal/strata_cli/drafting_cmd.py:19-38, 211-213`

計画作成時は、選択されたドラフティング方式、ローカルのドラフター有無、モデル・backend・対応状況などから結果を組み立てます。machine 出力には `schema_version: 1` と `ok: true` に加え、取得要否 (`needed`)、状態 (`ready`)、サイズ (`gb`)、選択 (`choice`)、ドラフター名 (`drafter`)、説明などを含めて JSON 化し、標準出力へ一度出します。human 出力は通常 `result["text"]`、計画上の注記がある場合には `result["line"]` を出します。`terminal/strata_cli/drafting_cmd.py:240-266`

Hy4-Flash または Inkling-2-Mini の内蔵 drafter と判定された場合は、取得不要の計画を返します。この特別経路でも `json` と `jsonl` は JSON オブジェクト、`human` は説明文です。`terminal/strata_cli/drafting_cmd.py:211-233`

計画本体は `drafting_fetch.plan` を呼び、既存 pack の準備状況や必要サイズ、VRAM 見積もり等を計画結果に含めます。`plan` 分岐は `ensure_for` に進まないため、ここで drafter をダウンロード・pack する処理は行いません。`terminal/strata_control/drafting_fetch.py:68-88`、`terminal/strata_cli/drafting_cmd.py:247-266, 267-283`

## 適用条件と副作用

このオプションは `strata drafting plan` の出力形式に作用します。設定ファイルや環境変数との優先順位はありません。計画作成では設定ファイルやローカル状態を読み、hardware・installed engine・ドラフターの状態を調べることがありますが、`plan` 自体は取得処理へ進みません。設定ファイルが読み取れない場合 `_inputs` は空設定にフォールバックするため、意図したモデルの計画にならない可能性があります。`terminal/strata_cli/drafting_cmd.py:101-120, 247-266, 267-283`

## 出力とエラー

- `human`: 取得計画の説明文を標準出力に表示します。
- `json` / `jsonl`: `schema_version` と `ok` を含む単一 JSON オブジェクトを標準出力に表示します。plan 経路では JSON Lines のイベント列にはなりません。`terminal/strata_cli/drafting_cmd.py:247-266`
- 許可値以外は argparse の choices 検証で拒否されます（標準の argparse エラー経路）。この parser で choices を定義している箇所は `terminal/strata_cli/drafting_cmd.py:38` です。

調査した `plan` の出力分岐には、計画結果を JSON として返す成功経路が確認できました。計画内部で起きる全ての例外の標準出力・標準エラー形式や終了コードは、このオプションの処理だけからは特定できないため記載していません。

## 根拠

- `terminal/strata_cli/drafting_cmd.py:19-38` — `plan` と `fetch` の parser 定義、`--output` の選択肢・既定値。
- `terminal/strata_cli/drafting_cmd.py:211-233` — machine 出力判定と内蔵 drafter の plan 出力。
- `terminal/strata_cli/drafting_cmd.py:240-266` — DFlash2 の plan 結果の組み立て、JSON/human の出力分岐。
- `terminal/strata_cli/drafting_cmd.py:267-305` — `fetch` の分岐と取得処理。plan 出力と取得処理の境界確認に使用。
- `terminal/strata_control/drafting_fetch.py:68-88` — plan が返すローカル準備状況・サイズ・説明情報。
- `docs/cli/README.md:337-347` — `strata drafting plan` の階層と対象 option の索引登録。
