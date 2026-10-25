# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops init` |
| オプション | `--output` |
| 別名 | `--json`（`--output json` の alias） |
| 値 | `human` または `json` |
| 既定値 | `human` |

## 役割

初期化結果の表示形式を選びます。レシピの作成内容は変えず、成功結果を人向けの短い文または JSON で出力します。

## 使い方

```sh
strata ops init --profile my-profile --output json
```

`--profile` は必須です。`--output` は `human` / `json` のみ受理し、省略時は `human` です。`strata ops` の各 one-shot サブコマンドに同じ選択肢で登録されており、`--json` は `--output json` と同じ結果になります（`strata_cli/cli.py:255-267, 508-515, 2232-2235`）。

## 値と既定値

- `human`: 既定値。初回などレシピが作られた場合は `Created: restart, calibrate, check` の形式、作成対象が既にそろっている場合は `Recipes already initialized` を標準出力へ出します（`strata_cli/cli.py:1391-1398, 535-542`）。
- `json`: 成功時に1行の JSON を標準出力へ出します。schema は `schema_version: 1`、`ok: true`、`profile`、今回新規作成した ID の配列 `created` です。既に初期化済みなら `created` は空配列です（`strata_cli/cli.py:1395-1398, 535-542`）。
- `--json` は bool alias で、parse 後に `output` を `json` に切り替えます。両方を指定した場合も `--json` が最終的に優先されます（`strata_cli/cli.py:508-515, 2232-2235`）。
- それ以外の値は argparse の `choices` により拒否されます（`strata_cli/cli.py:267`）。

## 実行時の動作

`--output` の値は `_ops` で `machine` に変換され、`recipes.initialize(a.profile)` の結果を `_success` に渡します。したがってこのオプションは表示形式だけを切り替え、初期化の対象やファイル作成処理には使われません（`strata_cli/cli.py:1391-1398`）。

初期化は `restart`（`runtime.restart`）、`calibrate`（`engine.calibrate.measure`）、`check`（`components.verify`）を既定レシピとして扱います。同名ファイルがなければ作成し、既に正しい kind のレシピがあれば保持します。既存ファイルが壊れている、または kind が違う場合はエラーになり、異なる kind の既存レシピは上書きしません（`strata_control/recipes.py:153-177`）。保存先は選択 profile の設定ディレクトリ下 `.ops/<profile>/` です。ディレクトリを作る経路では private directory として作成し、POSIX では既存ディレクトリの所有者専用権限も検査します（`strata_control/recipes.py:38-59, 130-150`）。

## 適用条件と副作用

- `--profile` は必須で、保存済み profile を読み込めなければ初期化に失敗します（`strata_cli/cli.py:266`; `strata_control/recipes.py:38-40, 153-154`; `strata_control/profiles.py:150-166`）。profile 保存場所は `STRATA_PROFILE_DIR` があればその値、Windows では `%APPDATA%/Strata/profiles`（未設定時はホーム配下）、それ以外では `$XDG_CONFIG_HOME/strata/profiles`（未設定時は `~/.config/strata/profiles`）です（`strata_control/profiles.py:38-45`）。
- 初期化に伴い、未作成の既定レシピ JSON と必要なディレクトリを作成します。`--output` を指定しただけでは、追加のファイル副作用はありません（`strata_control/recipes.py:51-52, 153-177`）。
- `--quiet` を同時に指定すると human の成功メッセージは抑制されます。JSON 出力は quiet capture の対象外で、そのまま出力されます（`strata_cli/cli.py:514-515, 2236-2248`）。

## 出力とエラー

成功時は終了コード `0` です。`human` の成功文と `json` の成功オブジェクトはいずれも標準出力に出ます（`strata_cli/cli.py:535-542, 1395-1398`）。

保存 profile がない場合、recipe directory の symlink / 権限不整合、既存 recipe の不正形式や kind の不一致などは失敗になります。捕捉された `ValueError` / `OSError` はエラーメッセージを出し、例外に `exit_code` があればその値、なければ `2` を返します。JSON 指定時は `schema_version: 1`、`ok: false`、`error.code`、`error.message` の JSON を標準出力へ出し、human 指定時は `strata: ...` を標準エラーへ出します（`strata_cli/cli.py:527-532, 2166-2183`; `strata_control/profiles.py:30-35, 160-165`; `strata_control/recipes.py:47-58, 160-176, 184-195`）。値の選択ミスなど parser 段階の引数エラーは、`main` の `parse_known_args` により `--output` 形式のエラー出力処理へ進む前に argparse が扱います（`strata_cli/cli.py:2223-2235`）。

## 根拠

- parser とスコープ、既定値、許容値、`--json` / `--quiet` の追加: `strata_cli/cli.py:255-267, 508-515`
- 初期化 dispatch、成功出力、quiet 処理、例外出力: `strata_cli/cli.py:527-542, 1391-1398, 2166-2183, 2232-2248`
- 初期化対象・既存値との扱い・保存処理: `strata_control/recipes.py:38-64, 130-177`
- profile 必須条件と保存先決定: `strata_control/profiles.py:25, 30-55, 150-166`
