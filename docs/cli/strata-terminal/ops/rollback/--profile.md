# `strata ops rollback --profile`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops rollback` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み serving profile の名前。引数なしでは実行できない |

## 役割

`--profile` は、指定した操作レシピ `NAME` をどの serving profile のローカル保存領域から読み、どの領域の履歴へ戻すかを選びます。プロフィールの設定自体を巻き戻す指定ではありません。ロールバック先は別の必須引数 `--to REVISION` で選びます（`terminal/strata_cli/cli.py:283-305`、`terminal/strata_cli/cli.py:1506-1509`）。

## 使い方

```sh
# profile `local` にある `restart` レシピを指定 revision へ戻す
strata ops rollback restart --profile local --to 0123456789abcdef
```

`REVISION` は事前に `strata ops history restart --profile local` で確認できる履歴 revision を指定します。コマンド名・レシピ名・`--profile`・`--to` はそれぞれ別の値です（`terminal/strata_cli/cli.py:292-305`、`terminal/strata_cli/cli.py:1501-1509`）。

## 値と既定値

- 値を取る文字列オプションで、`ops` 配下の各操作 parser に共通して登録され、必須です。既定値、短縮別名、parser 上の選択肢はありません（`terminal/strata_cli/cli.py:283-295`）。
- 実処理では profile ID とレシピ名の両方が `^[a-z][a-z0-9_-]{0,63}$` に合う必要があります。さらに、その名前の保存済みプロフィールが読み込めなければ処理できません（`terminal/strata_control/profiles.py:25,48-55,153-173`、`terminal/strata_control/recipes.py:32-40`）。
- `ops rollback` ではレシピ名も位置引数で必須、`--to` も必須です。`--to` は16桁の小文字16進 revision でなければなりません（`terminal/strata_cli/cli.py:292-305`、`terminal/strata_control/recipes.py:253-256`）。

## 実行時の動作

CLI は `--profile` を `recipes.rollback(a.profile, a.name, a.to)` に渡します。レシピの保存先は、プロフィール設定ディレクトリの `.ops/<profile>/` です。設定ディレクトリは `STRATA_PROFILE_DIR` があればそれを使い、なければ Windows では `%APPDATA%/Strata/profiles`（`APPDATA` がなければユーザープロファイル下）、その他の OS では `$XDG_CONFIG_HOME/strata/profiles`（未設定時は `~/.config/strata/profiles`）です（`terminal/strata_cli/cli.py:1506-1509`、`terminal/strata_control/recipes.py:38-59`、`terminal/strata_control/profiles.py:38-45`）。

指定 revision の履歴ファイルを読み、revision の一致、ファイル形式・サイズ、保存内容と profile / recipe ID の整合を確認してから現行レシピへ保存します。保存時はロック下で現在 revision が変わっていないことを再確認し、現在版を履歴に保全して、復元内容を現行レシピファイルへ原子的に書き込みます。したがってこの操作は `--profile` が指す配下のレシピファイルを変更します。プロフィール本体や他 profile のレシピはこの処理の対象ではありません（`terminal/strata_control/recipes.py:253-275,214-237`）。

## 適用条件と副作用

プロフィールが保存されていない場合は失敗します。launch preset 名を直接指定してもこのコマンドの profile 引数としては別名解決されず、保存済み profile として読み込める必要があります（`terminal/strata_control/recipes.py:38-40`、`terminal/strata_control/profiles.py:153-173,176-184`）。

レシピと履歴は通常のファイルとして読み込まれ、POSIX ではレシピ・履歴ファイルに owner-only の権限が要求されます。recipe/history ディレクトリの symlink や不正な権限・形式、履歴内容と revision の不一致も拒否されます（`terminal/strata_control/recipes.py:38-59,72-86,180-196,253-273`）。

## 出力とエラー

成功時は既定の human 出力で `Restored recipe NAME: OLD_REVISION -> NEW_REVISION` を表示し、終了コード `0` です。`--output json` を指定すると、復元した recipe と変更前後の revision を含む JSON を出力します（`terminal/strata_cli/cli.py:1461-1464,1506-1509,566-573`）。

引数不足・形式不正は argparse のエラー（通常終了コード `2`）になります。profile / recipe / history が見つからない場合や保存内容が不正な場合はエラーとなり、通常の不正・未検出は `ProfileError` の既定コード `2`、保存ファイルや履歴の問題はコード `5`、編集中に recipe が変わった場合はコード `6` です。エラーは human 出力では stderr、JSON 出力時はエラー JSON になります（`terminal/strata_cli/cli.py:558-563,2248-2255`、`terminal/strata_control/profiles.py:30-35`、`terminal/strata_control/recipes.py:190-195,214-236,253-275`）。

## 根拠

- `terminal/strata_cli/cli.py:283-305` — `ops` サブコマンド群への `--profile` 登録、必須指定、および rollback の `NAME` / `--to`。
- `terminal/strata_cli/cli.py:1461-1464,1506-1509` — `--profile` を rollback helper へ渡し、成功結果を出力する処理。
- `terminal/strata_control/recipes.py:32-59,180-196` — profile と recipe の識別・保存場所・読み込み検証。
- `terminal/strata_control/recipes.py:214-237,253-275` — 履歴 revision の検証、現行版の保全、復元値の保存と失敗経路。
- `terminal/strata_control/profiles.py:25,38-55,153-184` — profile 名の形式、設定ディレクトリ、保存済み profile 読み込み。
- `terminal/strata_cli/cli.py:558-573,2248-2255` — 成功・失敗時の human / JSON 出力と終了コード処理。
