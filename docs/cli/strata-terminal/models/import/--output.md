# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models import` |
| オプション | `--output` |
| 別名 | なし（`--json` は別に定義された alias） |
| 値 | `human` または `json` |

## 役割

既存 GGUF ファイル群の import plan を、人向けの複数行表示か機械処理向け JSON で出力します。このコマンドは候補を調査するだけで、モデルを Strata に採用したりファイルを変更したりしません（`strata_cli/cli.py:157-161, 550-561`、`strata_control/models.py:579-585, 720-735`）。

## 使い方

```sh
strata models import /path/to/model.gguf --plan --output json
```

`PATH` は位置引数です。`--plan` は parser 上必須です。`--output` の値は省略できます（`strata_cli/cli.py:157-161`）。

## 値と既定値

- `human`: 既定値。成功時は候補ファイル数と状態、認識したモデル、既設定情報、adoption 状態、および「No files changed」を平文で標準出力します。
- `json`: 成功時は `schema_version: 1`、`ok: true`、`plan` を含む JSON オブジェクトを標準出力します。
- それ以外の値は `argparse` の `choices` 検査で拒否されます。値を取るオプションなので `--output` の後には値が必要です（`strata_cli/cli.py:161`）。

明示した `--output` を複数回指定した場合、parser は通常の `store` action で値を保持するため最後の指定が有効です（`strata_cli/cli.py:161`）。

## 実行時の動作

コマンド処理は `models.plan_import(PATH)` を呼び出し、その返した同一 plan を `--output` の値に応じて整形します。`json` は成功時に `_success` 経由で JSON を出力し、`human` は `_import_words` の平文を出力します（`strata_cli/cli.py:550-561, 535-542, 708-723`）。

`--json` は one-shot コマンド用に別途追加される alias で、指定時は `main` が `a.output` を `json` に置き換えます。したがって `--output json` と同じ出力モードです（`strata_cli/cli.py:510-515, 2232-2237`）。`--quiet` もこの parser に追加されますが、`output` が `json` のとき `main` は quiet 用の人向け出力抑制経路に入らず、JSON 出力を保ちます（`strata_cli/cli.py:510-515, 2236-2247`）。

plan 作成は指定パスが絶対パスであること、ファイルまたはディレクトリであること、GGUF shard の組や metadata が読めることなどを調べます。候補の不備が plan の `issues` に記録された場合は、`human` では説明を標準エラーへ、`json` では `ok: false` と `plan` を含む JSON を標準出力へ出し、どちらも終了コード `5` になります（`strata_control/models.py:579-640, 656-735`、`strata_cli/cli.py:552-561, 606-614`）。

## 適用条件と副作用

`--output` は表示形式だけを選び、import の探索・判定内容は変えません。plan はモデル候補のローカルファイルを読み取りますが、返却データでは `would_write` が `false` で adoption は未完了とされています。人向け成功文にもファイル変更なしと明記されます（`strata_control/models.py:579-585, 720-735`、`strata_cli/cli.py:708-723`）。ネットワーク接続やモデル採用処理への転送はこの経路では行われません（`strata_cli/cli.py:552-561`）。

## 出力とエラー

- plan の作成に成功し `issues` が空なら、`human` は標準出力に説明文、`json` は標準出力に成功 JSON を出して終了コード `0` です（`strata_cli/cli.py:552-561`）。
- plan は作成できたものの候補に問題がある場合、上記のとおり終了コード `5` です。JSON 形式は `{"schema_version": 1, "ok": false, "plan": ...}` で、通常の `_error` 形式とは異なります（`strata_cli/cli.py:554-560`）。
- 絶対パスでない、対象が存在しない、GGUF でない等、`plan_import` が `ProfileError` を送出するケースは `_run` が `ValueError` として捕捉します。終了コードは例外の `exit_code`（この import の検査エラーは通常 `5`）で、`human` は `strata: ...` を標準エラーに出し、`json` はエラー JSON を標準出力に出します（`strata_control/models.py:586-640`、`strata_control/profiles.py:30-35`、`strata_cli/cli.py:527-533, 2166-2173`）。
- `human` / `json` 以外の値など parser エラーは `argparse` による usage/error 表示と終了コード `2` になります。parser の検査より前に起きるため、`--output json` を指定してもこのエラーは JSON 形式になりません（`strata_cli/cli.py:157-161, 2223-2235`）。

## 根拠

- parser 定義と `--json` / `--quiet` の追加: `strata_cli/cli.py:157-161, 510-515, 2232-2247`。
- import の dispatch、成功・不備時の出力: `strata_cli/cli.py:550-561, 606-614, 708-723`。
- plan の読取専用契約・検査結果: `strata_control/models.py:579-640, 656-735`。
- 一般的な例外出力と終了コード: `strata_cli/cli.py:527-533, 2166-2183`、`strata_control/profiles.py:30-35`。
- コマンド階層と option scope: [`docs/cli/README.md`](../../../README.md) の `strata models import` 節。文書配置・調査基準: [`001_investigation.md`](../../../001_investigation.md)。

調査対象は指定 checkout の source です。同一 revision の既存 CLI help および Release artifact は照合していません。
