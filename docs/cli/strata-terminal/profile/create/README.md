# `strata profile create`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile create` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/profiles.py` |
| 位置引数 | `name`（必須。保存する profile 名） |
| 必須オプション | `--from-config CONFIG.json` |
| 出力形式 | `--output human` または `--output json`（既定値: `human`）。`--json` は JSON 出力の別指定 |

## 役割

既存の run config JSON を参照する名前付き profile をユーザー設定領域に新規保存します。新しい profile は空の serving overrides から始まり、run config の内容は profile に複製しません。profile の作成自体はエンジンやサーバーを起動せず、ネットワークにも接続しません（`strata_cli/cli.py:71-74,958-963`、`strata_control/profiles.py:1-5,236-249`）。

## 基本的な使い方

```sh
strata profile create local --from-config /path/to/strata-model.json
```

JSON を機械処理する場合:

```sh
strata profile create local --from-config /path/to/strata-model.json --output json
```

`name` は小文字英字で始め、1〜64文字の小文字英字・数字・`_`・`-` で構成します。例では、実在する run config の絶対パスを指定してください（`strata_control/profiles.py:25,48-55,236-243`）。

## 主な動作

1. `--from-config` のパスを `~` 展開し、存在するパスへ解決します。run config は UTF-8 JSON object で、`args` が文字列配列、`exe` と `tokenizer` が空でない文字列である必要があります（`strata_control/profiles.py:135-147,236-243`）。
2. profile の初期データ（schema version `1`、指定名、解決後の絶対 `source_config`、空の `overrides`）を作ります（`strata_control/profiles.py:120-132,243`）。
3. 保存先ディレクトリに profile 名ごとのロックを取り、同名ファイルまたはシンボリックリンクがすでにあれば失敗します。新規ファイルは一時ファイルへの書き込み後に置換して保存します（`strata_control/profiles.py:185-210,213-233,244-249`）。
4. 成功後、保存 profile を読み直して revision を計算します。revision は保存データの SHA-256 の先頭16桁です（`strata_control/profiles.py:62-64,249`）。

既定の保存先は Windows では `%APPDATA%/Strata/profiles`（`APPDATA` が未設定ならホーム以下）、それ以外では `$XDG_CONFIG_HOME/strata/profiles`（未設定なら `~/.config/strata/profiles`）です。`STRATA_PROFILE_DIR` を設定すると保存先を置き換えます（`strata_control/profiles.py:38-45`）。

## 実行モードと出力

- 既定の human 出力は `Saved profile <name> at revision <revision>` です。
- `--output json` または `--json` は、成功時に `schema_version`、`ok`、`profile`、`revision` を含む JSON を stdout に出します。`--output` は `human` または `json` のみ受理します（`strata_cli/cli.py:73-74,508-515,535-542,958-963`）。
- `--quiet` は one-shot コマンド共通の指定です。human 成功出力を抑えますが、JSON 出力は維持します（`strata_cli/cli.py:508-515,2217-2248`）。
- 新規 profile の作成であり、同名 profile の更新・上書きには使えません。既存の profile を変更する場合は `strata profile set`、参照先を切り替える場合は `strata profile use-config` を使います（`strata_cli/cli.py:84-95,244-249`）。

## エラーと注意点

- `name` が規則に合わない場合、run config が存在しない・読めない場合、JSON 構造が必要条件を満たさない場合、または profile がすでに存在する場合は作成されません。名前や既存 profile の競合は通常終了コード `2`、run config の読み込み不成立は `5` です（`strata_control/profiles.py:30-35,48-51,135-147,236-247`）。
- 未知の引数や不正な `--output` 値は argparse が拒否し、usage とエラーを表示して終了コード `2` になります（`strata_cli/cli.py:40-45,73-74,2223-2231`）。
- 保存先へのアクセスなどで発生した OS エラーは CLI の共通エラー処理を通り、JSON モードでは JSON エラー、通常モードでは `strata:` で始まる stderr のメッセージになります（`strata_cli/cli.py:527-532,2166-2183`）。
- `--from-config` は profile が参照する run config を選ぶだけです。profile を作成しても参照先 config は変更されず、run config 内の実行引数・ファイルの妥当性すべてを検査する処理ではありません。確認するのは JSON と `args` / `exe` / `tokenizer` の形です（`strata_control/profiles.py:135-147,236-249`）。

## 関連文書

- [`strata profile` の概要](../README.md)
- [CLI 文書索引](../../../README.md) — `strata-terminal` のコマンド階層とオプション文書
- [`--from-config`](--from-config.md)・[`--output`](--output.md)・[`--json`](--json.md)・[`--quiet`](--quiet.md)
- [profile の一覧](../list/README.md)、[profile の編集](../set/README.md)、[run config の切り替え](../use-config/README.md)

## 根拠

- Strata `strata_cli/cli.py:69-74,508-516` — コマンド階層と parser 定義、`--json` / `--quiet` の追加。
- Strata `strata_cli/cli.py:527-542,958-963,2166-2183,2217-2248` — success/error 出力、コマンド実行、quiet 処理。
- Strata `strata_control/profiles.py:25-55,120-147` — profile 名、保存先、profile / run config の検証。
- Strata `strata_control/profiles.py:185-249` — ロック、atomic 保存、create の重複判定と作成処理。
