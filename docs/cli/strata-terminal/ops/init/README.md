# `strata ops init`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops init` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/recipes.py` |

## 役割

指定した保存済み profile 用に、Strata の型付き operator recipe の初期セットを作成します。作られるのは `restart`（runtime 再起動）、`calibrate`（engine calibration 測定）、`check`（components 検証）の3件です。recipe は profile と同じローカル設定領域の `.ops/<profile>/` 以下に JSON として保存されます。

このコマンドは recipe を準備するだけで、定義された runtime 操作・測定・検証を実行しません。個別 recipe の編集・計画確認・実行には [`strata ops` のコマンド一覧](../../../README.md)にある `create`、`set`、`plan`、`run` などを使います。

## 基本的な使い方

```sh
# 既存の saved profile に初期 recipe を用意
strata ops init --profile four-gpu

# 登録内容を確認
strata ops list --profile four-gpu
```

`--profile` は必須です。`--output json` を付けると機械可読 JSON を出力できます。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 人向け出力 | `strata ops init --profile four-gpu` | 作成した ID を `Created: ...` と表示します。既に初期化済みなら `Recipes already initialized` と表示します。 |
| JSON 出力 | `strata ops init --profile four-gpu --output json` | `schema_version`、profile ID、今回作成した ID 配列を JSON で返します。 |
| ヘルプ | `strata ops init --help` | `init` parser の usage と共通引数を表示します。 |

## 主な動作と副作用

- まず指定 profile を読み込み、profile が有効であることを確認します。profile ID は小文字英字で始まり、小文字英数字・`_`・`-` のみ、最大64文字です。
- `restart`、`calibrate`、`check` の各 recipe がなければ作成します。`restart` は `runtime.restart`、`calibrate` は `engine.calibrate.measure`、`check` は `components.verify` の kind です。
- 初期値は restart の `startup_wait_s: 300`、calibrate の report directory（profile 設定領域内の `.reports`）、check の空の params です。
- recipe 保存先は profile 設定ディレクトリの `.ops/<profile>/` です。POSIX ではディレクトリ mode `0700`、JSON ファイル mode `0600` を要求・利用します。書き込みは profile ごとの lock を使い、recipe ファイルは排他的作成（既存ファイルを上書きしない）です。初めに profile をロードするため、権限昇格実行で profile ファイルが読み取り不能になっている場合、共通 loader が owner 権限を修復してから読むことがあります。
- 同じ profile での再実行は、不足 recipe のみを作って既存の正しい recipe は保持します。3件がすべて揃っていれば変更せず正常終了します。
- 既定名の recipe が異なる kind で既に存在する場合はエラーになります。中身が壊れている、profile がない、保存先が symlink である、POSIX の所有者専用権限条件を満たさない場合も処理が失敗し得ます。

## 注意点

- `--profile` はプロファイル名であり、`strata profile create` などで既に作られた saved profile が必要です。未登録の profile をこのコマンドが作るわけではありません。
- 初期化された recipe は後続の `strata ops run` で明示的に実行するまで runtime の再起動や calibration を開始しません。
- 失敗時は人向け出力では `strata: ...` を stderr に出します。`--output json` ではエラー JSON を stdout に出します。終了コードは入力・profile エラーで通常 `2`、安全性・ファイル状態のエラーで `5`、OS ファイル操作エラーで `6` など、発生した例外に応じます。

## 関連文書

- [CLI 索引](../../../README.md) — `strata ops` の全コマンドと各 option 文書
- [`--help`](--help.md) — `strata ops init --help`
- [`--json`](--json.md) — 共通 JSON 出力 option
- [`--output`](--output.md) — human / JSON 出力形式
- [`--profile`](--profile.md) — 操作対象 profile

## 根拠

- `strata_cli/cli.py:255-267` — `ops` と各 action parser、`--profile` 必須、`--output` の選択肢と既定値。
- `strata_cli/cli.py:1391-1398` — init の dispatch、成功 payload と人向けメッセージ。
- `strata_cli/cli.py:527-541,2119-2173` — 成功・失敗の出力形式、ValueError 等のエラー変換。
- `strata_control/recipes.py:38-59,62-65` — profile 配下 `.ops/<profile>` の保存先とディレクトリ条件。
- `strata_control/recipes.py:117-127,153-177` — 既定 recipe の kind / params、既存 recipe を保つ初期化と不整合時の失敗。
- `strata_control/recipes.py:130-150` — lock 下での排他的作成、mode `0600`、既存ファイルを上書きしない作成。
- `strata_control/profiles.py:25,38-55,150-166` — profile ID、設定ディレクトリ、profile のロードと未作成・不正時のエラー。
- `docs/TERMINAL.md:96-115` — init 後の一覧・編集・plan・run の利用例。
- `docs/MANAGEMENT_PROTOCOL.md:13-15` — management recipe 操作の profile ID と実行処理に関する説明。

調査範囲は上記 checkout の Python CLI / recipe 実装とリポジトリ内利用者向け資料です。OS ごとの実際の ACL、配布済み CLI の差異は実機・Release artifact で確認していません。
