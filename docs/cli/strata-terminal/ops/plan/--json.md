# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops plan` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

レシピの plan 結果を、`schema_version` と `ok` を含む機械可読 JSON envelope で標準出力へ出します。プレビューそのものを実行するかどうかは変えません。plan は保存済みレシピとその種類に応じた事前確認を読み取り、`would_execute: false` を含む結果を返します（`strata_cli/cli.py:1440-1447`、`strata_control/recipes.py:329-360`）。

## 使い方

```sh
strata ops plan restart --profile work --json
```

`--output json` でも同じ machine-readable モードを選べます。

## 値と既定値

- `--json` は parser 上 `store_true` のフラグです。値は受け取らず、省略時は偽です（`strata_cli/cli.py:508-515`）。
- `ops plan` の `--output` は `human`（既定）または `json` を受け付けます（`strata_cli/cli.py:258-268`）。`--json` を指定すると引数処理後に `output` が `json` へ設定されるため、`--output human --json` も JSON モードです（`strata_cli/cli.py:2223-2235`）。
- 値付きの `--json=true` は定義されていません。未知引数は parser のエラーとなり、通常終了コード 2 です（`strata_cli/cli.py:2223-2231`）。

## 実行時の動作

`--json` 指定時、plan の成功・不成功いずれも stdout に1行の JSON を出します。形は `{"schema_version":1,"ok":<bool>,"plan":<plan>}` です。`ok` は `plan.operation.ok` と同じで、false の場合も plan 内容を返した後、`operation.exit_code`（未設定なら 5）で終了します。`--json` なしの場合も plan 自体は整形 JSON で stdout に出ますが、envelope は付きません（`strata_cli/cli.py:1440-1447`）。

事前確認の内容はレシピの種類で異なります。`runtime.restart` は `runtime.plan_restart()` を呼び、再起動用の preflight と実行時効果の説明を含めます。`engine.calibrate.measure` は calibration preview を呼びます。これは明示的にエンジンを起動せず、設定ファイルを書き換えない preview です。`components.verify` は保存済み `live` 設定（未指定なら false）で component inspection を行います（`strata_control/recipes.py:329-360`、`strata_control/runtime.py:734-740`、`strata_control/calibration.py:95-111`、`strata_control/doctor.py:146-164,218-235`）。したがって `--json` は出力形式だけを選び、plan の事前確認内容を追加・省略しません。

## 適用条件と副作用

- `--profile` とレシピ名が必要です。レシピの読み込みではプロファイルとレシピ ID、JSON schema、recipe kind / params を検証し、ファイルは通常ファイルで 64 KiB 未満であること、POSIX では owner-only mode であることを確認します（`strata_cli/cli.py:258-268`、`strata_control/recipes.py:32-35,93-114,180-196`）。
- `--json` 自体はファイルを変更せず、レシピの実行にも進みません。plan はプロファイル revision が確認中に変わった場合、終了コード 6 のエラーにします（`strata_control/recipes.py:356-360`）。ただし種類に応じた確認は行われます。特に `components.verify` は recipe の `live: true` なら host GPU probe を試み得ます（`strata_control/recipes.py:349-355`、`strata_control/doctor.py:230-233`）。
- 同じ `--json` は `ops` の他の one-shot サブコマンドにも登録されていますが、この文書の対象は `ops plan` です（`strata_cli/cli.py:258-260,508-515`）。

## 出力とエラー

- plan の検査結果が不成功でも JSON は stdout に出力され、その検査結果に応じた終了コードになります（通常は 5、restart は preflight の `exit_code` を使います）（`strata_cli/cli.py:1441-1447`、`strata_control/recipes.py:332-355`）。
- レシピ不在・不正、profile 関連エラーなど例外として伝播する失敗は、`--json` 時に `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` を stdout に出し、エラーコードで終了します（`strata_cli/cli.py:527-532,2166-2183`）。引数構文エラーは argparse が stderr に出し、JSON envelope にはなりません（`strata_cli/cli.py:2223-2235`）。

## 根拠

- `strata_cli/cli.py:255-268,508-515` — ops parser、`--profile`、`--output` と共通 `--json` の登録。
- `strata_cli/cli.py:2223-2235` — `--json` から `output=json` への変換と引数解析。
- `strata_cli/cli.py:1391-1447,527-542,2166-2183` — ops plan の JSON 出力、終了コード、共通成功・エラー出力。
- `strata_control/recipes.py:93-114,180-196,329-360` — レシピ validation / load と plan 分岐。
- `strata_control/runtime.py:734-740` — restart plan の preflight 呼び出し。
- `strata_control/calibration.py:95-111` — calibration preview の読み取り専用動作。
- `strata_control/doctor.py:146-164,218-235` — components inspection と live GPU probe 条件。

調査範囲は上記 checkout のソースです。異なる OS 上の実行結果や、runtime preflight の RPC 先で行われる詳細な状態確認はこの調査では実行・検証していません。
