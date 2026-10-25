# `strata tune list`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune list` |
| 実装 | `strata_cli/cli.py` |
| 対象 | 保存された tuning job の一覧 |

## 役割

`strata tune run` が記録した job の ID、状態、backend、objective を一覧表示します。job の保存先を読み取る確認用コマンドで、job の実行や設定の変更はしません。サブコマンドと `--state-dir` / `--output` は `strata_cli/cli.py:395-397,482-484` で登録されています。

これは名前の似た `strata presets list` とは別の一覧です。`strata tune list` は tuning job の状態記録を対象とし、preset の列挙には `strata presets list` を使います（`strata_cli/cli.py:482-484`、`strata_cli/tune_commands.py:49-59`）。

## 代表的な使い方

```sh
# 既定の保存先にある job を人向け表示で確認
strata tune list

# JSON 形式で取得
strata tune list --output json

# 指定した state directory を一覧
strata tune list --state-dir ./tuning-state
```

`--state-dir` と `--output` はこのサブコマンドの parser に定義されています。既定の出力形式は `human` で、`json` も選べます（`strata_cli/cli.py:482-484`）。

## 主な動作

- 一覧のルートは `--state-dir`、環境変数 `STRATA_TUNE_DIR`、ユーザー state directory 内の `tuning/` の順で決まります。既定の state base は POSIX で `${XDG_STATE_HOME:-~/.local/state}/strata`、Windows で `${LOCALAPPDATA:-~/AppData/Local}/Strata` です（`strata_cli/cli.py:1643-1650`、`strata_control/paths.py:13-21`）。
- ルートがディレクトリなら、その直下を名前順に走査し、各項目の `job.json` を読みます。出力に含めるのは JSON の `id`、`state`、`plan.backend`、`plan.objective` です。JSON 読み込み時に `OSError` または値エラーとなるファイルはスキップされます。ルートが存在しない、またはディレクトリでなければ空の一覧になります（`strata_cli/cli.py:1655-1668`）。
- 人向け出力では job ごとに ID の先頭12文字、状態、backend、objective を表示します。job がなければ `no tuning jobs recorded` と表示します。JSON 出力では `schema_version: 1`、`ok: true`、`jobs` を含むオブジェクトを標準出力に出します（`strata_cli/cli.py:1669-1676,535-538`）。
- コマンド自身は state directory や job ファイルを作成・変更・削除しません。job の永続化は tuner が job directory 内の `job.json` に行います（`strata_control/tuning.py:317-341,359-375`）。

## 注意点

- この一覧は再帰検索せず、指定したルートの直下にある job directory のみを対象にします（`strata_cli/cli.py:1655-1668`）。
- JSON として読めても、内容の schema validation は行いません。トップレベル値や `plan` の形式が想定外の場合、フィールド参照で例外となる可能性があります（`strata_cli/cli.py:1661-1668`）。
- 有効な `--output` 値は `human` と `json` です。未知の値や値の欠落は argparse の引数エラーになります（`strata_cli/cli.py:482-484`）。

## 関連文書

- [`strata tune` 概要](../README.md)
- [`strata tune run` 概要](../run/README.md)
- [`strata tune status` 概要](../status/README.md)
- [`strata presets list`（CLI 索引）](../../../README.md)
- [CLI オプション索引](../../../README.md)

## 根拠

- `strata_cli/cli.py:395-397,482-486,1802-1803` — `tune` 階層、`list` parser、オプション、job 作成時の保存処理。
- `strata_cli/cli.py:1641-1650,1655-1676` — state root の選択、job 走査、フィールド抽出と表示。
- `strata_cli/cli.py:535-538` — JSON 成功応答の形式。
- `strata_control/paths.py:13-21` — OS ごとのユーザー state base。
- `strata_control/tuning.py:317-341,359-375` — job directory と `job.json` の保存。
- `strata_cli/tune_commands.py:49-59` — `strata presets list` の parser。tuning job list とは別コマンド。

## 調査範囲

記載した挙動は上記 commit の Terminal CLI parser と実行経路、および state path / job 保存実装で確認しました。同一 revision の CLI `--help` や Release artifact は実行・照合していません。
