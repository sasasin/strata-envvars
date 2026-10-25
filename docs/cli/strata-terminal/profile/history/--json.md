# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile history` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると JSON 出力を選ぶ |

## 役割

プロフィールのリビジョン履歴を、機械処理しやすい JSON で標準出力へ出します。履歴の表示内容は `--output json` と同じです。

## 使い方

```sh
strata profile history my-profile --json
```

`my-profile` は必須のプロフィール名です。

## 値と既定値

`--json` は `argparse` の `store_true` フラグで、引数の値を受け付けません。省略時はフラグが偽で、`--output` の既定値 `human` に従います。`--json` を指定すると、引数の順序にかかわらず `--output` が `json` に設定されるため、併記した `--output human` より JSON 指定が優先します。`--output` 自体は `human` または `json` のみ受け付けます。

## 実行時の動作

このフラグは出力形式だけを切り替えます。処理はプロフィール履歴を読み、成功時に compact JSON の1行を標準出力へ書きます。トップレベルには `schema_version: 1`、`ok: true`、要求した `profile` 名、`history` 配列が含まれます。配列の先頭は現在のリビジョン（`revision` と `current: true`）、続く項目は `.history/<name>/` にある保存済みリビジョン（`revision` とファイル更新時刻由来の `saved_at`）で、保存済み項目は更新時刻の降順です。同じリビジョンの重複項目は除かれます。

履歴処理ではプロフィール名を検証し、保存済みプロフィール本体も読み込みます。名前は小文字英字で始まり、`a-z`、数字、`_`、`-` のみからなる1〜64文字です。履歴ディレクトリでは16桁の小文字16進数名の通常ファイルだけを候補にし、シンボリックリンクは除外します。

このコマンドの履歴処理は読み取りです。履歴ファイルの新規作成・削除・変更は行いません。ただし CLI 全体では引数解析より前に `private_files.adopt_user_defaults()` が呼ばれます。またプロフィール読み取り中に権限エラーが起きた場合、共通処理が既知の Strata ディレクトリの権限を修復し、コマンドを一度再実行する経路があります。これらは `--json` 固有ではありません。

## 適用条件と副作用

`--json` は `profile_history` parser を含む one-shot コマンド群に共通追加され、このサブコマンドでも有効です。フラグ自体にファイル・ネットワーク・プロセスへの追加処理はありません。履歴の読み取りは既定のプロフィールディレクトリ（Windows は `%APPDATA%` 配下、その他は `$XDG_CONFIG_HOME` または `~/.config` 配下）を使い、`STRATA_PROFILE_DIR` があればその値が優先します。

## 出力とエラー

成功時は JSON を stdout に出して終了コード `0` を返します。無効なプロフィール名などの `ValueError` 系失敗は、JSON モードでは `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` 形式を stdout に出します。未保存プロフィールは `ProfileError` の終了コード `5`、形式不正な名前は既定コード `2` です。ファイル操作エラーはまず権限修復・再実行を試みる場合があります。再試行後も処理できない場合は JSON モードでエラー JSON を出し、一般の OS エラーはコード `6`、権限エラーが再度発生した場合はコード `5` になります。

`--json` に値を付けた場合や未知のオプションを渡した場合は、通常の argparse エラー経路となり、usage とエラーが stderr に出て終了コード `2` です。この経路は JSON 応答ではありません。

## 根拠

- `strata_cli/cli.py:99-101` — `history` parser、必須位置引数 `name`、`--output` の選択肢と既定値。
- `strata_cli/cli.py:508-515` — `profile_history` を含む one-shot parser 群へ、値を取らない `--json` を追加。
- `strata_cli/cli.py:2223-2235` — 引数解析後、`--json` を `--output json` に変換。
- `strata_cli/cli.py:958-960,1006-1010` — 出力モード選択と履歴取得後の応答構築。
- `strata_cli/cli.py:527-542,2166-2183` — 成功・失敗 JSON の形式と終了コード処理。
- `strata_cli/cli.py:2085-2105` — PermissionError 時の権限修復と一度だけの再実行。
- `strata_control/profiles.py:38-45,48-55` — プロフィールディレクトリと名前規則。
- `strata_control/profiles.py:150-166` — プロフィール本体の読み込み、未保存・読み込み失敗の扱い。
- `strata_control/profiles.py:312-323` — 履歴候補の条件、現在リビジョン追加、並び順。
- `strata_cli/cli.py:2217-2224` — parser 構築前に実行される共通初期処理。

調査範囲は上記 checkout のソースです。同一 revision の CLI `--help` は実行せず、Release 配布物との照合も行っていません。
