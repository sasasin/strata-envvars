# `strata drafting plan --mode`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting plan` |
| オプション | `--mode` |
| 別名 | なし |
| 値 | `auto`、`mtp`、`dflash2`、`off` のいずれか |

## 役割

`--mode` は `strata drafting plan` がどの推測ドラフター選択で必要ファイルや実行可否を計画するかを指定します。run config を渡した場合は、その `drafting` 設定をコマンドライン値で上書きします。省略時は run config の選択を使い、設定がなければ `auto` 相当として扱われます。計画結果では指定した選択と、モデル・backend・カード・ファイル状態を踏まえた実際の drafter が区別されます。

## 使い方

```sh
# run config の設定ではなく Auto の選択で計画する
strata drafting plan --config ./strata-model.json --mode auto

# DFlash2 を選択した場合の計画を確認する
strata drafting plan --config ./strata-model.json --mode dflash2

# run config をまだ作っていない場合は family と model を指定して計画する
strata drafting plan --family qwen --model IQ3_S --mode mtp
```

## 値と既定値

- parser が受理する値は `auto`、`mtp`、`dflash2`、`off` です。別の値は argparse の choices 検証で拒否されます（`terminal/strata_cli/drafting_cmd.py:24-30`、選択肢の定義は `terminal/strata_control/drafting.py:37-40`）。
- この引数自体の既定値は未指定（`None`）です。未指定なら run config の `drafting` を参照し、それもない場合は `normalize()` が `auto` を既定として使います（`terminal/strata_cli/drafting_cmd.py:101-120`、`terminal/strata_control/drafting.py:882-885`）。
- `--config` が指定されても読み込みに失敗した場合、現行実装は例外を捕捉して空設定として続行します。その場合 `--mode` 未指定なら `auto` 相当になります（`terminal/strata_cli/drafting_cmd.py:101-120`）。
- `--mode` は `plan` と `fetch` の両 parser に同じ choices で登録されています。本書は索引に記載された `plan` スコープを扱います（`terminal/strata_cli/drafting_cmd.py:19-38`）。

## 実行時の動作

- `auto` は常に同じ drafter を意味するわけではありません。モデル・backend・カード別の既定や DFlash2 の実行対応を評価し、選択結果は MTP または DFlash2 になります。`mtp` は MTP を選択し、`off` は drafter を無効にします。`dflash2` を指定しても、対応モデルでない・engine/backend が対応しない場合など、計画上の実効 drafter は MTP または off になり得ます（`terminal/strata_control/drafting.py:1521-1545`、`1548-1587`）。
- run config に `mtp: false` があり、選択が `auto` なら `off` に補正されます。また config の split engine が起動を担うと予測され、`--no-split` がない場合、`auto` または `mtp` は split 用の `mtp` 計画へ切り替わります（`terminal/strata_cli/drafting_cmd.py:117-125`）。
- 計画は選択値に基づき、drafter の必要性・準備状況、MTP 層の必要性、選択結果、支援状況をまとめます。人向け出力または JSON を標準出力へ返し、`plan` 分岐では終了コード 0 で戻ります（`terminal/strata_cli/drafting_cmd.py:240-266`）。`plan` はダウンロード処理を呼ばず、設定ファイルも書き換えません。
- Hy4-Flash と Inkling-2-Mini はモデルファイルに drafter が組み込まれている特別経路です。この経路では `plan` は別個のダウンロード不要と報告し、`--mode off` のときだけ `choice` を off、それ以外の受理値では auto として出力します（`terminal/strata_cli/drafting_cmd.py:156-208, 211-227`）。

## 適用条件と副作用

- `--mode` が影響するのは drafting の計画値です。モデル名や family を与えないと、計画はモデル固有の選択ではなく一般的な情報になります。run config がある場合、`--mode` はその `drafting` 値を優先します（`terminal/strata_cli/drafting_cmd.py:101-120`）。
- `strata drafting plan` の処理は drafter をダウンロードしません。CLI 全体の起動時にはユーザー既定のファイル権限を採用する処理が呼ばれます（`terminal/strata_cli/cli.py:2314-2327`）。このコマンド経路でそれ以外のファイル変更が行われることは、確認した parser・plan 処理からは確認できません。
- 機器検出、モデル情報の解決、設定ファイルの内容に依存します。ここでは実機の GPU/backend ごとの結果は実行確認していません。

## 出力とエラー

- 不正な mode 値は parser の choices 検証でエラーになります。コマンド選択後に未知の引数が残った場合も argparse のエラー処理に入り、終了コード 2 となります（`terminal/strata_cli/drafting_cmd.py:29`、`terminal/strata_cli/cli.py:2325-2334`）。
- `--output json` を指定すると、選択結果や必要量などを含む JSON が stdout に出ます。通常の人向け出力は計画文です（`terminal/strata_cli/drafting_cmd.py:247-266`）。

## 根拠

- `terminal/strata_cli/drafting_cmd.py:19-38` — `drafting plan` parser、`--mode` の choices と未指定時の扱い。
- `terminal/strata_cli/drafting_cmd.py:101-137` — config 値との優先順位、`mtp: false` と split engine による計画値の補正。
- `terminal/strata_cli/drafting_cmd.py:211-266` — plan の特別経路、判定・出力・終了。
- `terminal/strata_control/drafting.py:37-40, 882-885, 1521-1587` — 有効値、auto の既定、モデル・backend に応じた選択と fallback。
- `terminal/strata_cli/cli.py:2314-2339` — CLI 起動、引数 parse、ユーザー既定の権限採用。
- 索引上の対象階層: `docs/cli/README.md:337-347` — `strata drafting plan` と `--mode` のリンク、および同階層の option scope。

調査制約: ソースコードと索引を確認し、CLI の実行、build、GPU 実行、テストは行っていません。特定 hardware での検出結果や実出力は未検証です。
