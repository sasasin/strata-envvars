# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models list` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると `--output json` と同じ出力形式を選ぶ |

## 役割

成功時と、コマンド内で処理されるエラー時の結果を JSON で標準出力へ出します。モデル一覧の対象範囲を選ぶものではありません。ローカルの run config 一覧が既定で、`--served` を指定すると接続先の現在の server instance が報告するモデルに切り替わります。

## 使い方

```sh
strata models list --json
strata models list --served --url https://strata.example --json
```

1つ目は既知のインストール場所にあるローカル run config を列挙します。2つ目は server の現在の instance を問い合わせます。URL、saved connection、認証 credential、timeout など接続条件の指定方法はこのフラグの対象外です。

## 値と既定値

- `--json` は共通 one-shot parser 群に `action="store_true"` で追加されます。値を後置せず、未指定時は false です。`strata models list` の個別定義ではなく、`models_list` parser を含む共通登録ループが追加元です（`strata_cli/cli.py:508-515`）。
- `--output` は `human` または `json` を受け、既定値は `human` です（`strata_cli/cli.py:147-152`）。`--json` が指定されると parse 後に `a.output` が `json` に設定されるため、併記した `--output human` よりも `--json` が優先されます（`strata_cli/cli.py:2232-2235`）。
- `--json` と `--output json` の重複指定は同じ JSON 出力を選びます。無効な `--output` 値は argparse の選択肢検査で拒否されます。`--json` 自体には値の検証や範囲指定はありません。

## 実行時の動作

`--json` はデータ収集や対象選択を変更せず、出力モードだけを切り替えます。ローカル一覧では `strata_control.models.list_installed(a.install_dir)` の結果を成功 envelope に入れ、`schema_version: 1`、`ok: true` と一覧 payload を標準出力に1行の JSON として出力します。人間向け一覧の整形は JSON モードでは使われません（`strata_cli/cli.py:588-596`、`strata_cli/cli.py:535-542`）。

ローカル一覧の収集はインストール場所にある setup 生成 run config を読み取り、重複 ID は先に見つかった場所のものを採用します。読取・検査できない config は一覧中に `component_status: "invalid"` として記録される場合があり、一覧全体を中断する扱いとは区別されています（`strata_control/models.py:1-12,185-210`）。

`--served` と併用した場合は `connections.resolve(...)` で URL/connection 等を解決し、server の snapshot を取得します。成功 JSON の scope は `served_current_instance` で、server が現在報告するモデルのみを含み、インストール済みモデル全体の inventory ではない旨の note も含まれます（`strata_cli/cli.py:564-585`）。server からの telemetry は `/v1/telemetry` を優先し、404 の場合 `/metrics` と `/v1/status`、または `/v1/status` のみへ fallback します（`strata_cli/client.py:134-152`）。接続設定の優先順位や timeout の規則は `strata_cli/connections.py:273-302` にあります。

## 適用条件と副作用

- `--served` と `--installed` は同じ相互排他グループです（`strata_cli/cli.py:143-146`）。`--installed` は既定のローカル一覧範囲を明示するフラグで、`_models` の分岐では `--served` の有無だけで local/served が選ばれます（`strata_cli/cli.py:564-588`）。
- `--url`、`--connection`、`--credential-env`、`--timeout` は `--served` 専用です。`--served` なしでいずれかを指定するとエラーになります（`strata_cli/cli.py:586-587`）。`--served` 時に `--install-dir` を指定しても適用されず、エラーになります（`strata_cli/cli.py:565-568`）。
- JSON 表示フラグ自体はファイルを書き換えません。ローカル経路は run config の読み取り、served 経路は server への HTTP telemetry request を行います（`strata_control/models.py:1-12,185-210`、`strata_cli/client.py:134-152`）。
- `--quiet` と共通に受理されますが、`--json` により `output` が `json` になると `main` は quiet 用の標準出力捕捉を行わず `_run` に進みます（`strata_cli/cli.py:2232-2243`）。

## 出力とエラー

- 成功時は `{"schema_version":1,"ok":true,...}` 形式を標準出力へ出し、終了コードは 0 です（`strata_cli/cli.py:535-542`）。該当モデルがない場合も成功で、空一覧の案内文ではなく、空の `models` 配列等を含む JSON が出ます（`strata_cli/cli.py:588-596`）。
- `_error` を通るエラーは `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` 形式を標準出力へ出し、エラーコードを終了コードとして返します（`strata_cli/cli.py:527-532`）。たとえば `--served` なしの接続オプションや、served と install-dir の併用はコード 2 のエラーです（`strata_cli/cli.py:565-568,586-587`）。
- local config ごとの読取・検査エラーは一覧内の invalid 項目として返される経路があります（`strata_control/models.py:191-204`）。saved connection 不正や server 通信失敗など、コマンド実行中に `ValueError`、`OSError`、`ClientError` として処理される例外も、JSON エラー応答へ変換される経路があります（`strata_cli/cli.py:2166-2188`）。
- argparse が行う未知引数や不正な `--output` 値の拒否は `main` の JSON モード変換より前に起こり、`argparse` の usage/error 出力になります。`--served` と `--installed` の同時指定も相互排他グループで parse error となります。これらの parse error は上記 JSON envelope ではありません（`strata_cli/cli.py:143-146,2223-2235`）。

## 根拠

- parser の `--output` 定義: `strata_cli/cli.py:147-152`
- 共通 one-shot parser への `--json` 登録（`models_list` を含む）: `strata_cli/cli.py:508-515`
- `--json` による output 切替と quiet 分岐: `strata_cli/cli.py:2232-2243`
- local/served の実処理と引数適用条件: `strata_cli/cli.py:550-600`
- JSON 成功・エラー envelope: `strata_cli/cli.py:527-542`
- ローカル run config の一覧と read-only の範囲: `strata_control/models.py:1-12,185-210`
- saved connection の解決と timeout 範囲: `strata_cli/connections.py:273-302`
- server snapshot の endpoint fallback: `strata_cli/client.py:134-152`
