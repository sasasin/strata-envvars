# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops list` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み serving profile の名前。小文字英字で始まり、小文字英字・数字・`_`・`-` からなる最大64文字 |

## 役割

`strata ops list` が列挙する操作レシピの保存先 profile を選びます。値はファイルパスや run config のパスではなく、`strata profile` で保存した profile の ID です。profile の検証後、`<profile-dir>/.ops/<profile>/` にあるレシピ JSON を読みます（parser: `strata_cli/cli.py:255-267`、処理: `strata_cli/cli.py:1399-1403`、保存先: `strata_control/recipes.py:38-64`）。

## 使い方

```sh
strata ops list --profile work
```

JSON 形式で一覧を得る場合は、同じコマンドに `--output json` を付けます。

```sh
strata ops list --profile work --output json
```

## 値と既定値

値は必須で、既定値はありません。空値や profile ID の形式に合わない文字列は profile 名の検証で拒否されます。形式は `[a-z][a-z0-9_-]{0,63}` です（`strata_control/profiles.py:25,48-55`）。引数がない場合や値がない場合は `argparse` の構文エラーになります（`strata_cli/cli.py:255-267,2223-2231`）。

さらに、指定名の profile ファイルが存在し、JSON と profile schema が有効である必要があります。profile は `schema_version: 1`、一致する `id`、絶対パスの `source_config`、および対応済み serving override からなる構造を要求します（`strata_control/profiles.py:98-123,150-166`）。

## 実行時の動作

`list` action は `recipes.list_recipes(a.profile)` を呼び出します。そこではまず profile をロードして妥当性を確認し、profile ディレクトリを決めます。該当 `.ops/<profile>` ディレクトリがなければ空一覧を返し、存在する場合は `*.json` のうち profile ID 形式の stem を持つファイルを名前順に確認します（`strata_cli/cli.py:1399-1403`、`strata_control/recipes.py:38-64,199-211`）。profile ディレクトリの基点は、`STRATA_PROFILE_DIR` があればその値、なければ OS ごとの標準 profile 配下です（`strata_control/profiles.py:38-45`）。

各レシピは通常ファイルで64 KiB以下であること、JSON と recipe schema が有効であることを検査します。有効な項目は ID・kind・revision を返し、個々のレシピの検証に失敗した場合はその項目に ID と error を含めて一覧へ残します（`strata_control/recipes.py:93-114,180-210`）。このオプションは対象 profile の選択に使われ、レシピの実行や編集は行いません。

## 適用条件と副作用

対象 profile 自体が見つからない、profile JSON が不正、または profile ディレクトリが安全条件を満たさない場合は一覧全体の処理が失敗します。POSIX では profile 保存ディレクトリと既存の `.ops` 関連ディレクトリ・レシピに所有者限定の権限を要求します。Windows では profile 読込時にアクセス拒否が起きると、Strata のユーザーデータ領域でアクセス権を修復して再読込する経路があります。そのため通常は読み取り中心ですが、Windows のこの回復経路では ACL 等が変更されることがあります（`strata_control/recipes.py:38-59,180-195`、`strata_control/profiles.py:150-166`、`strata_control/private_files.py:442-484`）。

## 出力とエラー

成功時の既定の human 出力は各レシピの `id  kind`（不正レシピは `id  error`）です。該当レシピがない場合は `No recipes; use strata ops init --profile NAME` と表示します。`--output json` では `schema_version`, `ok`, `profile`, `recipes` を持つ JSON を stdout に出します（`strata_cli/cli.py:1399-1403,535-542`）。

profile の不在は `ProfileError` の終了コード5、形式や内容の不正は通常2となり、human 出力では stderr、JSON 出力では `ok: false` と error オブジェクトを stdout に出します。ファイルシステムの `OSError` は一般に終了コード6として処理されます（`strata_control/profiles.py:30-35,48-55,150-166`、`strata_cli/cli.py:2166-2183,527-532`）。個々の recipe の検証エラーは一覧項目に記録され、コマンド全体の失敗にはしません（`strata_control/recipes.py:199-210`）。

## 根拠

- parser と option scope: `strata_cli/cli.py:255-267`。`ops` の action parser 群に `--profile` を必須引数として追加し、`list` に位置引数を設けていません。
- `list` の呼び出しと出力: `strata_cli/cli.py:1391-1403`。
- profile ID、保存先基点、profile schema とロード: `strata_control/profiles.py:25-55,98-123,150-166`。
- profile 配下の recipe directory、列挙、個別 recipe validation: `strata_control/recipes.py:32-64,93-114,180-211`。
- Windows のアクセス回復経路: `strata_control/private_files.py:442-484`。
- 調査範囲: 上記 revision の Terminal CLI parser と呼び出し先を確認しました。別 platform の実機挙動、Release 配布物、同一 revision の `--help` 実行結果は確認していません。
