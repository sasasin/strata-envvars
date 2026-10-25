# `strata tune rollback --state-dir`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune rollback` |
| オプション | `--state-dir` |
| 別名 | なし |
| 値 | ディレクトリのパス（文字列）。省略可能 |

## 役割

rollback が apply 記録と適用前の設定バックアップを探す状態ディレクトリを指定します。ここには `applications/<application-id>/application.json` と `before.json` が置かれます。適用時に使った状態ディレクトリを指定してください。

## 使い方

```sh
strata tune rollback <application-id> --state-dir /path/to/tuning-state
```

`<application-id>` は `strata tune apply` が成功時に返す ID です。指定ディレクトリが apply 時の保存先と異なると、対応する記録を見つけられません。

## 値と既定値

- parser は値を必須とする文字列引数として定義し、形式・存在・ディレクトリであることの事前検証はしません。引数値の相対パスはプロセスの作業ディレクトリ基準で解釈されます。
- 省略時は `STRATA_TUNE_DIR` の値を使います。環境変数も未設定または空なら、既定のユーザー状態ディレクトリ配下の `tuning/` を使います。
- 明示値が空文字列の場合は truthy 判定を通らないため、省略時と同じ環境変数・既定値への解決になります。

## 実行時の動作

CLI は解決した状態ディレクトリを `tune_apply.rollback()` に渡します。そこで `applications/<application-id>/application.json` を読み、記録された設定ファイルと `before.json` を使って復元します。記録の `after_sha256` と現在の設定ファイルの SHA-256 が一致した場合だけ、`before.json` のバイト列で設定ファイルを原子的に置き換え、記録に rollback 済み時刻を保存します。

`--state-dir` は復元対象の設定ファイルの場所を直接指定するものではありません。復元先は application record 内の `config_path` です。human 出力では復元先と application ID を表示し、`--output json` では成功結果を JSON で返します。

## 適用条件と副作用

- ID に対応する application 記録、適用前バックアップ、復元先設定ファイルが存在する必要があります。
- 復元先設定が apply 後に変更されていると、新しい変更を失わないよう rollback を拒否し、設定ファイルには書き込みません。
- rollback 済みの記録は再実行できません。
- 記録が見つからない場合でも、状態ディレクトリ内の `applications/` は探索時に作成されます。成功時は設定ファイルを復元し、application record を更新します。
- 値自体の allowlist や相対パスの禁止はありません。指定先には既存の正しい記録があり、意図した Strata 状態領域を指すことを確認してください。

## 出力とエラー

- 成功時は終了コード `0`。通常出力は `restored <設定ファイル>` と rollback 済み application ID、JSON 出力は成功 payload です。
- application 記録がない場合は `no application record at ...`（code `404`）、すでに rollback 済みの場合はその旨、バックアップがない場合または設定ファイルがない場合は理由を返します。
- 設定ファイルが apply 後に変化している場合は「新しい変更を破棄するため復元できない」旨と code `409` を返します。
- rollback 固有の `ApplyError` は `--output json` なら `ok: false` と error code/message の JSON、human 出力なら `strata: ...` を stderr に出します。ファイル I/O の `OSError` は共通エラー処理を通り code `6` で報告されます。

## 根拠

- `strata_cli/cli.py:472-475` — `rollback` parser と `--state-dir` の定義（文字列、既定値 `None`）。
- `strata_cli/cli.py:1643-1650` — 明示値、`STRATA_TUNE_DIR`、既定状態領域の解決順序。
- `strata_control/paths.py:13-21` — POSIX の `$XDG_STATE_HOME`（既定 `~/.local/state`）と Windows の `%LOCALAPPDATA%` を使う状態基点。
- `strata_cli/cli.py:1712-1713,1953-1963` — 解決した状態ルートを rollback に渡し、成功・`ApplyError` を出力する処理。
- `strata_control/tune_apply.py:300-303,373-401` — application 記録領域の作成、記録とバックアップの検索、再実行・欠落・競合の拒否、ハッシュ照合、復元と記録更新。
- `strata_cli/cli.py:527-532` — human エラーを stderr、machine エラーを JSON に出し、指定コードを返す共通処理。
