# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile create` |
| オプション | `--output` |
| 別名 | なし（`--json` は別 parser action のショートカット） |
| 値 | `human` または `json` |

## 役割

作成した profile と revision を人向けテキスト、または機械処理向け JSON のどちらで標準出力へ出すかを選びます。profile の保存先を指定するオプションではありません。保存先は `STRATA_PROFILE_DIR`、または OS ごとの設定ディレクトリで決まります。

## 使い方

```sh
strata profile create demo --from-config /absolute/path/to/run-config.json --output json
```

`--from-config` は必須です。人向け出力は既定なので、次のように省略できます。

```sh
strata profile create demo --from-config /absolute/path/to/run-config.json
```

## 値と既定値

- `human` と `json` のみ受理されます。省略時は `human` です。parser は選択肢外の値を拒否します。
- 同じ `--output` を複数回指定した場合は、argparse の通常の値格納動作により最後に指定した値が使われます。
- `--json` は `profile create` にも追加される別フラグで、指定時は `--output json` と同じ結果になります。`--json` と `--output human` を併記した場合も、CLI の正規化処理が `output` を `json` に設定します。
- `--quiet` もこの one-shot コマンドに追加されます。人向け成功メッセージを抑制しますが、`--output json` の出力は抑制しません。

## 実行時の動作

`--output` は出力形式を決めるだけで、profile の作成自体を有効・無効にしません。コマンド処理は `profiles.create(name, from_config)` を必ず呼び、その後 `--output json` なら `schema_version`, `ok`, `profile`, `revision` を含む 1 行の JSON を標準出力へ出します。`human` なら `Saved profile <name> at revision <revision>` を出します。

profile は `STRATA_PROFILE_DIR` が設定されていればそのディレクトリ、Windows では `%APPDATA%\Strata\profiles`（`APPDATA` がなければユーザーの Roaming 配下）、それ以外では `$XDG_CONFIG_HOME/strata/profiles`（未設定時は `~/.config/strata/profiles`）に保存されます。実装はディレクトリを作成し、同名 profile が既にある場合は上書きせず失敗します。新規ファイルは一時ファイル経由で書き込み・同期した後に置き換えます。

## 適用条件と副作用

`--output` の適用先は `strata profile create` のみです。`--from-config` のパスは `~` を展開して実在パスへ解決し、その JSON がオブジェクトで `args` が文字列配列、`exe` と `tokenizer` が空でない文字列であることを確認します。作成される profile は schema version 1、指定名、解決済み `source_config`、空の `overrides` を持ちます。元の run config を変更したり、サーバーを起動したり、ネットワークへ接続したりはしません。

## 出力とエラー

- `human` 成功時は標準出力に成功メッセージ、`json` 成功時は標準出力に成功 JSON を出し、終了コード 0 です。
- 実行時エラーは `human` では `strata: <message>` を標準エラーへ出し、`json` では `schema_version: 1`, `ok: false`, `error: {code, message}` の JSON を標準出力へ出します。profile 名不正、同名 profile の存在、run config の検証失敗などは失敗します。同名 profile の存在は上書きされません。
- 不正な `--output` 値など parser エラーは argparse が usage とエラーを標準エラーへ出し、終了コード 2 で終了します。
- profile 名は小文字英字で始まり、以降は小文字英字・数字・`_`・`-` のみ、長さ 1〜64 文字です。run config が利用できない場合は profile エラー終了コード 5 になります。

## 根拠

- `strata_cli/cli.py:69-74` — `profile create` parser、必須 `--from-config`、`--output` の選択肢と既定値。
- `strata_cli/cli.py:508-515` — one-shot parser 群に `--json` と `--quiet` を追加。
- `strata_cli/cli.py:527-542` — JSON/人向け成功・失敗の出力先と形式。
- `strata_cli/cli.py:958-963` — `profiles.create` 呼び出しと、`--output` に応じた成功出力。
- `strata_cli/cli.py:2217-2247` — `--json` の正規化、および quiet 時に成功 stdout を抑制する処理。
- `strata_control/profiles.py:38-45` — profile 保存ディレクトリの選択。
- `strata_control/profiles.py:48-55` — profile 名の検証とファイル名。
- `strata_control/profiles.py:135-147` — run config JSON の読み込み・必須フィールド検証。
- `strata_control/profiles.py:185-210` — profile ディレクトリ作成と排他ロック。
- `strata_control/profiles.py:213-249` — 一時ファイル経由の保存、既存 profile の拒否、作成処理。
- `strata_control/private_files.py:320-346` — 作成される profile ディレクトリのユーザー専用権限処理（POSIX は mode `0700`。Windows は ACL を設定し、ACL 設定失敗時は継承規則を残す）。

調査は上記 checkout のソースに基づきます。CLI の `--help` は実行せず、Release 配布物や Windows 実機での動作照合は行っていません。
