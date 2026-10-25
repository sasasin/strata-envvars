# `strata ops history`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops history` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/recipes.py` |

## 役割

指定した profile に保存されている operator recipe の現在 revision と、過去に保存された revision を一覧表示します。recipe の内容を確認・復元する操作ではなく、復元には [`strata ops rollback`](../rollback/README.md) を使います。ここで扱う recipe revision の履歴は、実行記録を列挙する `strata ops runs` の operation journal とは別です。

## 基本的な使い方

```sh
# recipe restart の現在版と保存済み過去版を表示
strata ops history restart --profile four-gpu

# 同じ一覧を JSON で取得
strata ops history restart --profile four-gpu --output json
```

recipe 名と `--profile` は必須です。recipe 名・profile 名は小文字英字で始まり、小文字英字、数字、`_`、`-` を使えます。表示形式は `--output human|json`（既定値 `human`）または alias の `--json` で指定できます。`--quiet` は one-shot コマンド共通の抑制指定です。`--quiet` と JSON 出力を同時に使った場合、JSON 出力は維持されます。

## 主な動作

- 指定 recipe の現在ファイルを読み込み、その revision を一覧の先頭に `current: true` として返します。recipe が存在しない、profile が存在しない、recipe の形式が不正などの場合は一覧を返さず失敗します。
- recipe の `.history/<recipe>/` にある、16 桁の小文字16進 revision 名を持つ通常ファイルを過去版として収集します。シンボリックリンクは対象外です。現在 revision と重複する過去版は除外され、残りはファイルの更新時刻 `saved_at` の新しい順で返されます。
- revision のスナップショットは recipe の内容が変更されて保存される際に作られます。変更前の recipe bytes を `<revision>.json` に退避してから現行 recipe を atomic replacement するため、変更のない保存では新しい履歴項目は増えません。
- 保存先は profile directory 以下の `.ops/<profile>/<recipe>.json`、履歴スナップショットは `.ops/<profile>/.history/<recipe>/<revision>.json` です。profile directory は `STRATA_PROFILE_DIR` があればその値、なければ OS ごとの既定値（POSIX は `XDG_CONFIG_HOME` があればその値の下の `strata/profiles`、なければ `~/.config/strata/profiles`。Windows は `%APPDATA%/Strata/profiles`、`APPDATA` がなければ `~/AppData/Roaming/Strata/profiles`）です。
- このコマンドは recipe revision を一覧するだけで、recipe の実行や rollback、operation journal への追加は行いません。JSON 出力では `profile`、`recipe`、`history` が返り、過去版には `saved_at`（ファイル更新時刻）が含まれます。人間向け出力は各 revision と `current` / `saved` の区分を表示します。

## 注意点

- `ops history` は一覧のために現在の recipe を先に読み込みます。history directory がない場合も失敗にはせず、現在 revision だけを返します。
- profile・recipe の検証やファイル読み込みに失敗した場合、共通 CLI のエラー経路からエラーを表示して非ゼロ終了します。無効な引数や不足引数は argparse の usage/error と終了コード 2 になります。ファイル access error は共通エラーとして報告されます。
- POSIX では recipe directory、history directory、recipe file に owner-only の権限要件があります。履歴 directory が symlink、通常 directory でない、または必要な権限条件に反する場合は recipe history の読み取りが失敗します。
- 過去版の表示順は revision の値順ではなく、保存ファイルの更新時刻によります。ソースでは `saved_at` を mtime として扱うため、時刻の正確さや revision 間の因果関係を一覧だけから保証するものではありません。

## 関連文書

- [CLI 文書索引](../../../../README.md) — Terminal CLI のコマンド階層とオプション文書。
- [`strata ops rollback`](../rollback/README.md) — 保存済み revision の復元。
- [`strata ops runs`](../runs/README.md) — operation run journal の一覧。

## 根拠

- Strata `strata_cli/cli.py:255-267` — `ops` とその subcommand parser、必須の recipe 名・`--profile`、`--output` の定義。
- Strata `strata_cli/cli.py:508-515` — one-shot `ops` subcommand に追加される `--json` alias と `--quiet`。
- Strata `strata_cli/cli.py:1391-1394,1431-1435` — `history` 分岐、human/JSON 出力。
- Strata `strata_cli/cli.py:2160-2162,2166-2183,2223-2237,2241-2248` — ops dispatch、例外のエラー変換、JSON・quiet の共通処理。
- Strata `strata_control/recipes.py:32-35,38-65,71-86` — profile/recipe 名の検証、保存先、history directory の安全確認。
- Strata `strata_control/recipes.py:180-196,240-250` — recipe 読み込みと履歴一覧の組み立て、現在版の先頭表示、過去版の mtime 降順。
- Strata `strata_control/recipes.py:214-237` — 変更時に旧版を history directory へ保存してから現行 recipe を置換。
- Strata `strata_control/profiles.py:38-45,62-63` — profile directory の選択と revision の生成。
- Strata `docs/TERMINAL.md:96-122` — operator recipes、history/rollback の利用例と `ops runs` journal との区別。
