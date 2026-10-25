# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops create` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は無効 |

## 役割

レシピ作成時の通常の人間向け成功出力を抑えます。レシピの検証・保存処理や、作成先の権限・排他条件は変えません。

## 使い方

```sh
strata ops create restart --profile dev --kind runtime.restart --quiet
```

この例では `dev` プロファイルに `restart` という `runtime.restart` レシピを作成します。`--profile` と `--kind` は必須で、レシピ名は位置引数です（`strata_cli/cli.py:258-272`）。

## 値と既定値

値は不要です。`argparse` の `store_true` として登録され、既定値は `argparse.SUPPRESS` です。したがって指定時に真になり、省略時は Namespace に属性が作られませんが、実行時には `getattr(a, "quiet", False)` で偽として扱われます。短縮 alias はありません（`strata_cli/cli.py:510-515`, `strata_cli/cli.py:2236-2243`）。

`--quiet` は `ops_items` に含まれるすべての `ops` one-shot parser に共通追加されます。`create` にも適用されます（`strata_cli/cli.py:255-261`, `strata_cli/cli.py:510-515`）。

## 実行時の動作

`strata ops create` は `recipes.create(profile, name, kind)` を呼び出し、成功時には通常、人間向けに `Created recipe ...` を標準出力へ表示します（`strata_cli/cli.py:1412-1415`）。`--quiet` かつ `--output human`（既定）の場合、CLI は `_run` の標準出力を一時捕捉し、成功コードなら表示しません（`strata_cli/cli.py:2236-2247`）。

作成処理は引き続き実行されます。保存先はプロファイル設定ディレクトリ下の `.ops/<profile>/<name>.json` です。既定の設定ディレクトリは Unix 系で `$XDG_CONFIG_HOME/strata/profiles`（未設定時 `~/.config/strata/profiles`）、Windows で `%APPDATA%/Strata/profiles`（未設定時ユーザープロファイル下）です。`STRATA_PROFILE_DIR` があればそれが優先されます（`strata_control/profiles.py:38-45`, `strata_control/recipes.py:38-42`）。ディレクトリを作成し、ファイルは排他的に新規作成され、モード `0600` を指定して書き込み・同期されます。既存の同名レシピを上書きしません（`strata_control/recipes.py:130-150`）。

`--output json` または `--json` を併用すると、JSON 出力は `--quiet` より優先され、成功 JSON が標準出力に出ます。トップレベルの実行処理は `--json` を `output=json` に正規化し、JSON/JSONL のときは quiet の捕捉を行わず `_run` を直接呼びます（`strata_cli/cli.py:2232-2237`）。

## 適用条件と副作用

`strata ops create` は one-shot parser 群の一つであり、quiet の標準出力捕捉対象です。quiet が有効でも、プロファイルの読み込み、`.ops/<profile>` ディレクトリとレシピ JSON の作成は通常どおり起こります（`strata_cli/cli.py:510-515`, `strata_cli/cli.py:1412-1415`, `strata_control/recipes.py:130-150`）。

レシピ名とプロファイル名は小文字英字で始まり、小文字英字・数字・`_`・`-` のみ、長さ 1〜64 文字です。`--kind` は `runtime.restart`、`engine.calibrate.measure`、`components.verify` のいずれかを必須指定します。それぞれ初期パラメータは `startup_wait_s=300`、絶対パスの `.reports` ディレクトリ、空オブジェクトです（`strata_control/recipes.py:32-35`, `strata_control/recipes.py:117-127`）。

## 出力とエラー

- human 出力では、成功時の確認メッセージが `--quiet` により抑止されます。
- JSON 出力では quiet は効かず、成功時に `recipe` と `revision` を含む JSON が標準出力へ出ます（`strata_cli/cli.py:535-542`, `strata_cli/cli.py:1412-1415`, `strata_cli/cli.py:2232-2247`）。
- レシピ名・プロファイル名の不正、未対応の kind、同名レシピの存在などは失敗します。コマンド本体で捕捉される `ValueError` は人間向けエラーを標準エラーへ出し、`ProfileError` の既定終了コードは `2` です。ファイル操作エラーは整形され標準エラーに出され、終了コード `6` になります（`strata_control/recipes.py:32-35`, `strata_control/recipes.py:130-150`, `strata_cli/cli.py:2166-2183`）。
- quiet 実行中に `_run` が非ゼロで終わり、捕捉済み標準出力があれば、その内容は標準エラーへ戻されます。64 Ki 文字を超えて切り詰められた場合は、その旨の注記も標準エラーへ出ます（`strata_cli/cli.py:2196-2214`, `strata_cli/cli.py:2241-2248`）。
- 必須引数の欠落や不正な `--kind` など parser 段階のエラーは `_run` の捕捉より前に起こり、通常の argparse usage/error 表示と終了コード `2` になります（`strata_cli/cli.py:270-272`, `strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/cli.py:255-272` — `ops` の subcommand と `create` 引数。
- `strata_cli/cli.py:510-515` — one-shot parser 群への `--quiet` 登録。
- `strata_cli/cli.py:535-542`, `strata_cli/cli.py:1412-1415` — create の成功出力。
- `strata_cli/cli.py:2160-2188`, `strata_cli/cli.py:2196-2214`, `strata_cli/cli.py:2232-2248` — dispatch、エラー、quiet 出力処理。
- `strata_control/recipes.py:32-35`, `strata_control/recipes.py:38-59`, `strata_control/recipes.py:117-150` — 入力規則、保存先、既定値、排他的なファイル作成。
- `strata_control/profiles.py:38-45` — 設定ディレクトリの決定。
