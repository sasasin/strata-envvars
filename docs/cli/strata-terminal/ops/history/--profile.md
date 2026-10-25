# `strata ops history --profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops history` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み profile の ID（文字列） |

## 役割

履歴を表示する recipe と、その recipe 履歴の保存領域を profile ID で指定します。recipe 名は別の位置引数です。`--profile` は `ops` 配下の各操作 parser に共通で必須です。

## 使い方

```sh
strata ops history restart --profile four-gpu
```

`restart` は recipe 名、`four-gpu` は保存済み profile ID です。機械可読形式が必要なら `--output json` または `--json` を追加できます。

## 値と既定値

- 値は1つの文字列で、省略できません。既定値はありません。parser は `required=True` で登録しています。
- 値の形式は先頭が小文字英字で、続く文字は小文字英字・数字・`_`・`-`、長さは1〜64文字です。大文字、空文字、その他の記号は受理されません。
- recipe 名にも同じ形式制約が適用されます。
- このオプションに数値変換や列挙値の選択肢はありません。

## 実行時の動作

指定値は `recipes.history(profile, name)` に渡されます。処理は profile を読み込んで検証し、`.ops/<profile>` 以下の指定 recipe を読み込みます。現在の recipe revision を先頭に置き、履歴ディレクトリにある過去 revision を `saved_at` の新しい順に返します。人間向け出力は各 revision と `current` / `saved` の印、JSON 出力は `profile`、`recipe`、`history` を含む成功オブジェクトです。

履歴ディレクトリがまだなければ、過去 revision の項目はなく、現行 revision のみが返ります。この経路は履歴を読み取るもので、履歴ディレクトリを作成したり recipe を変更したりしません。recipe の作成・編集で過去版が保存されます。

`--output` の既定値は `human` です。`--json` は `ops history` にも追加される one-shot 共通オプションで、指定すると JSON 出力になります。`--quiet` も共通 parser に追加され、人間向け成功出力を抑制します。

## 適用条件と副作用

- profile ID はユーザーの profile 保存領域にある保存済み profile を指します。保存場所は `STRATA_PROFILE_DIR` が指定されればその値、未指定なら Windows は `APPDATA/Strata/profiles`（APPDATA がなければユーザーホーム配下）、それ以外は `XDG_CONFIG_HOME/strata/profiles`（未指定時は `~/.config/strata/profiles`）です。
- profile ファイル、recipe ファイル、存在する履歴ディレクトリを検査・読み取りします。profile の読み取りでアクセス拒否が起きた場合、実装は Strata 管理ファイルのアクセス権修復を試して再読込することがあります。
- recipe / 履歴ディレクトリがシンボリックリンク、通常ファイルでない、または POSIX で所有者限定の権限でない場合は拒否されます。履歴エントリとして採用するファイルは、16桁の小文字16進 revision 名で、通常ファイルかつシンボリックリンクでないものに限られます。

## 出力とエラー

- 成功時の人間向け出力は revision ごとの1行です。JSON では `schema_version: 1` と `ok: true` を含むオブジェクトが stdout に出ます。
- 指定 profile が保存されていない場合や recipe が存在しない場合、recipe の内容が不正な場合、検査対象のパスが安全条件を満たさない場合は失敗します。人間向けエラーは `strata: ...` として stderr に出て、JSON モードではエラーオブジェクトが stdout に出ます。
- `ProfileError` の通常終了コードは2です。profile / recipe の欠落や不正ファイルなど、明示的にコード5を指定する失敗もあります。

## 根拠

- parser のコマンド階層、位置引数、必須 `--profile`、出力形式、`--json` / `--quiet` の追加: `strata_cli/cli.py:255-267`, `strata_cli/cli.py:508-515`。
- `history` の呼び出し、返却値と表示: `strata_cli/cli.py:1391-1394`, `strata_cli/cli.py:1431-1435`。
- profile ID の書式、保存場所、profile 読込とアクセス修復: `strata_control/profiles.py:25`, `strata_control/profiles.py:38-50`, `strata_control/profiles.py:150-166`, `strata_control/private_files.py:476-484`。
- recipe profile / 名前検証、profile 読込、履歴パスの安全確認: `strata_control/recipes.py:32-35`, `strata_control/recipes.py:38-64`, `strata_control/recipes.py:71-86`, `strata_control/recipes.py:180-196`。
- 履歴の抽出条件と並び順: `strata_control/recipes.py:240-250`。
- 成功・失敗時の stdout / stderr と終了コード処理: `strata_cli/cli.py:527-542`, `strata_cli/cli.py:2166-2183`; `ProfileError` の既定終了コード: `strata_control/profiles.py:30-35`。
