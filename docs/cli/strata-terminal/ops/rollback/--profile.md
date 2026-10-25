# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops rollback` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み profile の名前。必須。 |

## 役割

ロールバックする operation recipe の保存先となる Strata の serving profile を名前で指定します。このコマンドで `--profile` に JSON ファイルのパスを渡す形式ではありません。profile 名と recipe 名は別の引数です。

## 使い方

```sh
strata ops rollback restart --profile local --to 0123456789abcdef
```

`restart` は recipe 名、`local` は保存済み profile 名、`--to` の値は戻す recipe revision です。例の revision は書式を示す値であり、実際には `strata ops history restart --profile local` などで確認できる保存済み revision を指定します。

## 値と既定値

- `--profile` は値を1つ取り、必須です。既定値はありません。`ops` の全 action parser が同じ `required=True` の定義を共有します。
- 値は `[a-z][a-z0-9_-]{0,63}` に一致する profile 名で、先頭は小文字英字、以降は小文字英字・数字・`_`・`-`、長さは1〜64文字です。パスや大文字を含む値は profile 名として受理されません。
- 指定した profile が未保存の場合はエラーになります。

## 実行時の動作

parser は `--profile` を `a.profile` に格納します。rollback 分岐はこの値と位置引数の recipe 名、および必須の `--to REVISION` を `recipes.rollback()` に渡します。profile 名は `strata_control.profiles.profile_dir()` 配下の保存済み profile と `.ops/<profile>/<recipe>.json` の recipe 保存領域を選びます。保存領域は `STRATA_PROFILE_DIR`、Windows では `APPDATA`、それ以外では `XDG_CONFIG_HOME`（未設定時はホーム配下の `.config`）に基づきます。

この option 自体は serving profile の内容を書き換えず、rollback 対象を profile ごとに特定します。ただし recipe 操作の前提として保存済み profile を読み込みます。profile 読み込みは、管理者実行などでロックされた profile ファイルのアクセス権を必要に応じて修復する処理を含みます。実際の recipe の復元では、指定 revision の履歴 JSON を検証して現在の recipe と入れ替え、現在版を履歴に保全します。値は `--to` が指定する履歴内容の適用先を決めるため、異なる profile を指定すれば別の recipe store が対象になります。

成功時は既定の human 出力で復元前後の revision を表示します。`--output json` またはその alias の `--json` を併用すると、recipe と `previous_revision` / `revision` を含む JSON を出力します。`--quiet` も parser では受理されますが、この rollback 成功分岐はその値を参照せず、human 出力を抑止しません。

## 適用条件と副作用

- 保存済み profile、および指定 recipe とその履歴が読み取り可能である必要があります。recipe データは通常 `profiles` 設定領域の `.ops/<profile>/` 以下から読み取られます。
- recipe の `--to` は16桁の小文字16進 revision でなければなりません。該当履歴が存在し、その内容の SHA-256 先頭16桁がファイル名と一致し、現在の profile と recipe ID に対して有効な schema である必要があります。
- rollback は現在 revision を比較してロック下で更新します。更新時は現在版を `.history/<recipe>/<current-revision>.json` に保管し、指定履歴の内容で recipe JSON を原子的に置き換えます。指定 revision と現行内容が既に同一なら `save()` はファイルを更新しません。
- recipe と履歴は通常最大64 KiBの通常ファイルであることが確認され、POSIX では owner-only 権限が要求されます。profile / recipe 名の不正、ファイル種別・サイズ・権限の問題、履歴の欠落・不整合は失敗要因になります。

## 出力とエラー

- `--profile` がない、または値を伴わない場合、`argparse` が usage/error を表示して終了コード2で拒否します。
- profile 名が不正、保存 profile が存在しない、recipe や revision が見つからない、履歴が壊れている場合、CLI は通常 stderr に `strata: <理由>` を出し、`ProfileError` の終了コードを返します。エラーに `--json` / `--output json` を指定すると JSON error object を出力します。一般の入力エラーはコード2、保存データやファイルの問題はコード5、編集中に内容が変わった場合はコード6です。
- 成功時は終了コード0です。人間向け出力は `Restored recipe <name>: <old> -> <new>`、JSON 出力には recipe と復元前後 revision が含まれます。

## 根拠

- parser の `ops` action、共通 `--profile`、rollback 専用 `--to`、および `--json` / `--quiet`: `strata_cli/cli.py:255-277`, `strata_cli/cli.py:508-516`
- rollback の dispatch と成功出力: `strata_cli/cli.py:1391-1394`, `strata_cli/cli.py:1436-1439`
- profile 名の形式と保存先: `strata_control/profiles.py:25`, `strata_control/profiles.py:38-55`
- 保存 profile の読み込みと権限修復: `strata_control/profiles.py:150-166`
- recipe 領域の profile 検証、パス構成、POSIX 権限条件: `strata_control/recipes.py:32-64`
- recipe 読み込み時の通常ファイル・サイズ検証と欠落時のエラー: `strata_control/recipes.py:180-196`
- 履歴の保存、atomic 更新、rollback revision 検証と復元処理: `strata_control/recipes.py:214-237`, `strata_control/recipes.py:253-275`
- JSON / human 成功出力とエラー出力: `strata_cli/cli.py:527-542`
- 指定 revision と調査日の確認: 対象リポジトリ `git rev-parse HEAD` / `git status --short --branch`（commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、`main...origin/main`、変更表示なし）。
