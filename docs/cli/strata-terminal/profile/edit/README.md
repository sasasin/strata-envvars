# `strata profile edit`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile edit` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/profiles.py` |
| 位置引数 | `NAME`（既存 profile 名） |
| 出力関連 option | [`--output`](--output.md)、[`--json`](--json.md)、[`--quiet`](--quiet.md)、[`--help`](--help.md) |

## 役割

保存済みの serving profile を JSON エディターで直接編集します。profile の一時コピーを `VISUAL` または `EDITOR` で開き、閉じた後に JSON と profile の内容、参照先 run config を検証してから保存します。profile は setup が作る run config と分離された serving overrides です（`strata_control/profiles.py:1-5`）。

## 使い方

`office` という profile がすでに保存されていて、`nano` が利用可能な POSIX 環境での例です。

```sh
EDITOR=nano strata profile edit office
```

JSON を機械処理する場合:

```sh
EDITOR=nano strata profile edit office --output json
```

`VISUAL` が設定されていれば `EDITOR` より優先されます。profile の作成方法は [`strata profile create`](../create/README.md)、一覧・内容確認は [`strata profile list`](../list/README.md) と [`strata profile show`](../show/README.md) を参照してください。

## 実行モード

このコマンドは一回限りの profile 編集です。名前を指定すると既存 profile を読み込み、エディターを起動します。成功時は既定の human 出力で保存した revision を表示し、`--output json` では更新後の profile、前後の revision、変更点を JSON で返します（`strata_cli/cli.py:958-968,998-1005`）。サブコマンド parser は `--output human|json` を受け付け、既定値は `human` です。`--json` は one-shot parser に追加される `--output json` の alias です（`strata_cli/cli.py:96-98,508-515`）。

## 主な動作と副作用

- profile 名で現在の保存内容と revision を読み込みます。保存ファイルがない場合や profile が不正な場合は編集を開始できません（`strata_control/profiles.py:48-55,120-132,150-166`）。
- `VISUAL`、なければ `EDITOR` の値を shell 文字列として分割し、そのコマンドに一時 JSON ファイルのパスを引数として渡して起動します。editor が未設定または空ならエラーです（`strata_control/profiles.py:349-362`）。
- 編集後は JSON として読み込み、schema version が 1 であること、profile の ID が指定名と一致すること、`source_config` が絶対パスであること、`overrides` が対応する型・範囲に合うことを検証します。さらに参照 run config が読み取れ、`args` が文字列配列、`exe` と `tokenizer` が空でない文字列であることも必要です（`strata_control/profiles.py:98-132,135-147,266-270`）。
- 変更があれば、保存前の profile を `.history/NAME/REVISION.json` に記録し、現在の profile を atomic replacement で更新します。同一内容なら既存 revision を返し、履歴・現在ファイルとも変更しません。revision が編集中に変化していれば保存を拒否します（`strata_control/profiles.py:266-295`）。
- この処理自体は推論 server を起動・再起動せず、ネットワーク接続もしません（`strata_control/profiles.py:1-5`）。保存した設定は後続の profile 利用時に適用されます。

## 注意点と失敗経路

- 編集には既存 profile と `VISUAL` または `EDITOR` の設定が必要です。名前は小文字英字で始め、以降は小文字英数字、`_`、`-` を使う 1〜64 文字です（`strata_control/profiles.py:25,48-50,349-356`）。
- editor が非 0 で終了した場合、編集 JSON が不正な場合、または検証・revision 競合で保存できない場合、一時 draft は削除されず、エラーにそのパスが含まれます。成功時は一時ファイルを削除します（`strata_control/profiles.py:362-379`）。
- profile 未保存・内容不正は通常終了コード 5、profile 変更の競合や editor の非 0 終了は 6、その他の入力・validation エラーは既定で 2 です。JSON 出力を指定した場合も失敗は `ok: false` と error code/message の JSON になります（`strata_control/profiles.py:30-35,150-166,363-375`、`strata_cli/cli.py:2166-2183`）。
- `--output` の選択肢は `human` と `json` です。省略時は human 出力です。各 output option の詳細は [コマンド索引](../../../README.md) の `strata-terminal` 節にある個別文書を参照してください。

## 関連文書

- [`strata profile` コマンド概要](../README.md)
- [`strata profile set`](../set/README.md) — 型付き値で serving overrides を設定
- [`strata profile validate`](../validate/README.md) — profile と参照 run config を検証
- [CLI 文書索引](../../../README.md)

## 根拠

- Strata `strata_cli/cli.py:69-105` — profile command hierarchy、edit parser、出力 parser。
- Strata `strata_cli/cli.py:508-515,958-1005` — `--json` の追加と profile edit の実行・成功出力。
- Strata `strata_cli/cli.py:2166-2183` — 例外から stderr / JSON error、終了コードへの変換。
- Strata `strata_control/profiles.py:1-5,25-50,98-166` — profile の役割、保存場所、名前・内容の検証と読み込み。
- Strata `strata_control/profiles.py:266-295,349-379` — revision 競合確認、履歴・atomic 保存、一時 editor draft と失敗時の保持。
- 利用者向け CLI help はこの調査では別途実行していません。記載内容は同一 revision の parser と実装に基づきます。
