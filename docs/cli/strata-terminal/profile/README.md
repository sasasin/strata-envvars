# `strata profile`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/profiles.py` |

## 役割

`strata profile` は、setup が作成した run-config JSON を変更せずに、名前付き serving profile の作成、参照、検証、編集、履歴管理を行います。profile は run config の絶対パスと serving 用 override を持つ別ファイルです。コマンド自体は推論エンジンやサーバーを起動せず、ネットワークサービスにも接続しません。profile を保存しても、稼働中サーバーの設定変更や再起動は行われません。保存済み値は、後で `serve` など profile を使うコマンドを実行するときに参照されます。読み込み時、昇格実行で所有者が変わった profile ファイルは、CLI が一度権限修復する場合があります。

## 基本的な使い方

```sh
# インストール済み run config から profile を作成
strata profile create local --from-config /path/to/run-config.json

# 保存済み profile の一覧と現在の設定を確認
strata profile list
strata profile show local --effective

# 変更案を表示してから保存
strata profile set local parallel=8 --plan
strata profile set local parallel=8

# profile を検証し、以前の revision を確認
strata profile validate local
strata profile history local
```

上記のファイルパスは例です。`create` と `use-config` は読み込み可能な run-config JSON を必要とします。設定値を直接編集する場合は `set`、`VISUAL` または `EDITOR` で一時 JSON を開く場合は `edit` を使います。

## サブコマンド

`profile` の下には必須のサブコマンドがあり、サブコマンドを省略した呼び出しは成立しません。

| サブコマンド | 用途 | 文書 |
| --- | --- | --- |
| `create NAME --from-config CONFIG.json` | run config を参照する新しい profile を作る | [`create`](create/README.md) |
| `list` | 保存済み profile と revision、読み込みエラーを一覧する | [`list`](list/README.md) |
| `show NAME [--effective]` | profile を表示し、`--effective` では解決後の設定も示す | [`show`](show/README.md) |
| `validate NAME` | profile と参照先 run config を使った起動設定を検査する | [`validate`](validate/README.md) |
| `set NAME KEY=VALUE...` | 型付き serving override を追加・更新する | [`set`](set/README.md) |
| `use-config NAME --from-config CONFIG.json` | profile の参照先 run config を切り替える | [`use-config`](use-config/README.md) |
| `edit NAME` | 一時 JSON をエディターで編集し、検証後に保存する | [`edit`](edit/README.md) |
| `history NAME` | 現在と保存済み revision を表示する | [`history`](history/README.md) |
| `rollback NAME --to REVISION` | 過去 revision の内容を現在値として復元する | [`rollback`](rollback/README.md) |

各サブコマンドの `--help` は [`strata profile --help`](--help.md) および各サブコマンド文書から参照できます。

## profile の保存と適用

profile ファイルは Windows では `%APPDATA%/Strata/profiles`、それ以外では `${XDG_CONFIG_HOME:-~/.config}/strata/profiles` に置かれます。環境変数 `STRATA_PROFILE_DIR` が設定されていれば、そのパスが使われます。名前は小文字英字で始まり、小文字英数字・`_`・`-` のみ、最大64文字です。

override として保存できる値は `host`、`port`、`parallel`、`batch_groups`、`max_queue`、`queue_timeout`、`offline`、`batch_telemetry` です。保存済み profile を適用する際は、明示したコマンド引数、profile override、run config、環境値または既定値の順で値が解決されます。`queue_timeout` は `max_queue` と併用する必要があるなど、起動設定としての整合性検査は `show --effective`、`validate`、または実際の serving 起動経路で行われます。

保存時には現在の内容を revision 付き履歴に退避してから一時ファイル経由で更新します。編集途中に別プロセスが profile を更新した場合は revision の不一致として失敗し、古い内容で上書きしません。`set` と `use-config` の `--plan` は変更案を表示して保存を行わず、`rollback` は指定 revision の内容を新しい現在値として保存します。

## 実行モードと出力

- 通常の出力は人間向けです。one-shot の profile サブコマンドでは `--output human|json` が使え、`--json` は JSON 出力の別表記です。`--quiet` は人間向けの成功情報を抑えますが、JSON 出力には適用されません。
- `set --plan` と `use-config --plan` は保存せず、変更内容を表示します。`show --effective` と `validate` は profile と run config から有効な起動設定を解決しますが、エンジンは起動しません。
- `edit` は profile の一時 JSON を作って外部エディターを起動します。エディターが失敗した場合や編集内容の検証・保存が失敗した場合、一時ファイルを draft として残し、その場所をエラーに含めます。
- `list` は個別 profile の読み込みエラーも一覧項目に含めます。見つからない profile、壊れた JSON、無効な値、競合 revision、利用できない run config などは失敗になります。

このコマンドの `--help` とオプション一覧は [`docs/cli/README.md`](../../README.md) の `strata-terminal` 節にあります。profile の保存先や適用時の優先順位については [Terminal CLI の利用者向け説明](../../../TERMINAL.md) も参照してください。

## 根拠

- Strata `strata_cli/cli.py:69-105` — `profile` と8つの必須サブコマンド、引数、`--output` の定義。
- Strata `strata_cli/cli.py:508-515` — profile one-shot parser 群に `--json` と `--quiet` を追加。
- Strata `strata_cli/cli.py:958-1020` — profile 操作の分岐、plan・effective・JSON/人間向け出力。
- Strata `strata_cli/cli.py:527-542,2166-2183,2217-2248` — 成功・エラー出力、終了コードの返却、quiet の適用。
- Strata `strata_cli/cli.py:745-779` — 明示引数・profile・run config 等の優先順位と有効設定の検査。
- Strata `strata_control/profiles.py:1-5,25-45,48-63` — 保存領域、名前規則、profile revision とモジュールの副作用境界。
- Strata `strata_control/profiles.py:66-147` — override の型・範囲、profile と run config の検証。
- Strata `strata_control/profiles.py:150-182,236-249` — 読み込み、一覧、作成時の検査と既存 profile の拒否。
- Strata `strata_control/profiles.py:266-295,304-346` — revision 競合確認、履歴保存、原子的更新、rollback。
- Strata `strata_control/profiles.py:349-388` — エディター実行、失敗時の draft 保持、profile 名と JSON パスの解決。
- Strata `docs/TERMINAL.md:156` — 利用者向けの保存先、優先順位、稼働中サーバーへの影響の説明。
