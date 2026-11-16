# `--config`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--config` |
| 別名 | `--profile` |
| 値 | `CONFIG.json` または保存済み serving profile 名。必須。 |

## 役割

起動対象の setup 生成 run config を指定します。保存済み serving profile 名を渡した場合は、その profile が参照する run config を使い、profile の serving overrides も適用します。run config は読み込み・検証され、エンジン実行引数やサーバー設定の基礎になります。設定ファイルを書き換えるオプションではありません。

## 使い方

```sh
# run config のパスからサーバーを起動
strata serve --config /path/to/strata-model.json

# 保存済み serving profile を使い、起動せず有効設定を確認
strata serve --profile local-gpu --plan --output json
```

## 値と既定値

- `strata serve` では `--config` / `--profile` のどちらかが必須で、値は `CONFIG.json` として受け取ります（`strata_cli/cli.py:45-47`）。
- `strata_control.profiles.resolve()` は、`.json` 拡張子、絶対パス、または `/`・`\` を含む値をパスとして扱い、それ以外を保存済み profile 名として解決します。パスは `expanduser()` と `resolve()` を通ります（`strata_control/profiles.py:385-390`）。従って、スラッシュのない名前は profile ID として解釈されます。
- パスの既定値はありません。指定された値は `_source()` から `profiles.read_run_config()` に渡されます（`strata_cli/cli.py:546-548`）。

## 実行時の動作

1. 直接パスならその run config を、profile 名なら保存 profile の `source_config` を選択し、run config を読み込みます（`strata_control/profiles.py:385-390`、`strata_cli/cli.py:546-548`）。
2. JSON は UTF-8 BOM 付きも含めて読み込まれます。Strata の版付きディレクトリを指す設定パスは解決処理に通され、`args` が文字列配列であること、および `exe` と `tokenizer` が空でない文字列であることを検証します（`strata_control/profiles.py:135-150`）。
3. 有効値はコマンドライン指定、保存 profile の override、run config、環境変数（`batch_telemetry` の場合）、組み込み既定値の順に選ばれます。たとえば profile 名を使うと、その profile の override が run config より優先されます（`strata_cli/cli.py:746-766`）。
4. 設定はサーバー起動引数とエンジン引数の計画に反映されます。`--plan` なら起動せず計画を出力し、通常は `serve.server.main()` に引数を渡して foreground サーバーを起動します（`strata_cli/cli.py:784-828`、`strata_cli/cli.py:917-957`）。

このオプションはパーサ上の別名 `--profile` と同じ `config` 値です。保存済み profile の意味は、値の形式によって決まり、ファイル名だけの裸の値（例: `local-gpu`）は profile 名として扱われます（`strata_cli/cli.py:45-47`、`strata_control/profiles.py:385-390`）。

## 適用条件と副作用

- 指定先は Strata の setup 形式の run config である必要があります。通常の起動ではその内容を `serve.server` に渡し、設定内の実行ファイル・引数・作業ディレクトリ等を使う実行経路に進みます（`strata_cli/cli.py:784-828`、`serve/server.py:9953-9956`）。
- `--engine mock` を指定してもこの run config の解決と検証は先に実行されます。`--engine` は parser の既定値が `strata` で、`strata` / `mock` のみを受理します（`strata_cli/cli.py:46-49`、`strata_cli/cli.py:917-944`）。
- `--plan` はサーバー起動を行いません。JSON 出力は `--plan` と組み合わせる必要があり、foreground 起動時の `jsonl` は `--plan` と併用できません（`strata_cli/cli.py:917-921`）。
- `--config` によって run config 自体を書き換える処理は確認できません。run config の値は読み込み、effective config もメモリ上で構成してエンジン引数を計算します（`strata_control/profiles.py:135-150`、`strata_cli/cli.py:813-821`）。

## 出力とエラー

- `.json` パス、絶対パス、スラッシュを含む値が存在しない・読めない場合、または JSON として不正な場合、`read_run_config()` は `cannot read run config (<例外型>)` の profile error を生成します。JSON 構造に `args`、`exe`、`tokenizer` が欠ける場合もエラーになります（`strata_control/profiles.py:135-150`）。
- パスに見えない値は profile 名として解釈されます。該当する profile が保存されていない場合は `profile '<name>' is not saved; use strata profile create` で失敗します（`strata_control/profiles.py:153-164`、`strata_control/profiles.py:385-390`）。
- 通常のエラーは `strata: <message>` を stderr に出力し、JSON/JSONL モードではエラー情報を JSON として出力します。ValueError 系の終了コードは例外の `exit_code` 属性（なければ 2）、ファイル I/O エラーは 6 です（`strata_cli/cli.py:526-534`、`strata_cli/cli.py:2179-2196`）。`jsonl` では起動前の失敗が `failed` イベントになります（`strata_cli/cli.py:831-837`、`strata_cli/cli.py:892-899`）。

## 根拠

- `strata_cli/cli.py:45-47` — `strata serve` の parser。`--profile` / `--config` の別名関係と必須指定。
- `strata_control/profiles.py:385-390` — パスと profile 名の判定・解決。
- `strata_cli/cli.py:546-548`、`strata_control/profiles.py:135-150` — run config の解決、文字コード、構造検証。
- `strata_cli/cli.py:746-781` — CLI、profile、run config 等の優先順位と設定間の競合検査。
- `strata_cli/cli.py:784-828`、`strata_cli/cli.py:917-957` — effective plan と foreground 起動への引き渡し。
- `serve/server.py:9953-9960`、`serve/server.py:10059-10068` — サーバー側 parser と指定 run config の読み込み。
- `strata_cli/cli.py:2179-2196` — 失敗時のメッセージ形式・終了コード処理。
