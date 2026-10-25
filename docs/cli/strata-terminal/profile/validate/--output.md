# `strata profile validate --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile validate` |
| オプション | `--output` |
| 別名 | `なし`（`--json` は同じ one-shot コマンドに追加される JSON 出力の別フラグ） |
| 値 | `human` または `json` |

## 役割

検証結果を人間向けの短い文、または機械処理向けの JSON で標準出力に出します。出力形式を選ぶだけで、検証対象や検証内容は変えません。

## 使い方

```sh
strata profile validate work --output json
```

保存済みプロファイル `work` と参照先 run config を検査し、JSON を出力します。`--output` を省略した場合は `human` です。

## 値と既定値

- parser は `human` / `json` のみを受理し、既定値は `human` です。別の値を渡すと argparse が usage とエラーを標準エラーに出し、終了コード 2 で終了します。
- このコマンドでは `--json` も one-shot parser 群に共通追加されるフラグです。指定すると `--output json` と同じ出力分岐になります。両方指定した場合も JSON です。
- `--output` はファイルパスではなく出力形式です。ファイル作成先・上書き先は指定しません。

## 実行時の動作

`human` の場合、成功時は `Profile <名前> is valid at revision <revision>` を標準出力に出します。`json` の場合は schema version 1 の JSON オブジェクトを一行出力します。成功オブジェクトは `ok: true` と `profile`、`revision`、`plan` を含みます。`plan` は検証で組み立てた有効設定、起動引数、エンジン引数などを含み、エンジン引数中の key/token/secret 等に該当する値は `<redacted>` に置き換えられます。

検証ではプロファイルを読み込み、参照する run config を読み、設定の整合性と launch plan の生成を行います。JSON 出力の選択によって実行内容が変わることはありません。検証コマンド自身は server / engine を起動しません。

## 適用条件と副作用

- `name` は保存済みプロファイル名です。プロファイルは `STRATA_PROFILE_DIR` があればそのディレクトリ、なければ OS に応じた Strata 設定ディレクトリから読み込まれます。
- プロファイルの読み込み経路は、管理者実行等でロックされたファイルのアクセス権を必要に応じて修復します。そのため検証は通常設定ファイルを変更しませんが、このアクセス権修復が発生する場合があります。
- launch plan の生成は run config 内の値、保存済み override、環境変数等を参照し、組み合わせによっては設定エラーになります。`--output` はこれらの条件を回避しません。
- 起動・ネットワーク接続・GPU 問い合わせ・計画ファイル出力は、この検証経路では行いません。

## 出力とエラー

- `human` 成功は説明文一行、`json` 成功は `{"schema_version":1,"ok":true,...}` 形式を標準出力に出し、終了コード 0 です。
- `json` の失敗は `schema_version: 1`、`ok: false`、`error`（`code` と `message`）を含む JSON を標準出力に出します。`human` の失敗は `strata: <エラー>` を標準エラーに出します。
- 未保存のプロファイル、無効なプロファイル、読めない run config、設定の矛盾などは失敗します。プロファイル関連エラーには既定の終了コード 2 のほか、読み込み等の失敗で 5 が設定される経路があります。

## 根拠

- `strata_cli/cli.py:81-83` — `profile validate` と位置引数 `name`、`--output` の choices / 既定値。
- `strata_cli/cli.py:508-515,2232-2236` — one-shot parser への `--json` 追加と `--output json` への変換。
- `strata_cli/cli.py:527-542,958-960,1015-1020` — machine/human 成功・失敗出力、および validate の plan 生成と成功文。
- `strata_cli/cli.py:745-826` — 設定の優先順位、検査、plan / engine argv の組み立てと引数の redaction。
- `strata_cli/cli.py:2166-2183` — ValueError / OSError の出力形式と終了コード処理。
- `strata_control/profiles.py:38-55,120-147,150-166` — プロファイル置き場、形式・参照先 run config の検証、読み込みエラーとアクセス権修復付き読み込み。

調査範囲は上記 commit の checkout にある Terminal CLI と `strata_control` 実装です。Release 配布物との照合および各 OS 上の実行確認は行っていません。
