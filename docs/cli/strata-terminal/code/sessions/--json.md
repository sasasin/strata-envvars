# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata code sessions list` |
| オプション | `--json` |
| 別名 | `--output json` |
| 値 | 値を取らない真偽フラグ |

## 役割

結果を機械可読な JSON で出力する指定です。`strata code sessions` の `--json` は `--output json` の別名として登録されています。

## 使い方

```sh
strata code sessions list --json
```

## 値と既定値

`--json` 自体は値を取りません。省略時の出力形式は `--output` の既定値 `human` です。`--output` が受け付ける値は `human` と `json` です。`--json` が指定されると、`--output` の指定順にかかわらず実行前に出力形式が `json` に設定されます（`strata_cli/cli.py:505-507, 512-515, 2232-2235`）。

## 実行時の動作

parser は `sessions` の位置引数 `action` に `list` のみを許し、`--json` を `store_true` のフラグとして登録します（`strata_cli/cli.py:505-507, 512-515`）。引数解析後、`--json` は `output` を `json` に変換します（`strata_cli/cli.py:2232-2235`）。

この revision では `strata code` の処理本体が利用不可を返すため、セッション一覧の成功応答は出力されません。`_run` は `code` コマンドに対し、shared Desktop harness が未インストールで coding sessions を利用できない旨をエラーコード 5 で返します。出力形式が `json` の場合、そのエラーは `schema_version: 1`、`ok: false`、`error.code`、`error.message` を含む JSON として標準出力に出ます（`strata_cli/cli.py:2162-2164, 527-532`）。

## 適用条件と副作用

このオプションは `code sessions` parser のスコープです。ファイル作成やセッションの変更は行わず、出力形式を切り替えます。`--quiet` と併用しても、JSON 出力時は `main` が `_run` を直接実行するため JSON エラーは抑制されません（`strata_cli/cli.py:514-515, 2236-2240`）。

## 出力とエラー

現行ソースではコマンドは成功せず、終了コード `5` となります。`--json` 使用時は上記のエラーオブジェクトが標準出力へ出力されます。`--json` を省略した場合は `strata: ...` 形式のエラーが標準エラーへ出力されます（`strata_cli/cli.py:2162-2164, 527-532`）。

## 根拠

- parser、action の選択肢、`--output` の既定値: `strata_cli/cli.py:505-507`
- one-shot parser 群への `--json` / `--quiet` 登録: `strata_cli/cli.py:508-515`
- `--json` から `output=json` への変換: `strata_cli/cli.py:2232-2235`
- `code` コマンドの未導入時エラーと出力形式判定: `strata_cli/cli.py:2162-2164`
- JSON / 人間向けエラー出力と終了コード: `strata_cli/cli.py:527-532`
- quiet 処理と JSON 時の直接実行: `strata_cli/cli.py:2236-2240`
- `strata code sessions list --json` が終了コード 5 と JSON error code 5 を返す既存 CLI テスト: `tests/terminal/test_profiles.py:106-108`

調査範囲は上記 commit の Terminal CLI ソースです。実行可能な同一 revision の CLI help や Release 配布物は別途確認していません。
