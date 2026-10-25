# `strata ops list`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops list` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/recipes.py`、`strata_control/profiles.py` |

## 役割

指定した保存済み serving profile に属するローカル operator recipe を一覧表示します。recipe は実行可能なコマンド文字列ではなく、Strata の既存 operation に結び付いた型付き設定として保存されます（`strata_control/recipes.py:1-5,28`）。このコマンドは一覧を読み取るもので、recipe の作成・編集・実行は行いません。

## 使い方

```sh
# recipe を人向けの形式で表示
strata ops list --profile my-profile

# JSON で表示（--json は --output json の別表記）
strata ops list --profile my-profile --json
```

`--profile` は必須です。`--output` は `human` または `json` を受け付け、既定値は `human` です。`--json` は one-shot コマンド共通 parser に追加され、解析後に `--output json` と同じ設定になります。`--quiet` も受理され、人向け出力を抑止します（`strata_cli/cli.py:255-268,508-515,2232-2248`）。

## 実行時の動作

CLI は `recipes.list_recipes(profile)` を呼び出します。まず保存済み profile を読み込み、レシピ保存先を確認します。profile は `STRATA_PROFILE_DIR` が設定されていればその場所、未設定なら Windows では `%APPDATA%/Strata/profiles`（`APPDATA` 未設定時はホーム下）、それ以外では `$XDG_CONFIG_HOME/strata/profiles`（`XDG_CONFIG_HOME` 未設定時は `~/.config/strata/profiles`）を基点とします（`strata_control/profiles.py:38-45`; `strata_control/recipes.py:38-42`）。

レシピは `<profile-dir>/.ops/<profile>/*.json` からファイル名順に列挙されます。小文字英字で始まり、小文字英字・数字・`_`・`-` だけで構成された ID の JSON ファイルが対象です。有効な recipe は `id`、`kind`、内容 revision を返し、読み込み・検証に失敗した recipe は `id` と `error` を含めて一覧に残します（`strata_control/recipes.py:199-211`）。recipe ディレクトリが存在しなければ空一覧です。

## 出力と注意点

- 人向け出力では各 recipe を `<id>  <kind>` 形式で表示します。エラーのある項目は kind の代わりにエラー文を表示します。空一覧なら `No recipes; use strata ops init --profile NAME` と案内します（`strata_cli/cli.py:1399-1403`）。
- `--output json` または `--json` では、成功を示す `schema_version: 1` と `ok: true` に `profile` と `recipes` を含む JSON を標準出力へ出します。空一覧は `recipes: []` です（`strata_cli/cli.py:535-542,1399-1402,2232-2235`）。
- 指定 profile が保存されていない、profile が不正、recipe 保存場所が symlink、または POSIX でディレクトリ権限が owner-only でない場合などはエラーになります。profile 未保存は終了コード 5 です。JSON 出力時のエラーは `ok: false` とエラー情報を JSON で返し、人向けの場合は `strata: ...` を標準エラーへ出します（`strata_control/profiles.py:150-166`; `strata_control/recipes.py:38-59,180-196`; `strata_cli/cli.py:527-532,2166-2188`）。
- `--quiet` は人向け stdout を抑止します。JSON 出力とは併用されず、エラーは通常のエラー経路で示されます（`strata_cli/cli.py:2236-2248`）。
- 一覧取得時、profile ファイルが elevated 実行で作られた権限状態にある場合、profile 読み込み処理が権限修復を行うことがあります（`strata_control/profiles.py:150-166`）。recipe の一覧処理自体は recipe を書き換えません。

## 関連文書

- [`strata ops` の索引・オプション一覧](../../../README.md#strata-ops-ops)
- [`strata ops` コマンド概要](../README.md)
- [`strata ops init`](../init/README.md)

## 根拠と調査範囲

- `strata_cli/cli.py:255-268,508-515` — サブコマンド、必須 `--profile`、出力形式、および共通の `--json` / `--quiet` parser 定義。
- `strata_cli/cli.py:1391-1403,527-542,2232-2248` — list 分岐、出力内容、JSON alias と quiet の処理。
- `strata_control/recipes.py:38-59,199-211` — profile 確認、recipe 保存場所の安全性確認、列挙・検証エラーの扱い。
- `strata_control/profiles.py:38-45,150-166` — profile 保存先と読み込み、未保存時の失敗および権限修復経路。

この記述は上記 commit の checkout 内のソースを対象とし、別 revision の配布 CLI や Release artifact は照合していません。OS ごとの実ファイル権限の挙動はコード上の条件を記載しており、各 OS での実行確認はしていません。
