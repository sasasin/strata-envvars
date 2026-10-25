# `strata ops init --profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops init` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 必須の profile 名（文字列） |

## 役割

初期化対象となる保存済み serving profile を選び、その profile に紐づく operation recipe の初期セットを用意します。profile 自体を新規作成するオプションではありません。profile は事前に保存されている必要があります（`strata_cli/cli.py:1395-1398`、`strata_control/recipes.py:153-157`）。

## 使い方

```sh
strata ops init --profile PROFILE_NAME
```

`PROFILE_NAME` は作成済みの profile ID に置き換えます。機械可読な成功結果が必要なら `--output json` または `--json` を併用できます。

## 値と既定値

- 値は必須です。parser は `--profile` を `required=True` で登録し、既定値や型変換は指定していません（`strata_cli/cli.py:255-267`）。値の省略は argparse の usage error になります。
- profile 名は英小文字で始まり、続く文字は英小文字・数字・`_`・`-`、長さは最大64文字です。正規表現に一致しない値は profile 読み込み時に拒否されます（`strata_control/profiles.py:25`、`strata_control/profiles.py:48-55`）。空文字、英大文字、空白、64文字を超える名前も受理されません。
- 名前の検証後、profile は `STRATA_PROFILE_DIR` があればそのディレクトリから、それ以外は Windows では `%APPDATA%/Strata/profiles`（未設定時はホーム下の `AppData/Roaming/Strata/profiles`）、POSIX では `$XDG_CONFIG_HOME/strata/profiles`（未設定時は `~/.config/strata/profiles`）から読み込まれます（`strata_control/profiles.py:38-45`）。

## 実行時の動作

`strata ops init` の parser は `--profile` をこのサブコマンドを含む各 `ops` action に必須登録します。`init` の handler は値を `recipes.initialize(a.profile)` に渡し、その処理はまず対象 profile を読み込みます（`strata_cli/cli.py:255-267`、`strata_cli/cli.py:1391-1398`、`strata_control/recipes.py:153-157`）。このオプションの適用対象は `ops init` です。

初期化される recipe は次の3つです（`strata_control/recipes.py:153-157`）。

| ID | 種別 | 初期パラメーター |
| --- | --- | --- |
| `restart` | `runtime.restart` | `startup_wait_s: 300` |
| `calibrate` | `engine.calibrate.measure` | profile ディレクトリ下の `.reports` を指す絶対パス `report_dir` |
| `check` | `components.verify` | 空のパラメーター |

recipe は profile ディレクトリ内の `.ops/<profile>/` に保存されます。新規作成時は既存ファイルを排他的に作成するため上書きせず、ファイル mode は `0600` です。POSIX では保存ディレクトリとファイルの owner-only 条件も確認します（`strata_control/recipes.py:38-59`、`strata_control/recipes.py:130-150`、`strata_control/recipes.py:153-177`）。

## 適用条件と副作用

- 対象 profile が読み込み可能であることが前提です。存在しない profile は「保存されていない」旨のエラーになり、`strata profile create` を案内します（`strata_control/profiles.py:150-166`）。
- 既定 ID の recipe がすでに存在する場合、内容を読み込み検証します。種別が期待値と同じならその recipe は保持され、新規作成一覧には含まれません。異なる種別なら初期化はエラーになります（`strata_control/recipes.py:158-177`）。
- 新規 recipe があると `.ops` 以下にディレクトリと JSON ファイルを作成します。profile ファイル自体を書き換える処理はありません（`strata_control/recipes.py:130-150`、`strata_control/recipes.py:153-177`）。
- 同時実行などで作成時に同名ファイルが先にできた場合は、既存 recipe を読み直し、期待する種別ならそのまま続行します（`strata_control/recipes.py:134-150`、`strata_control/recipes.py:165-176`）。

## 出力とエラー

- 成功時の人間向け出力は、新規作成があれば `Created: restart, calibrate, check` のように作成 ID を列挙し、すべて初期化済みなら `Recipes already initialized` です。終了コードは `0` です（`strata_cli/cli.py:1395-1398`、`strata_cli/cli.py:535-542`）。
- `--output json` または `--json` では `{ "schema_version": 1, "ok": true, "profile": ..., "created": [...] }` 形式を stdout に出します（`strata_cli/cli.py:1391-1398`、`strata_cli/cli.py:535-542`、`strata_cli/cli.py:508-515`、`strata_cli/cli.py:2232-2236`）。
- profile 名など通常の入力エラーは `ProfileError` / `ValueError` として処理され、human 出力では `strata: <message>` を stderr に出して終了コード `2`（または例外が指定するコード）を返します。保存 profile がない場合や読み込み可能な recipe でない場合はコード `5` です（`strata_control/profiles.py:30-35`、`strata_control/profiles.py:150-166`、`strata_control/recipes.py:153-177`、`strata_cli/cli.py:2166-2173`、`strata_cli/cli.py:527-532`）。
- `--quiet` は `ops init` にも登録されますが、quiet 時に抑制されるのは stdout の人間向け情報です。JSON 出力では `_run` を通常どおり実行するため、JSON は抑制されません（`strata_cli/cli.py:508-515`、`strata_cli/cli.py:2232-2248`）。

## 根拠

- 索引上の配置・コマンド階層・リンク: `docs/cli/README.md:476-484`。
- parser 定義と適用スコープ: `strata_cli/cli.py:255-267`。
- `--profile` の初期化処理への引き渡しと成功文言: `strata_cli/cli.py:1391-1398`。
- profile ID と保存先、profile 読み込み失敗: `strata_control/profiles.py:25`、`strata_control/profiles.py:38-55`、`strata_control/profiles.py:150-166`。
- 初期 recipe、既存 recipe の扱い、保存処理: `strata_control/recipes.py:117-177`。
- help の補助確認: 同一 checkout の `python strata.py ops init --help` は `--profile PROFILE` を必須として表示し、parser 定義と一致しました。

調査範囲は上記 commit の source checkout です。別の Release artifact やインストール済み CLI の挙動は照合していません。
