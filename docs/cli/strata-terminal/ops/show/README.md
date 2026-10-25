# `strata ops show`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops show` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/recipes.py`、`strata_control/profiles.py` |
| 必須引数 | `NAME`、`--profile PROFILE` |
| 出力形式 | `--output human|json`（既定値 `human`）、`--json` は `--output json` の別表記 |

## 役割

指定した保存 profile に属する operator recipe を読み込み、その recipe 本体と revision を表示します。recipe の作成・編集・実行は行いません。recipe をまだ初期化していない場合は [`strata ops init`](../init/README.md) を先に使います。

## 使い方

```sh
strata ops show restart --profile four-gpu
strata ops show restart --profile four-gpu --output json
```

`NAME` と `PROFILE` は小文字英字で始まり、小文字英字・数字・`_`・`-` で構成する ID です。`show` parser は recipe 名を位置引数に取り、`--profile` を必須にします。`--output` は `human` または `json` のみを受け付け、`--json` と `--quiet` もこの one-shot コマンドで有効です（`strata_cli/cli.py:255-267,508-515`）。

## 実行時の動作

CLI は `strata ops show` を `_ops` に振り分け、`recipes.load(profile, name)` で保存 recipe と revision を読み込み、`{"recipe": ..., "revision": ...}` を成功結果として返します（`strata_cli/cli.py:1391-1394,1416-1418,2160-2161`）。recipe の保存先は profile ディレクトリ下の `.ops/<profile>/<name>.json` です。profile ディレクトリは `STRATA_PROFILE_DIR` があればそこを使い、未設定時は Windows で `%APPDATA%/Strata/profiles`、POSIX で `$XDG_CONFIG_HOME/strata/profiles`（未設定なら `~/.config/strata/profiles`）です（`strata_control/recipes.py:38-64`、`strata_control/profiles.py:38-45`）。

既定の `--output human` では人向けの recipe 要約ではなく、recipe と revision を整形 JSON で stdout に出します。`--output json` または `--json` は `schema_version: 1` と `ok: true` を含む一行 JSON を出力します（`strata_cli/cli.py:527-542`）。`--quiet` は human 出力を抑制します。JSON 出力では quiet が無視され、JSON を出力します（`strata_cli/cli.py:2232-2247`）。

## 注意点と失敗経路

- `--profile` は必須です。recipe 名と profile ID は小文字英字・数字・`_`・`-` の制約を受けます。profile または recipe がない場合、recipe の JSON/schema が不正な場合、ファイルが通常ファイルでない場合、recipe が 64 KiB を超える場合は失敗します（`strata_cli/cli.py:255-267`、`strata_control/recipes.py:32-35,93-114,180-196`）。
- POSIX では `.ops` の profile 用ディレクトリは mode `0700`、recipe ファイルは mode `0600` を要求し、シンボリックリンクや不正なファイル種別も拒否します（`strata_control/recipes.py:38-59,180-188`）。Windows の ACL 条件はこのソース確認だけでは評価していません。
- `show` 自体は recipe を編集・実行・journal 記録しません。ただし recipe の読み込みに先立ち、保存 profile も検証のため読みます。profile 読み込みには `private_files.read_bytes_repairing` が使われ、管理者実行で権限が変わった profile を一度修復して書き戻す場合があります（`strata_control/recipes.py:38-40`、`strata_control/profiles.py:150-166`）。そのため、すべての環境でファイルシステムに対して完全な read-only とは限りません。
- 不正値や保存内容の問題は CLI のエラー出力・終了コードに変換されます。通常の `ValueError` 系は例外の `exit_code`（既定 `2`）、`OSError` は `6` で、JSON モードでは `{schema_version, ok:false, error}` を stdout に出します。recipe がない場合は `5` です（`strata_control/profiles.py:30-35`、`strata_control/recipes.py:185-195`、`strata_cli/cli.py:527-532,2166-2188`）。

## 関連文書

- [`strata ops` の概要](../README.md) — コマンド群の役割。
- [`strata ops init`](../init/README.md)、[`list`](../list/README.md)、[`plan`](../plan/README.md)、[`run`](../run/README.md) — recipe の初期化・一覧・preview・実行。
- [CLI 索引](../../../README.md) — `show` の option scope とコマンド階層。

## 根拠

- `strata_cli/cli.py:255-267,508-515` — `ops show` parser、必須 profile、共通出力 option と alias。
- `strata_cli/cli.py:1391-1394,1416-1418,2160-2161` — recipe 読み込み、返却 payload、コマンド dispatch。
- `strata_control/recipes.py:32-64,93-114,180-196` — ID・recipe schema・保存場所・ファイル検査。
- `strata_control/profiles.py:30-45,150-166` — profile directory、profile 読み込みと権限修復。
- `strata_cli/cli.py:527-542,2166-2188,2232-2247` — 成功・失敗出力、終了コード、`--json` と `--quiet` の扱い。
- `docs/cli/README.md:507-515` — `strata ops show` の概要ページ・option link と scope。
- `docs/TERMINAL.md:96-122` — operator recipe の利用例と機能説明。
