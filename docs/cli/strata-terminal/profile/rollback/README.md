# `strata profile rollback`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile rollback` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/profiles.py` |
| 必須引数 | `NAME` と `--to REVISION` |
| 出力形式 | 人間向け（既定）または JSON |

## 役割

指定した保存済み profile の履歴 revision の内容を現在の profile に復元します。復元対象は profile JSON であり、setup が生成した run config は書き換えず、稼働中の server も再起動・変更しません。復元した profile は以後の起動で使われます（[profile 管理の説明](../../../../TERMINAL.md)）。

## 使い方

まず履歴を確認し、表示された保存済み revision を指定します。

```sh
strata profile history local
strata profile rollback local --to 0123456789abcdef
```

JSON で結果を受け取る例:

```sh
strata profile rollback local --to 0123456789abcdef --json
```

`NAME` は profile 名です。小文字英字で始まり、小文字英数字、`_`、`-` を使う1〜64文字の形式が受理されます。`--to` は省略できません。

## 実行時の動作

1. CLI は現在の profile を読み込み、現在 revision を得ます。
2. `--to` の値が16文字の小文字16進数か確認し、`.history/NAME/REVISION.json` を開きます。
3. 履歴ファイルが通常ファイルであること、ファイル内容の SHA-256 先頭16文字が指定 revision と一致すること、JSON が現在の profile 名に対応する schema・値であることを検証します。
4. 検証した内容を保存処理へ渡します。profile の同時変更がないことを lock 内で再確認し、変更があれば中断します。変更がある場合、現在の profile を履歴に退避してから、新しい内容を一時ファイル経由で原子的に置き換えます。

履歴に格納されているのは過去の profile の内容です。復元結果は保存処理でシリアライズされ、その内容から現在 revision が算出されます。人間向け成功表示は `Restored profile NAME: PREVIOUS -> REVISION; running instances are unchanged` です。JSON は `schema_version`、`ok`、`profile`、`previous_revision`、`revision` を含みます。すでに現在の内容と復元対象が同じ場合、保存処理は変更を行わず現在 revision を返します。

## 実行モードと副作用

これは profile 1件を変更する one-shot コマンドです。保存先は `STRATA_PROFILE_DIR` があればその値、Windows では `%APPDATA%/Strata/profiles`（`APPDATA` 未設定時はユーザープロファイル下）、その他では `${XDG_CONFIG_HOME:-~/.config}/strata/profiles` です。profile 本体、履歴、lock 用ファイルをローカルで扱います。ファイル操作は一時ファイル、置換、lock を用います。

この操作はエンジン起動、ネットワーク通信、GPU 操作を行いません。実行中の server はそのままです。後で profile を使って起動する際は、明示的な CLI 設定が保存済み override より優先し、保存済み override は run config の値より優先します。

## 出力とエラー

- `--output` は `human` または `json` を受け付け、既定は `human` です。one-shot parser に追加される `--json` は JSON 出力の別表記、`--quiet` は人間向け成功出力を抑制する指定です。JSON 出力は quiet の対象外です。
- profile が存在しない、profile 名や `--to` が不正、履歴が見つからない・不正・内容不一致、履歴の profile 検証に失敗した場合は復元されません。変更競合も保存時に拒否されます。
- `ProfileError` は通常終了コード2、profile/履歴の不在や読み込み・検証失敗はコード5、変更競合はコード6です。OS のファイル操作エラーも CLI 共通処理で通常コード6として報告されます。
- 人間向けエラーは標準エラーに `strata: ...` と表示されます。`--json` または `--output json` の場合は `{schema_version, ok: false, error: {code, message}}` 形式を標準出力に出します。

## 注意点

- revision は完全な16桁を指定します。履歴一覧は [`strata profile history`](../history/README.md) で確認できます。
- rollback は現在の profile も履歴へ保存するため、復元後も直前の状態を履歴から選べます。
- 成功メッセージに明記されるとおり、稼働中の server は変わりません。設定を稼働中 server に反映するには別途 server のライフサイクル操作が必要です。
- source checkout の実装を調査した文書です。Release 配布物や異なる OS 上での実地動作は確認していません。

## 関連文書

- [`strata profile` 概要](../README.md)
- [`strata profile history` 概要](../history/README.md)
- [`--to` 文書](--to.md)
- [CLI 索引](../../../README.md)

## 根拠

- Strata `strata_cli/cli.py:102-105,508-515` — rollback parser 定義と `--json` / `--quiet` の追加。
- Strata `strata_cli/cli.py:1011-1014,527-542` — rollback 呼び出し、成功時の人間向け文言・JSON payload。
- Strata `strata_cli/cli.py:2166-2183,2232-2247` — 例外の終了コード・出力形式と quiet の処理。
- Strata `strata_control/profiles.py:25,38-45` — profile 名の形式と保存先。
- Strata `strata_control/profiles.py:150-166` — 現在 profile の読み込み・revision 算出・検証。
- Strata `strata_control/profiles.py:213-234,266-295` — lock 下の更新、変更競合検査、履歴退避、原子的保存。
- Strata `strata_control/profiles.py:326-346` — `--to` 相当の revision 検査、履歴ファイル検証、復元。
- Strata `docs/TERMINAL.md:156` — 保存先、revision 管理、起動中 profile への非反映と設定優先順位の利用者向け説明。

調査対象は上記 commit の checkout に含まれるソースと文書です。指定 revision の状態は `git status --short --branch` で `## main...origin/main`（未コミット変更なし）と確認しました。
