# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune rollback` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

rollback の結果を人向けテキストか機械処理向け JSON で表示します。復元対象や rollback の可否は変えません。

## 使い方

```sh
strata tune rollback 20261025T120000Z-0123456789ab --output json
```

`application_id` は rollback 対象の適用記録 ID です。rollback は、その記録に保存された apply 前の設定ファイルを復元します。

## 値と既定値

- `human` / `json` のみ受理されます。省略時は `human` です。短縮別名は定義されていません（`strata_cli/cli.py:472-475`）。
- 値は `argparse` の `choices` で制限されます。別の値を指定すると parser が usage とエラーを stderr に出し、終了コード 2 で終了します（`strata_cli/cli.py:472-475`, `strata_cli/cli.py:2217-2231`）。
- `--output` は rollback 処理の後に出力形式を選ぶだけです。rollback に伴うファイル復元・記録更新はどちらの形式でも同じです（`strata_cli/cli.py:1953-1963`）。

## 実行時の動作

### `human`

成功時、stdout に復元先と application ID の状態を2行で表示し、終了コード 0 を返します（`strata_cli/cli.py:1959-1963`）。

### `json`

成功時、stdout に `schema_version: 1`、`ok: true` と rollback 結果を含む1行の JSON を出し、終了コード 0 を返します。結果には `application` レコードと `restored`（復元先パス）が含まれます（`strata_cli/cli.py:1959-1960`, `strata_cli/cli.py:535-541`, `strata_control/tune_apply.py:397-401`）。

このコマンドが参照する適用記録の格納先は、`--state-dir` が指定されていればその値、なければ `STRATA_TUNE_DIR`、それもなければユーザー状態ディレクトリ配下の `tuning` です。`--output` はこの選択に影響しません（`strata_cli/cli.py:1643-1650`, `strata_cli/cli.py:1712-1713`）。`--state-dir` はこのコマンドの別オプションです（`strata_cli/cli.py:472-475`）。

## 適用条件と副作用

rollback の実処理は `strata_control.tune_apply.rollback` が行います。対応する `application.json` と退避済み `before.json` があり、対象設定ファイルが存在し、現在のファイル内容の SHA-256 が apply 時に記録した `after_sha256` と一致する場合に限り復元します。ファイルは退避内容で atomic replace され、適用記録には `rolled_back: true` と `rolled_back_at` が保存されます（`strata_control/tune_apply.py:373-401`）。

記録がない、既に rollback 済み、退避ファイルがない、対象設定がない場合は復元を拒否します。apply 後に設定ファイルが編集されていれば、その変更を消さないよう終了コード 409 相当で拒否し、設定ファイルには書き込みません（`strata_control/tune_apply.py:381-396`）。

既定の状態ディレクトリは OS ごとに異なり、Windows は `%LOCALAPPDATA%\Strata`（未設定ならユーザープロファイル下の `AppData\Local\Strata`）、POSIX は `$XDG_STATE_HOME/strata`（未設定なら `~/.local/state/strata`）です（`strata_control/paths.py:13-21`）。このコマンドではその下の `tuning` が使用されます（`strata_cli/cli.py:1643-1650`）。

## 出力とエラー

- `human` の処理エラーは stderr に `strata: <理由>` を出します。`json` では stdout に `schema_version: 1`、`ok: false`、`error.code` と `error.message` を含む JSON を出します（`strata_cli/cli.py:527-532`, `strata_cli/cli.py:1957-1958`）。
- 適用記録がない場合は `ApplyError` のコード 404、設定変更の競合は 409、それ以外の rollback 拒否は既定コード 6 です（`strata_control/tune_apply.py:35-40`, `strata_control/tune_apply.py:381-396`）。OS のファイル操作エラーも CLI の共通処理でコード 6 のエラー出力になります（`strata_cli/cli.py:2176-2183`）。
- 不正な JSON の適用記録は `JSONDecodeError`（`ValueError` の派生）として共通エラー処理に入り、終了コード 2 で報告されます（`strata_control/tune_apply.py:383`, `strata_cli/cli.py:2166-2173`）。

## 根拠

- parser 定義と値制約: `strata_cli/cli.py:472-475`
- `--state-dir` / `STRATA_TUNE_DIR` / 既定状態パスの選択、rollback 呼び出し: `strata_cli/cli.py:1643-1650`, `strata_cli/cli.py:1712-1713`
- 成功・失敗時の表示切り替え: `strata_cli/cli.py:1953-1963`
- JSON envelope と人向けエラー出力: `strata_cli/cli.py:527-541`
- rollback の検査、atomic restore、記録更新: `strata_control/tune_apply.py:373-401`
- 既定ユーザー状態ディレクトリ: `strata_control/paths.py:13-21`
- 共通例外処理: `strata_cli/cli.py:2166-2183`
