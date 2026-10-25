# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops create` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み serving profile の名前（必須） |

## 役割

作成する操作レシピをどの保存済み serving profile に関連付けるかを指定します。profile 名を受け取り、run-config のパスとしては解釈しません。`strata ops create` はレシピ定義を作成するコマンドで、作成した操作を実行するものではありません。

## 使い方

```sh
strata ops create restart --profile my-profile --kind runtime.restart
```

`my-profile` は既に保存されている profile の ID、`restart` は新しいレシピ名です。`--kind` も必須です。

## 値と既定値

- `--profile` は値を1つ取ります。`ops` の `create` を含む各 one-shot 操作 parser に `required=True` で登録され、既定値はありません（`strata_cli/cli.py:255-267`）。
- profile ID は小文字英字で始まり、小文字英字・数字・`_`・`-` のみ、最大64文字です。レシピ名も同じ規則で検証されます（`strata_control/profiles.py:25,48-55`; `strata_control/recipes.py:32-35`）。
- `--kind` の必須選択肢は `runtime.restart`、`engine.calibrate.measure`、`components.verify` です（`strata_cli/cli.py:270-272`）。
- profile を省略すると argparse が usage とエラーを stderr に出して終了コード 2 で終了します。未登録の kind も parser が拒否します（`strata_cli/cli.py:270-272`; 標準 `argparse` parser は `strata_cli/cli.py:40-45` で構築）。

## 実行時の動作

parser の値は `a.profile` として `_ops` から `recipes.create(a.profile, a.name, a.kind)` に渡されます（`strata_cli/cli.py:1391-1394,1412-1415`）。profile は `profiles.load()` で読み込まれる保存済み profile であり、存在しない profile 名を新規作成する処理や、設定ファイルのパスを受け入れる処理はありません（`strata_control/recipes.py:38-41`; `strata_control/profiles.py:38-55,150-166`）。profile ディレクトリは `STRATA_PROFILE_DIR` があればその値（`~` 展開後）、なければ Windows の `%APPDATA%` または既定 AppData、POSIX の `$XDG_CONFIG_HOME` または `~/.config` 以下です（`strata_control/profiles.py:38-45`）。

レシピは `<profile_dir>/.ops/<profile>/<name>.json` に保存されます。作成時は profile とレシピ ID を検証し、kind ごとの初期値を組み立てます。`runtime.restart` は `startup_wait_s: 300`、`engine.calibrate.measure` は profile directory 下の `.reports` を指す `report_dir`、`components.verify` は空の `params` が初期値です（`strata_control/recipes.py:38-64,117-127`）。

作成時には profile ごとの lock を取り、`O_CREAT | O_EXCL` で新規ファイルだけを作るため、既存レシピを上書きしません。ファイルは POSIX では mode `0600` で開き、flush と fsync 後に読み戻して revision を返します。`.ops` と profile 用ディレクトリも必要に応じて private directory helper で作成されます（`strata_control/recipes.py:130-150,38-59`）。

## 適用条件と副作用

- 指定 profile が保存済みで、profile ファイルとして有効である必要があります。profile のロード時には profile の形、ID、source-config の絶対パス、override 値も検証されます（`strata_control/profiles.py:120-132,150-166`）。
- レシピファイルが既に存在する場合はエラーになり、上書き・更新はしません（`strata_control/recipes.py:134-141`）。
- profile ID またはレシピ名が不正、profile が未保存、profile/recipe の保存先が symlink・非ディレクトリの場合は作成を拒否します。POSIX では既存の profile / recipe directory が mode `0700`、recipe file が mode `0600` でない場合も拒否します（`strata_control/recipes.py:32-58`; `strata_control/profiles.py:48-55,150-166`）。
- レシピ JSON の新規作成だけがこのコマンドの成功経路です。実行中 service の再起動、calibration、component 検証は行いません。これらは保存された kind を後続の `ops run` が扱う処理です（`strata_cli/cli.py:1412-1415`; `strata_control/recipes.py:3-5`）。

## 出力とエラー

既定の human 出力は `Created recipe <name> (<kind>) at <revision>`、`--output json` または alias の `--json` は schema version 1、`ok: true`、recipe、revision を含む JSON です（`strata_cli/cli.py:508-515,535-542,1412-1415`）。

アプリケーション側の `ValueError` は `_error` を通り、human 時は `strata: ...` を stderr、JSON 時は `ok: false` と error code/message を stdout に出します。profile 未保存は code 5、ID 不正・同名レシピなど既定の `ProfileError` は code 2 です（`strata_cli/cli.py:527-532,2166-2173`; `strata_control/profiles.py:30-35,160-165`; `strata_control/recipes.py:130-141`）。ファイルアクセス等の `OSError` は汎用のファイルエラー文と code 6 に変換されます（`strata_cli/cli.py:2176-2183`）。

## 根拠

- parser と `--profile` / `--kind` の宣言: `strata_cli/cli.py:255-272`
- 共通 `--json` / `--quiet` の追加: `strata_cli/cli.py:508-516`
- コマンドから recipe 作成 helper への引き渡しと成功出力: `strata_cli/cli.py:1391-1415`
- profile directory、ID、保存済み profile のロード: `strata_control/profiles.py:25,38-55,120-132,150-166`
- レシピ保存先、初期値、排他的な新規作成: `strata_control/recipes.py:28-64,117-150`
- 例外の表示と終了コード: `strata_cli/cli.py:527-542,2166-2183`

この調査では parser と実装ソースを確認し、CLI `--help` は実行していません。実ファイルシステム上での作成結果、OS ごとの ACL、保存ディレクトリの実在状態は実行環境に依存するため確認対象外です。
