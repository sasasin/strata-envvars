# `strata ops run` の `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops run` |
| オプション | `--profile PROFILE` |
| 別名 | なし |
| 値 | 保存済みプロフィール名。parser 上は文字列。実行時は小文字英字で始まり、小文字英字・数字・`_`・`-` のみ、1〜64文字に制限される |

## 役割

レシピを保存・管理している Strata serving profile を選びます。`ops run` はこのプロフィールに属する名前付きレシピを読み込み、その種類に応じた操作を実行します。`--profile` はプロフィール名を受け取るもので、run-config JSON のパスを受け取る引数ではありません。

## 使い方

```sh
strata ops run --profile my-profile restart
```

この例では、プロフィール `my-profile` に保存されている `restart` レシピを実行します。`strata ops init --profile my-profile` は初期レシピを作成します（`strata_cli/cli.py:255-266`）。

## 値と既定値

- `--profile` は `ops` の各サブコマンドに共通して定義され、`required=True` のため省略できません。`ops run` では位置引数のレシピ名も必要です（`strata_cli/cli.py:258-267`）。
- argparse は値を文字列として受け取ります。名前の検証はプロフィールのロード時に行われ、正規表現 `[a-z][a-z0-9_-]{0,63}` に一致する必要があります。大文字、空白、パス区切り、先頭数字は受け付けません（`strata_control/profiles.py:25,48-55`）。
- 該当する既定値はありません。プロフィール名を指定しても、未保存のプロフィールは自動作成されません（`strata_control/profiles.py:150-166`）。
- `ops` のレシピは選んだプロフィールの設定ディレクトリにある `.ops/<profile>/<recipe>.json` から読み込まれます。recipe ID にもプロフィール名と同じ形式制約が適用されます（`strata_control/recipes.py:32-64,180-196`）。

## 実行時の動作

`_ops` は `--profile` とレシピ名でレシピを読み込み、そのプロフィールのレシピ revision とプロフィール revision を実行記録に関連付けます。`--if-revision` と `--if-profile-revision` が指定されている場合は、実行前にそれぞれの revision が一致するか確認します（`strata_cli/cli.py:1448-1457`、`strata_control/recipes.py:363-400`）。

レシピ種別によりプロフィールの使われ方と副作用が異なります。

- `runtime.restart`: 選択プロフィールの管理対象 runtime を再起動します。レシピの `startup_wait_s` が起動待ち時間になり、再起動に失敗した場合の復元処理などは runtime 側の実装に委譲されます（`strata_control/recipes.py:375-412`）。
- `engine.calibrate.measure`: 選択プロフィールで校正測定を行い、レシピの `report_dir` に UUID 付き JSON レポートを新規作成します。`--exclusive` が必須で、測定結果は適用前に別途レビューする必要があります。プロフィールの run config はこの測定では変更しません（`strata_control/recipes.py:395-396,413-423`）。
- `components.verify`: 選択プロフィールの run config に対する component 検査を実行します。レシピの `live` が true の場合は host GPU の照会を含みます。レシピ計画上はファイルを書きません（`strata_control/recipes.py:424-428`、計画上の効果は `strata_control/recipes.py:349-355`）。

実行前提条件のオプション `--if-owner-id`、`--if-instance-id`、`--if-source-sha256` は restart レシピにだけ適用されます。これらを他の種別と組み合わせると拒否されます。`--exclusive` も calibration レシピ以外では拒否されます（`strata_cli/cli.py:278-290,1448-1457`、`strata_control/recipes.py:375-396`）。

レシピと実行 journal はプロフィールディレクトリ以下に置かれます。プロフィールディレクトリは `STRATA_PROFILE_DIR` で指定でき、未指定時は OS に応じたユーザー設定ディレクトリです（`strata_control/profiles.py:38-45`、レシピ保存場所は `strata_control/recipes.py:38-64`、journal は `strata_control/journal.py:47-63`）。

## 適用条件と副作用

- 指定プロフィールが保存済みで、有効なプロフィール JSON として読み込める必要があります。保存されていない場合は「profile ... is not saved」となり、終了コード 5 です（`strata_control/profiles.py:150-166`）。
- 指定プロフィールに対象レシピが存在しない場合は、`strata ops init --profile <PROFILE>` の案内を含むエラーとなり、終了コード 5 です。壊れたレシピ、非通常ファイル、64 KiB を超えるレシピも拒否されます（`strata_control/recipes.py:180-196`）。
- 実行可能な操作は保存レシピの `kind` によって決まります。対応種別は `runtime.restart`、`engine.calibrate.measure`、`components.verify` です（`strata_control/recipes.py:28,93-114`）。
- 実行開始時に operation journal の記録を作り、成功・失敗・完了状態不明を記録します。したがって `--profile` はレシピ選択だけでなく、操作記録のプロフィール境界も決めます（`strata_control/recipes.py:397-400,429-439`、`strata_control/journal.py:1-5,47-63`）。
- `runtime.restart` はサーバー状態を変更し得ます。`engine.calibrate.measure` はエンジンを起動して測定し、レポートを作成します。オプション指定だけでは read-only 動作になりません。

## 出力とエラー

- 成功時の標準出力は、通常は operation JSON（整形済み）、`--output json` では `schema_version`、`ok`、`operation` を含む JSON です（`strata_cli/cli.py:1458-1464`）。
- レシピ実行中に標準出力へ出る進捗は標準エラーへリダイレクトされます（`strata_cli/cli.py:1451-1457`）。
- 操作結果が `ok: false` の場合は結果にある `exit_code`、なければ 5 を返します。プロフィール・レシピの検証などで発生した `ValueError` は、通常は `strata: ...` を標準エラーに出して例外の `exit_code`（既定 2）を返します。JSON 出力時はエラーを JSON にします（`strata_cli/cli.py:527-532,2166-2173`）。
- `--profile` の省略や値の欠落など parser エラーは argparse が usage とエラーを表示し、終了コード 2 で終了します（`strata_cli/cli.py:2223-2231`）。

## 根拠

- parser と option scope: `strata_cli/cli.py:255-290`
- コマンドから実際の実行への引き渡し、出力: `strata_cli/cli.py:1391-1464`
- profile 名・保存プロフィールの検証と保存先: `strata_control/profiles.py:25,38-55,150-166`
- レシピの profile 紐付け、読み込み、run 動作: `strata_control/recipes.py:32-64,93-114,180-196,363-439`
- 実行記録の保存先と上限: `strata_control/journal.py:1-5,25-27,47-63`

調査範囲は上記 checkout のソースです。同一 revision の CLI help は実行していません。索引上の予定パスは `strata-terminal/ops/run/--profile.md` で、コマンド階層・option scope と parser 定義は一致しています（`docs/cli/README.md:569-583`）。
