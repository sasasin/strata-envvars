# `strata tune run --model`

`strata tune run` で測定対象として記録するモデル識別子を指定します。この値は必須ですが、モデルファイルを選択したり読み込んだりする引数ではありません。

## 使い方

```sh
strata tune run --engine PATH --backend BACKEND --model MODEL
```

`MODEL` はモデルを識別する文字列です。parser には `choices`、`type`、既定値がなく、`required=True` のみが設定されています。したがって指定を省くと argparse が引数エラーにし、空文字を含む値の形式検査は行いません。短縮 alias はありません。

## 動作

CLI はこの値を `tuning.plan_tuning()` に渡し、計画の `model` フィールドにそのまま記録します。計画と実行結果は tuning job の JSON に保存されるため、値はジョブ状態・レポートに付随する識別情報になります。履歴レコードにも `model_path` 欄としてこの値が渡されますが、この欄への記録はモデルファイルの検証やハッシュ計算ではありません。

モデルのバイト列を比較用 identity に含めるには、別オプション `--model-path` が必要です。`--model-path` がない場合、計画の model digest は `None` となり、モデル内容に基づく履歴比較はできません。`--full-digests` は `--model-path` などで得るファイル identity の計算方法に関するもので、`--model` の文字列を検証したりハッシュしたりしません。

`--mode api` の場合、実際に起動する worker のモデルは `--config` の run configuration によります。ソース上、`--model` の値と設定内モデル名またはモデルファイルとの一致確認はありません。API モードを使う場合は、記録用の識別子と設定の実モデルが対応していることを利用者が確認してください。

## 既定値・検証・失敗

- 既定値はありません。指定しない場合は parser が要求引数のエラーを出します。
- 任意の文字列として受理され、Strata による追加の値検証、パス解決、モデル読込は確認できません。
- `--model` 固有の失敗経路は確認できません。ジョブの起動失敗や計測失敗は別の処理としてジョブ結果に記録されます。

## 副作用と出力

この引数自体はファイルやプロセスを操作しません。`strata tune run` 全体では候補構成の測定を実行し、ジョブ状態・レポートとチューニング履歴を保存しますが、run config / active profile は変更しません。測定結果は human または JSON 出力で返り、human 出力ではジョブ ID と `strata tune status <job>` での確認先が表示されます。推薦を設定へ適用する操作は別の `strata tune apply` です。

## 根拠

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、調査日 `2026-10-25`。作業ツリーは `main...origin/main` で変更表示なし。

- `strata_cli/cli.py:414-459` — `tune run` parser。`--model` は `required=True` の文字列引数で、値制約・型変換・default はない。
- `strata_cli/cli.py:1708-1710,1742-1768` — run 分岐から `plan_tuning()` へ値を渡す箇所。`--model-path` と `--full-digests` は別引数。
- `strata_control/tuning.py:723-768` — 計画生成。`model` は `TuningPlan.model` に格納し、identity の model は `model_path` がある場合のみファイルから生成する。
- `strata_control/tuning.py:682-712` — 履歴への記録。`plan.model` は `model_path` 欄に渡される。
- `strata_control/tuning.py:343-362` — job 状態の JSON 保存。
- `strata_cli/cli.py:1771-1786,1840-1846` — API モードは `--config` を使って worker を開始し、測定モードと別途 apply が必要なことを出力する。
