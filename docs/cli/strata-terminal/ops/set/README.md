# `strata ops set`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops set` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/recipes.py` |

## 役割

指定したプロファイルに保存されている型付き operation recipe のパラメーターを1項目変更します。recipe は既知の操作種別と値だけを持ち、任意の shell コマンドを実行する仕組みではありません。`set` は recipe を保存する操作で、recipe の operation 自体は実行しません。実行内容の確認には `strata ops plan`、実行には別途 `strata ops run` を使います。

## 基本的な使い方

```sh
# restart recipe の起動待ち時間を45秒に変更する
strata ops set restart --profile four-gpu startup_wait_s=45

# 保存せず、変更案と would_save を表示する
strata ops set check --profile four-gpu live=true --plan

# calibration recipe のレポート保存先を変更する
strata ops set calibrate --profile four-gpu report_dir=/private/path/reports

# recipe を JSON で表示する
strata ops set restart --profile four-gpu startup_wait_s=45 --output json
```

recipe は先に `strata ops init --profile NAME` または `strata ops create` で用意します。初期化で作られる名前は `restart`、`calibrate`、`check` です。変更案を確認してから保存し、動作の事前確認と実行はそれぞれ `ops plan` と `ops run` で行ってください。

## 引数と出力形式

構文は `strata ops set NAME --profile PROFILE KEY=VALUE [--plan] [--output {human,json}]` です。`NAME` は recipe ID、`--profile` は必須です。assignment は位置引数1つだけで、`=` より前をキー、後ろを値として解釈します。キーと値に `=` が含まれる場合、最初の `=` で分割され、残りは値に含まれます。

`--output` の既定値は `human`、選択肢は `human` と `json` です。JSON 出力は recipe と revision を返します。`--plan` を付けると保存せず、現在の recipe と提案値を比較して `would_save` を返します。同じ値を再設定した場合、保存時も recipe を変更せず revision は変わりません。

## 値と既定値

受け付けるキーは recipe の kind によって異なります。

| recipe kind | `KEY=VALUE` | 解釈と検証 |
| --- | --- | --- |
| `runtime.restart` | `startup_wait_s=N` | 整数に変換し、1〜600 の範囲。小数表記や整数以外は拒否されます。 |
| `engine.calibrate.measure` | `report_dir=PATH` | 文字列として受け取り、空でなく、NUL を含まず、絶対パスであること。 |
| `components.verify` | `live=true` または `live=false` | 小文字の真偽値のみ。 |

recipe 作成時の初期値は `startup_wait_s=300`、calibration の `report_dir` はプロファイルディレクトリ内の `.reports`、components verify はパラメーターなしです。`set` 自体に共通の assignment 既定値はありません。`live` を設定しない recipe では `false` 相当として扱われます。

## 実行時の動作と副作用

通常実行では、recipe を読み込んで assignment を型変換・検証した後、現在の revision を条件として保存します。内容が変わる場合、直前の版を history に退避し、recipe ファイルを atomic write で置き換えます。保存済み recipe が編集中に変更されて revision が一致しなくなった場合は、競合として保存を拒否します。`--plan` は提案内容を返すだけで recipe ファイルや履歴を更新しません。

`--plan` は **設定変更のプレビュー** であり、後続の `ops plan` のように operation の preflight や実行効果まで調べるものではありません。保存した値が operation にどう影響するかは `ops plan NAME --profile PROFILE` で確認してください。特に calibration recipe は `ops run` 時に測定と新規レポート作成を行い、component recipe の `live=true` は計画と実行の両方で GPU inventory を照会します。`ops set` そのものはそれらの操作を行いません。

## エラー

`KEY=VALUE` 形式でない、値が空、キーが recipe kind で未対応、値が型・範囲条件を満たさない場合は `ProfileError` になります。recipe が未作成・破損している場合や、recipe の profile/name が不正な場合も失敗します。競合時は変更を保存せず、再読込を促すエラーになります。CLI は `ProfileError` のメッセージと exit code を返します。parser が必要引数や `--output` の選択肢を満たさない入力を検出した場合は argparse の usage/error 経路になります。

## 関連文書

- [`strata ops` の索引とオプション一覧](../../../README.md#strata-ops-set-opsset)
- [`strata ops` コマンド概要](../README.md) — recipe の全体像
- Strata ソースの `docs/TERMINAL.md` — recipe の初期化、設定、計画、実行、履歴の手順

## 根拠

- `strata_cli/cli.py:255-275` — `ops` のサブコマンド登録、共通引数、`set` の assignment と `--plan` parser。
- `strata_cli/cli.py:1391-1394,1423-1430` — JSON/human の選択、提案値の生成、plan 分岐、通常保存と応答。
- `strata_control/recipes.py:93-114,117-127` — recipe schema と kind ごとの型・範囲・パス検証、および作成時の初期値。
- `strata_control/recipes.py:214-237` — revision 競合検出、変更なし時の扱い、history 退避と atomic 保存。
- `strata_control/recipes.py:278-296` — `KEY=VALUE` の分割、型変換、kind ごとの対応キー、提案内容の検証。
- `docs/TERMINAL.md:96-122` — 利用例、plan/run の役割、各 recipe kind の効果。
