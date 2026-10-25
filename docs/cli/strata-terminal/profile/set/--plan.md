# `--plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile set` |
| オプション | `--plan` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時 `false`、指定時 `true` |

## 役割

指定した serving profile の override 変更案を表示し、profile JSON を保存せずに終了します。位置引数 `assignments` は1件以上必須で、`KEY=VALUE` の形式です（`strata_cli/cli.py:84-88`）。

## 使い方

```sh
strata profile set office parallel=8 batch_groups=auto --plan
```

`office` は既存の profile 名です。`--plan` は `--output human`（既定）または `--output json` と併用できます。

## 値と既定値

- `--plan` は `action="store_true"` です。値は不要で、既定値は `false` です（`strata_cli/cli.py:84-88`）。
- `assignments` は1件以上必要です。使えるキーは `host`、`port`、`parallel`、`batch_groups`、`max_queue`、`queue_timeout`、`offline`、`batch_telemetry` です（`strata_control/profiles.py:25-27,66-95`）。
- `host` は空でなく空白を含まない文字列、`port` は整数 `0..65535`、`parallel` は整数 `1..1024`、`max_queue` は整数 `0..4096` です。
- `batch_groups` は `auto` または整数 `1..1024`、`queue_timeout` は有限の秒数 `0.1..600`、`offline` と `batch_telemetry` は小文字の `true` / `false` を指定します。数値の形式変換と範囲検証は `parse_assignment` / `validate_overrides` が行います（`strata_control/profiles.py:66-117`）。
- `=` のない指定、未対応キー、不正な数値・boolean、範囲外の値は拒否されます。複数の `KEY=VALUE` を渡して同じキーを重ねた場合、辞書化の結果は最後の値です（`strata_control/profiles.py:66-95,304-309`）。
- 指定されていない既存 override はそのまま案に残ります。値を空にして override を削除する構文はありません（`strata_control/profiles.py:304-309`）。

## 実行時の動作

処理は既存 profile を読み込み、assignment を変換・検証して、現在の `overrides` に指定キーを重ねた候補を作ります。`--plan` の場合は元の override と候補を比較し、差分 `changes` と `would_save` を返して、通常の保存処理へ進みません。差分のない指定なら `changes` は空で `would_save` は `false` です（`strata_cli/cli.py:986-997`、`strata_control/profiles.py:304-309`）。

通常の人向け出力（`--output` 省略時を含む）は整形済み JSON の plan payload です。`--output json` または共通 alias `--json` は `schema_version: 1` と `ok: true` を含む機械向け JSON envelope を出します。`--json` は one-shot parser 群へ後から追加され、`--quiet` も受理されます（`strata_cli/cli.py:508-515,535-542,2232-2247`）。`--quiet` 単独では成功時の stdout が抑制されます。`--json` / `--output json` と併用すると JSON 出力経路が quiet 抑制より優先します（同 `:2232-2247`）。

この preview は変更案の確認だけを行い、推論 server を起動・再構成しません。保存後の override は profile を使う起動計画で、コマンドライン指定、保存済み profile、run config の順に優先されます。`STRATA_BATCH_TELEMETRY` は `batch_telemetry` に限り、run config の値がない場合に既定値より先に参照されます。ただし `--plan` 自体はその起動計画を作らず、set 対象の差分を表示します（`strata_cli/cli.py:745-779,986-997`）。

## 適用条件と副作用

- 指定した profile が読み込め、全 assignment が検証を通る場合に plan が返ります。profile が未保存・破損している場合や値が不正な場合は失敗します（`strata_control/profiles.py:98-117,150-166,304-309`）。
- profile の保存、履歴作成、一時ファイルへの書き込みは `--plan` 経路では呼ばれません（`strata_cli/cli.py:986-997`; 保存処理は `strata_control/profiles.py:266-295`）。ただし読み込み時に `private_files.read_bytes_repairing` が呼ばれるため、権限等の修復が必要な profile では読取に伴う属性修復が起こり得ます（`strata_control/profiles.py:150-166`）。
- `queue_timeout` は `max_queue` が設定されていない場合に起動時の有効設定検証で拒否されます。また `batch_groups` は run config の `args` に `--batch-groups` がすでにある場合、`parallel` は該当する run config 引数との組み合わせによって拒否されます。この `profile set --plan` は assignment/profile 自体を検証しますが、この起動時競合検査は実行しません（`strata_cli/cli.py:745-779`）。そのため plan 表示だけで、後続の起動に適用可能と確定するものではありません。

## 出力とエラー

- 成功時は終了コード `0` です。既定の人向け形式では `{profile, revision, changes, would_save}`、JSON 形式ではそれらを `plan` に格納した成功 envelope を stdout に出します（`strata_cli/cli.py:535-542,986-992`）。
- `ProfileError` などの値エラーは、通常は `strata: <message>` を stderr に出して終了コード `2` です。JSON モードでは JSON error envelope を stdout に出します。profile の未保存・読取不能など `ProfileError` が明示するケースは終了コード `5`、未処理のファイル操作 `OSError` は CLI 共通処理でコード `6` になります（`strata_control/profiles.py:30-35,150-166`; `strata_cli/cli.py:527-532,2166-2188`）。
- `name`、1件以上の `assignments` の不足や parser が認識しない引数は、処理本体に入る前に argparse が拒否します（`strata_cli/cli.py:84-88,2223-2236`）。

## 根拠

- コマンド parser と `--plan` のスコープ: `strata_cli/cli.py:84-88`
- one-shot parser への `--json` / `--quiet` 追加、出力 helper、quiet 処理: `strata_cli/cli.py:508-515,527-542,2232-2247`
- `profile set` の差分計算、plan 分岐、保存分岐: `strata_cli/cli.py:986-997`
- assignment のキー、型変換、値検証、候補作成: `strata_control/profiles.py:25-27,66-117,304-309`
- profile load の読取・属性修復経路と保存処理: `strata_control/profiles.py:150-166,266-295`
- override の優先順位、起動時の組み合わせ検証: `strata_cli/cli.py:745-779`

CLI help の実行、build、テストは行わず、この revision の parser 定義と使用箇所を確認しました。調査時の Strata checkout は `main...origin/main` で未コミット変更表示はありませんでした。
