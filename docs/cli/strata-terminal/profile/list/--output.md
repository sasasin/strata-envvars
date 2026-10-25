# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile list` |
| オプション | `--output` |
| 別名 | `--json`（JSON 出力を選ぶフラグ） |
| 値 | `human` または `json` |

## 役割

保存済み profile の一覧を、人向けの行表示か機械処理向け JSON で出力します。名前や保存場所を指定するオプションではありません。

## 使い方

```sh
strata profile list --output json
```

人向け表示は既定なので、通常は `strata profile list` と実行します。`strata profile list --json` も JSON 出力になります。

## 値と既定値

- 受理値は `human` と `json`、既定値は `human` です。`argparse` の `choices` による制約なので、その他の値は処理前に拒否され、usage と引数エラーが表示されます（終了コード 2）。
- `--output` は値を一つ取ります。値の省略や不正値は argparse のエラー経路です。
- `--json` は当該 parser に後から登録される `store_true` のフラグで、`main()` が `a.output = "json"` に設定します。`--output json --json` は同じ結果です。`--output human --json` も後段の alias 処理が優先し JSON になります。
- 同じ `--output` を複数回指定した場合は argparse の通常の `store` 動作で最後に解析された値が残ります。

## 実行時の動作

コマンドは profile 保存ディレクトリにある `*.json` のうち、profile ID の規則に合うファイルを名前順に列挙し、各ファイルを読み込んで検証します。有効な項目には `id`、revision、`source_config` が含まれます。`--output` の値はこの結果を人向け表示にするか JSON にするかだけを選択します。保存ディレクトリは環境変数 `STRATA_PROFILE_DIR` があればその値、なければ OS に応じた設定ディレクトリです。

- `human`: profile があれば各行を `<id>  <revision>` の形で表示し、profile がない場合は `No saved profiles` と表示します。個別 profile の読み込みエラーは `<id>  <error>` として表示されます。
- `json`: 標準出力に `schema_version: 1`、`ok: true`、`profiles` 配列を含む JSON オブジェクトを一行で出力します。各有効要素には `id`、`revision`、`source_config`、読み込みエラー要素には `id` と `error` が入ります。
- `--quiet` を併用すると、人向け出力は抑止されます。`--output json` または `--json` の場合は機械可読出力が優先され、JSON は抑止されません。

## 適用条件と副作用

保存ディレクトリが存在しない場合は空の一覧として成功します。profile 一覧処理自体は profile の作成・更新・削除を行いません。ただし profile のロードでは、読み取り権限エラー時に Strata 管理下ファイルのアクセス権を一度修復して再読込する処理が呼ばれることがあります。修復に成功した場合はファイル権限が変更され得ます。これは `strata_control.private_files.read_bytes_repairing()` の実装に基づくもので、プラットフォーム別の修復条件の全てはここでは実機確認していません。

## 出力とエラー

- 成功時の終了コードは 0 です。JSON モードは成功 envelope を標準出力へ出し、人向けモードは profile 行または空一覧メッセージを標準出力へ出します。
- 一つの profile が `ProfileError` になる場合、その profile を `error` 付き項目として結果に含め、一覧処理自体は継続します。
- 一覧ディレクトリの列挙など、個別 profile の `ProfileError` 捕捉外で `OSError` / `ValueError` が発生すると、共通エラー処理へ進みます。`--output json` では `schema_version: 1`、`ok: false`、エラーの `code` と `message` を標準出力に JSON で出し、その他のファイル操作エラーはコード 6、値エラーは通常コード 2 です。人向けでは `strata: <message>` を標準エラーへ出します。
- 不正な `--output` 値など parser エラーは `_run()` より前に argparse が処理するため、共通 JSON エラー envelope ではなく usage とエラーメッセージになります。

## 根拠

- parser のコマンド階層、値、既定値: `strata_cli/cli.py:70-76`
- `--json` alias と `--quiet` の登録、出力形式の切り替え: `strata_cli/cli.py:508-515`, `strata_cli/cli.py:2232-2247`
- profile 一覧の human / JSON 整形: `strata_cli/cli.py:958-967`
- 成功・失敗 JSON と人向けエラー出力: `strata_cli/cli.py:527-542`
- 共通例外処理と終了コード: `strata_cli/cli.py:2166-2183`
- 保存先決定、ソート・対象ファイル・個別エラーの処理: `strata_control/profiles.py:38-45`, `strata_control/profiles.py:169-182`
- profile 読み込みと権限修復付き read: `strata_control/profiles.py:150-166`, `strata_control/private_files.py:476-484`
