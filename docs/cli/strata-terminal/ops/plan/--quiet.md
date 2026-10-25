# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops plan` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

人向けの標準出力を抑制します。`ops plan` の通常出力は整形 JSON なので、成功した計画結果も抑制対象です。計画の生成自体を省くオプションではありません。

## 使い方

```sh
strata ops plan restart --profile work --quiet
```

`restart` は既存の recipe 名、`work` は profile ID の例です。どちらも実環境に存在する必要があります。

## 値と既定値

- `--quiet` は `store_true` のフラグで、値を取りません。省略時は quiet ではありません。
- 値を続けて渡す構文ではありません。余分な引数は quiet 処理に入る前に parser が拒否し、usage とエラーを標準エラーへ出して終了コード 2 になります。
- このオプションは `ops plan` 専用の parser 宣言ではなく、`ops` の各 one-shot parser に共通追加されます。`ops plan` でも `--quiet` は受理されます。
- `--output` の既定値は `human`、選択肢は `human` と `json` です。`--json` は `--output json` の別表記です。

## 実行時の動作

`strata ops plan` は recipe を読み込み、その種類に応じて restart の事前確認、calibration の preview、または component 検査を行い、実行計画を生成します。`--quiet` はこの処理を変更せず、成功時に標準出力へ出す計画 JSON を隠します。計画自体は `would_execute: false` として返され、実行は行いません。

通常の `--output human`（既定）では、plan handler が整形 JSON を標準出力へ書きます。`--quiet` があると main の出力捕捉で成功時の標準出力は表示されません。`--output json` または `--json` を指定すると、JSON/JSONL 出力モードでは quiet 捕捉を行わないため、`--quiet` を併記しても機械可読 JSON は標準出力に出ます。したがって、出力を隠したい場合は `--output json` / `--json` を併用しないでください。

## 適用条件と副作用

- `--quiet` は `ops` の one-shot action（`init`、`list`、`create`、`show`、`edit`、`set`、`history`、`rollback`、`plan`、`run`、`runs`、`result`）に共通追加されます。`ops plan` の parser では `--profile` が必須です。
- plan の標準出力のみを制御します。標準エラーは捕捉対象ではありません。計画処理が返す失敗状態や終了コードも変更しません。
- plan が失敗終了し、捕捉中に標準出力へ既に情報が書かれていれば、その内容は標準エラーへ戻されます。捕捉内容が 64 KiB を超えて切り詰められた場合は、標準エラーへ `strata: earlier human output omitted in quiet mode` も出ます。
- `--quiet` 自体によるファイル変更・recipe 実行・ネットワーク通信はありません。plan の種類ごとの事前確認が読む情報や live 検査の詳細は、それぞれの処理に依存します。

## 出力とエラー

- 成功かつ `--output human` の場合、plan の整形 JSON は抑制され、終了コードは 0 です。
- plan の判定が失敗の場合、JSON 出力は `ok: false` を含み、終了コードは計画の `exit_code`（なければ 5）です。quiet 時は捕捉した標準出力を標準エラーへ移します。
- `--output json` / `--json` では成功・失敗いずれも JSON を標準出力に出し、`--quiet` はその出力を抑制しません。
- recipe/profile 読み込み等で例外が発生した場合、通常のエラー処理が診断を標準エラーに出し、エラーコードを返します。quiet はこの標準エラー診断を隠しません。
- `--quiet` に値を付けるなど余分な引数があると、parser が quiet の出力捕捉を始める前に usage と `unrecognized arguments` を標準エラーへ出し、終了コード 2 で拒否します。

## 根拠

- `strata_cli/cli.py:255-268` — `ops` action parser 群、必須 `--profile`、`--output` の選択肢と既定値。
- `strata_cli/cli.py:508-515` — one-shot parser に `--json` と `--quiet` を後付けする定義。`argparse.SUPPRESS` のため quiet 省略時に属性を作らず、main 側で false 相当として扱います。
- `strata_cli/cli.py:1391-1447` — `ops plan` が `recipes.plan` を呼び、`--output json` なら schema 付き JSON、それ以外は整形 JSON を出す処理と、計画結果に基づく終了コード。
- `strata_control/recipes.py:329-360` — recipe 種類ごとの preview、profile revision の再確認、`would_execute: false` を含む plan 結果。
- `strata_cli/cli.py:527-542` — 通常の成功・失敗出力先と終了コード。
- `strata_cli/cli.py:2166-2193` — `ValueError`、`OSError`、`ClientError`、割り込み時の stderr 診断と終了コード。
- `strata_cli/cli.py:2223-2231` — parser 実行と余分な引数を quiet 捕捉より前に拒否する経路。
- `strata_cli/cli.py:2196-2215,2232-2248` — quiet の出力捕捉上限、JSON/JSONL 時の捕捉回避、失敗時の標準エラーへの復帰。
