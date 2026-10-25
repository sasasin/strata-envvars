# `--context`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--context` |
| 別名 | なし |
| 値 | 整数（`argparse` の `int` 変換）。既定値は `None`（省略） |

## 役割

測定対象のコンテキスト長をチューニング結果の識別情報に記録します。指定値は測定条件として記録され、同じエンジン・モデル等でも異なるコンテキストで得た履歴を比較対象から区別します。このオプション自身はエンジンや API worker にコンテキスト長を設定しません。

## 使い方

```sh
strata tune run --engine /path/to/strata --backend cuda --model example-model \
  --model-path /models/example.gguf --context 32768
```

`--engine`、`--backend`、`--model` は `run` の必須引数です。上のパスとモデル名は書式例です。実際の測定に使うエンジン、モデル、コンテキストに合わせてください。

## 値と既定値

- `--context` の直後の値は Python 整数に変換されます。`32768` のような整数を指定します。小数や整数でない文字列は `argparse` が拒否します。
- 省略時は `None` が渡され、識別情報にも `null` として記録されます。
- `run` parser と `plan_tuning` への経路に、正数・最小値・最大値を検証する処理は見当たりません。したがって parser 上は `0` や負数も整数として受理されます。ただし、それらを実コンテキスト長として測定する保証はソースから確認できません。
- このオプションの重複指定を独自に検証する処理はありません。`argparse` の通常の単一値引数として扱われます。

## 実行時の動作

CLI は値を `tuning.plan_tuning(..., context=a.context)` に渡します。そこで値は `TuningPlan.context` に保持され、エンジン、モデル、backend、workload、マシン情報とともに比較用 identity の `context` フィールドへ入ります。履歴比較では context が異なると「異なる context」と判定されます。そのため、値は測定結果の文脈化と過去結果との比較可否に作用します。

一方、測定 workload は `--prompt-tokens`、`--max-new`、固定 seed、temperature から別途作られます。`context` は workload や探索 candidate の engine 引数に追加されません。`--mode api` の実測 worker は `--config` で起動されるため、その worker の実コンテキスト設定は構成ファイル側に依存します。`--context` と構成ファイル内の値が異なる場合に警告・補正する処理は確認できません。

## 適用条件と副作用

- 対象は `strata tune run` の parser だけです。同じ文字列の `strata tune apply --context` は別 parser・別コマンドのオプションであり、この文書の対象外です。
- `--context` 自体がファイルやプロセスを操作することはありません。`run` は plan を含む job 状態を `job.json` に保存し、完了時に履歴を追記します。指定した値は job の plan と比較 identity に残ります。
- `--context` の値は既定の人間向け進捗表示には個別表示されません。JSON 出力では job の plan に含まれます。
- `--mode api` を使う場合は別途 `--config` と `--api-expect` が必要です。欠けると測定開始前にエラーコード 2 で終了します。これは `--context` 固有の条件ではありません。

## 出力とエラー

- 整数へ変換できない値は `argparse` の引数エラーとなり、usage とエラーメッセージが stderr に出て終了コード 2 になります。
- 有効な整数について、context 固有の範囲エラーや警告は実装されていません。
- 通常の人間向け出力は sweep の状態・測定結果等を stdout に表示し、context を単独では表示しません。`--output json` は job を含む JSON を stdout に出力します。
- `run` は job データを `job.json` に保存し、履歴ストアへ測定結果を記録します。したがって、この引数は保存された比較キーに影響しますが、既存の serving profile を変更するものではありません。

## 根拠

- `strata_cli/cli.py:414-459` — `strata tune run` parser と `--context` の `type=int, default=None` 定義。
- `strata_cli/cli.py:1708-1709,1742-1768` — `run` dispatch と `a.context` の `plan_tuning` への転送。workload の構築は `1763-1770`。
- `strata_control/tuning.py:295-301,723-768` — plan が context を保持し、比較 identity に含める処理。値の範囲検証はこの関数内にありません。
- `strata_control/tune_history.py:99-118,121-143` — 比較キーの context と、異なる context を非比較理由にする処理。
- `strata_control/tuning.py:339-362,682-710` — `job.json` の保存と完了時の履歴記録。
- `strata_cli/cli.py:1771-1786,1805-1847` — API mode の必須条件、測定モード選択、および人間向け/JSON 出力。
- `strata_cli/cli.py:527-532` — 通常エラーの stderr 表示と終了コード返却。
