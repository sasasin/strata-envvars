# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops run` |
| オプション | `--output` |
| 別名 | なし（`--json` は `--output json` にする別オプション） |
| 値 | `human` または `json` |

## 役割

`strata ops run` が実行した operation の結果を、既定値 `human` または機械処理向け `json` の形式で標準出力へ出します。この設定は表示形式を選び、recipe の実行内容や副作用を選択・抑止するものではありません（parser は `strata_cli/cli.py:278-290`、出力分岐は同 `:1458-1464`）。

## 使い方

```sh
strata ops run restart-local --profile default --output json
```

`restart-local` は recipe 名、`default` は必須の profile ID の例です。recipe 名と `--profile` は `strata ops run` の共通引数で、`--output` は全 `ops` action に登録されています（`strata_cli/cli.py:258-267`）。

## 値と既定値

- `--output` は `human` / `json` のみを受理し、省略時は `human` です。空値を含む別値は argparse の選択肢検査で拒否されます。複数回指定した場合は argparse の通常の引数処理により最後の `--output` 値が残ります（`strata_cli/cli.py:267`）。ただし `--json` を併記すると、`main` が `output` を `json` に設定します（同 `:2232-2235`）。
- `--json` は one-shot `ops` parser 群に後から登録される別名 option です。指定時は `main` が `output` を `json` に設定します。`--output json` と同じ機械可読出力になります（`strata_cli/cli.py:508-515, 2232-2235`）。
- `--quiet` も `ops run` に登録されます。JSON 出力時は quiet の stdout 抑制処理を通らず、JSON が出力されます。`human` と `--quiet` を併用すると、成功時の stdout は抑制され、失敗時に捕捉した出力があれば stderr に出されます（`strata_cli/cli.py:508-515, 2236-2248`）。

## 実行時の動作

`--output json` では成功・operation 完了失敗ともに、`schema_version: 1` と `ok`、`operation` を含む JSON オブジェクトを1行で標準出力へ書きます。成功した operation は終了コード `0`、結果が失敗なら結果の `exit_code`（なければ `5`）で終了します（`strata_cli/cli.py:1458-1464`）。`--output human` では専用の人間向け整形文ではなく、operation 全体をインデント付き JSON として標準出力へ出します。終了コードの規則は JSON と同じです（同 `:1462-1464`）。

recipe 実行中に recipe 側が標準出力へ書く内容は stderr に振り替えられ、最終 operation レコードは標準出力に出ます（`strata_cli/cli.py:1451-1464`）。`--output` は実行処理に渡されません。recipe の内容に応じて、runtime restart、engine calibration measurement、または components verify が動きます。たとえば calibration recipe はレポートディレクトリを用意して新しい JSON report を書き、適用前のレビューを要求します（`strata_control/recipes.py:374-428`）。

## 適用条件と副作用

このオプション自体の副作用は出力形式の選択です。operation の実行によるファイル・runtime 等への作用は recipe に依存し、`--output human/json` では変化しません（`strata_cli/cli.py:1451-1464`、`strata_control/recipes.py:374-428`）。

## 出力とエラー

- recipe の読み込み、revision 条件、または実行中に発生した `ValueError` / `OSError` / `ClientError` は CLI 共通の例外処理へ渡ります。JSON モードでは `schema_version: 1, ok: false, error: {code, message}` 形式、human モードでは `strata: ...` を stderr に出します（`strata_cli/cli.py:527-532, 2166-2188`）。
- `recipes.run` は operation の例外を journal に `failed` または `completion_unknown` として記録して再送出します。結果が `ok: false` で完了した場合も `failed` として記録され、CLI は結果に応じた終了コードを返します（`strata_control/recipes.py:429-438`）。
- 引数値の欠落や許可されない値は実行前の argparse 検査で失敗します（`strata_cli/cli.py:267`）。この調査では CLI を実行して表示文や実際の終了コードを検証していません。

## 根拠

- parser 定義と `--json` alias の登録: `strata_cli/cli.py:255-290, 508-515`
- `--json` を `--output json` として処理する箇所: `strata_cli/cli.py:2217-2237`
- run の実行と出力形式・終了コード: `strata_cli/cli.py:1391-1394, 1448-1464`
- 共通成功・エラー出力と例外経路: `strata_cli/cli.py:527-542, 2166-2193`
- recipe の前提条件、種別ごとの実行、副作用、journal 記録: `strata_control/recipes.py:363-438`
- 索引上の scope とリンク: `docs/cli/README.md:569-581`

調査対象 checkout は `git status --short --branch` で `## main...origin/main` と表示され、未コミット変更はありませんでした。文書リポジトリには調査開始時から未コミット変更がありましたが、指定文書以外は編集していません。ビルド、CLI 実行、テスト、性能測定は行っていません。
