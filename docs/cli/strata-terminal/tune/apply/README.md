# `strata tune apply`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune apply` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/tune_apply.py` |
| 引数 | 完了した sweep の job ID |

## 役割

`tune run` が保存した測定結果の推奨値を、対応する run configuration（`strata-<model>.json`）へ反映するコマンドです。sweep の実行だけでは設定を変更せず、apply を別の手順として実行します。保存済み profile を直接変更するコマンドではありません（`strata_cli/cli.py:1632-1638,1845-1846,1850-1855`）。

## 基本的な使い方

```sh
# 測定 job に対応する設定を自動検索して適用
strata tune apply 0123abcd

# 設定ファイルとモデルファイルを明示し、JSON で結果を受け取る
strata tune apply 0123abcd --config ./strata-model.json --model-path ./model.gguf --output json
```

job ID は 8〜64 桁の小文字16進数で、保存先の job 記録と照合されます。`--config` を省略すると、現在の作業ディレクトリ以下にある `strata-*.json` を探し、job のモデル名がファイル名に含まれる候補を優先します。一致候補がなく、候補が複数ある場合は自動選択せず、`--config` の指定を求めます（`strata_cli/cli.py:1924-1950`）。

## 実行モードと主な動作

1. state directory から job を読み込みます。`--state-dir` がなければ `STRATA_TUNE_DIR`、それもなければ標準 state directory の `tuning` が使われます（`strata_cli/cli.py:1643-1650,1710-1712`）。
2. run configuration を選び、sweep が記録したモデル digest と現在の engine・model・backend・workload・context・machine の identity を照合します。apply 時に `--model-path` を指定すると、現在のモデルファイルから identity を再計算します（`strata_cli/cli.py:1863-1903`、`strata_control/tune_history.py:48-81,99-143`）。
3. sweep が `completed` であること、適用可能な推奨があること、測定中に重大な drift がないこと、設定に実際の差分が生じることを確認します。推奨対象の flag は設定内の全出現を除いて推奨値に置き換え、その他の引数や設定フィールド、環境変数、vision 設定などは保持します（`strata_control/tune_apply.py:118-166,227-289`）。
4. 元の設定を digest 付きで退避し、application record と候補設定を state directory に記録してから、設定ファイルを一時ファイル経由で置き換えます（`strata_control/tune_apply.py:62-74,339-370`）。人間向け出力には差分、前後の digest、復元用の `strata tune rollback <application-id>` を表示します（`strata_cli/cli.py:1907-1920`）。

CLI は現在、候補設定を実際に起動して token 生成を確かめる検証関数を渡さず (`verify=None`)、設定を書き込みます。成功時にも「候補は稼働中のモデルに対して検証されていない」と表示されるため、反映後に利用する前に生成を確認してください（`strata_cli/cli.py:1900-1905,1918-1920`）。

## 主なオプション

このコマンドでは `--config`、`--model-path`、`--context`、`--state-dir`、`--output` を受け付けます。`--output` は `human`（既定）または `json` です。なお、parser には整数値を取る `--context` がありますが、現行の `_tune_apply` は `a.context` を参照せず、identity の context には sweep job の plan に記録された値を使います。したがって apply 時に指定した `--context` が照合値や設定へ反映されるとは確認できません（parser: `strata_cli/cli.py:461-470`、実処理: `strata_cli/cli.py:1868-1903`）。

sweep にモデル digest が記録されていない場合は適用を拒否します。sweep 時と apply 時でモデル digest の算出方法が異なる場合も identity が一致せず拒否され得ます。`tune run` 時に `--model-path` を与えてモデル identity を記録し、apply 時にも同じモデルを指定してください（`strata_cli/cli.py:1883-1898`、`strata_control/tune_history.py:39-45,121-143`）。

## 失敗と副作用

job が見つからない、設定が見つからない、モデル digest がない、identity を再計算できない場合はエラーとなります。未完了 job、推奨なし、重大な drift、設定との差分なし、記録済み identity との不一致なども `ApplyError` として拒否されます。人間向けエラーは stderr に `strata:` を付けて出力し、JSON モードでは `ok: false` とエラー code/message を出力します（`strata_cli/cli.py:527-532,1859-1905`、`strata_control/tune_apply.py:50-55,240-283`）。

適用時は run configuration と state directory 内の `applications/<application-id>/` に、退避した `before.json`、候補設定、application record が書き込まれます。以前の設定は `strata tune rollback` で復元できます（コマンド階層は [CLI オプション索引](../../../README.md) を参照）。ただし、apply 後に設定が編集されている場合、rollback は新しい編集を失わせないよう復元を拒否します（`strata_control/tune_apply.py:300-370,373-401`）。

## 関連文書

- [CLI オプション索引](../../../README.md) — `strata tune run`、`apply`、`rollback` の階層と option scope。
- [`strata tune` 概要](../README.md)
- [`--context`](--context.md)（parser で受理される値）
- [調査基準](../../../001_investigation.md)

## 根拠

- `strata_cli/cli.py:461-475` — `tune apply` / `rollback` の parser と引数。
- `strata_cli/cli.py:1643-1650,1708-1713` — tune state directory と dispatch。
- `strata_cli/cli.py:1850-1921` — job/config/identity の選択、実際の適用呼び出し、出力と未検証の注意。
- `strata_cli/cli.py:1924-1950` — config 自動検索と job ID の読み込み。
- `strata_control/tune_apply.py:118-166,227-289,306-370` — 設定への反映、適用条件、退避と atomic write。
- `strata_control/tune_apply.py:373-401` — rollback の競合保護。
- `strata_control/tune_history.py:48-81,99-143` — file identity と比較条件。
