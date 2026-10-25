# `strata profile history`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile history` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/profiles.py` |

## 役割

指定した保存済み profile の現在 revision と、保存履歴に残っている以前の revision を一覧表示します。履歴を確認するコマンドであり、profile の変更・復元やサーバーの起動は行いません。過去 revision の復元は [`strata profile rollback`](../rollback/README.md) を使います。

## 使い方

```sh
# profile「local」の現在・過去 revision を人間向けに表示
strata profile history local

# 同じ一覧を JSON で取得
strata profile history local --json
```

`NAME` は必須です。profile 名は小文字英字で始まり、小文字英数字、`_`、`-` のみを使えます。`--output` は `human` または `json` を受け付け、省略時は `human` です。`--json` は `--output json` の別表記です。

## 実行時の動作

このコマンドは profile の履歴ディレクトリから `*.json` を調べ、ファイル名の拡張子を除いた部分が16桁の小文字16進 revision であり、通常ファイルかつシンボリックリンクでないものだけを候補にします。profile 本体を読み込んで現在 revision を得た後、現在 revision を `current: true` として先頭に置き、履歴候補から同じ revision を除いて `saved_at`（ファイルの更新時刻）の降順に並べます。従って JSON の過去項目には `revision` と `saved_at` が含まれます。履歴ファイルがない場合も、現在の profile が読み込めれば現在 revision の項目は返ります。

標準出力は通常、人間向けの各行 `REVISION  current` または `REVISION  saved` です。JSON モードでは `{schema_version, ok, profile, history}` を出力します。`--quiet` も parser で受理されますが、人間向け成功出力を抑制します（JSON 出力には適用されません）。

保存先は `STRATA_PROFILE_DIR` が設定されていればそのディレクトリ、未設定なら Windows では `%APPDATA%/Strata/profiles`（`APPDATA` がなければユーザープロファイル配下）、その他の環境では `${XDG_CONFIG_HOME:-~/.config}/strata/profiles` です。履歴はその下の `.history/NAME/` にあります。

## 注意点

- このコマンドの位置引数は任意のパスではなく profile 名です。profile 名の形式不正、profile 本体がない・読み込めない・検証に失敗する場合は一覧を返せません。
- 履歴ファイルは revision 名とファイル種別で候補選別されますが、この一覧処理では各履歴ファイルの内容と revision の一致までは検証しません。復元可否の検証は rollback 側で行われます。
- profile 履歴は、profile 保存処理が更新前の内容を退避したものです。初回作成以前や保存時に履歴ファイルが作られなかった revision は一覧に現れません。
- ソース上、このコマンド自身は profile を更新せず、エンジンやサーバーを起動しません。CLI プロセス共通のユーザー所有権調整処理は実行されます。

## 関連文書

- [`strata profile` 概要](../README.md)
- [`strata profile rollback`](../rollback/README.md)
- [`--help`](--help.md)、[`--output`](--output.md)、[`--json`](--json.md)、[`--quiet`](--quiet.md)
- [CLI 索引](../../../README.md)

## 根拠

- Strata `strata_cli/cli.py:99-101,508-515` — サブコマンド、位置引数、`--output` と共通 `--json` / `--quiet` の parser 定義。
- Strata `strata_cli/cli.py:958-959,1006-1010` — profile history の呼び出しと人間向け一覧の構成。
- Strata `strata_cli/cli.py:535-542,2166-2183,2217-2244` — 成功出力、例外のエラー出力・終了コード、共通 `--quiet` 処理。
- Strata `strata_control/profiles.py:25,30-35,38-55` — profile 名の規則、保存領域、profile path。
- Strata `strata_control/profiles.py:312-323` — 履歴候補の選別、現在 revision の読込、並び順。
- Strata `strata_control/profiles.py:266-295` — profile 保存時に旧 revision を `.history/NAME/` へ退避する処理。
- Strata `strata_control/profiles.py:326-345` — rollback 時の revision 内容検証と復元処理。

調査は指定 revision の checkout にあるソースに限定しました。異なる OS の実行環境や Release 配布物での実地動作は確認していません。
