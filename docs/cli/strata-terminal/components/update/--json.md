# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

更新処理の結果を機械処理向け JSON で出力します。更新内容や実行条件は変更せず、`--output json` の別表記として働きます。

## 使い方

```sh
strata components update --check --json
```

更新を実行する場合は `--check` を外します。`components update` は通常、エンジンと Control の更新を行うコマンドです。

## 値と既定値

値は不要で、既定では `--json` は無効、出力形式は `--output human` です。`--json` は Terminal CLI が update parser に後から登録する `store_true` フラグで、`strata components update` でも有効です。値を後置する構文はありません。`--output` は `human`、`json`、`jsonl` を受け付けます。

## 実行時の動作

CLI の parser 構築時、`update_cmd.add_parsers` が返す parser 群に `--json` と `--quiet` が追加されます。`main` は `--json` が有効なら `a.output` を `json` に設定してからコマンドを実行します。そのため、`--output human --json` と指定しても JSON が選ばれます。`--output json` と `--json` の併用も同じ出力形式です。

`update_cmd.run` は `output` が `json` または `jsonl` のとき機械出力モードとし、JSON 形式では成功時に `schema_version` と `ok` を含む結果、失敗時に `schema_version` と `ok: false`、エラーコード・メッセージを含むオブジェクトを stdout に出します。JSON モードでは進捗イベントを個別には表示せず、最終結果を出力します。`--check` の結果も JSON オブジェクトになります。

## 適用条件と副作用

これは一回で完了するコマンド向けの option です。`--output jsonl` と同時に指定すると CLI が拒否し、「`--json` は one-shot only」とする失敗イベントを stdout に出して終了コード 2 を返します。JSON 出力自体は更新を開始・抑止しません。更新の有無は `--check`、`--no-engine`、`--no-control`、`--app` などの update option で決まります。更新を実行する場合のダウンロード・インストール等の副作用は `--json` によるものではありません。

## 出力とエラー

実行時エラーは JSON モードでは stdout のエラーオブジェクトとして出力され、コマンドが返す終了コードを維持します。たとえば feed、署名、acquisition 拒否、割り込みは `update_cmd.run` の失敗経路で処理されます。parser が認識しない引数や `--json` の後に余分な値を置いた場合は、`argparse` の usage/error 経路となり、stderr にエラーを出して終了コード 2 です。

## 根拠

- `strata_cli/cli.py:139-140` — update parser 群を登録。
- `strata_cli/update_cmd.py:30-59` — `--output` の値と既定値、`components update` parser、共通 option の登録対象。
- `strata_cli/cli.py:508-515` — update parser 群へ値なし `--json`（`store_true`）を追加。
- `strata_cli/cli.py:2223-2237` — parse 後に `--json` を `output=json` に反映し、`jsonl` との併用を拒否。
- `strata_cli/cli.py:2135-2137` — `strata components update` を `update_cmd.run` に委譲。
- `strata_cli/update_cmd.py:62-84,163-224` — 機械出力判定、進捗出力、check/更新結果の JSON 出力。
- `strata_cli/update_cmd.py:225-235` — JSON モードの実行時失敗を処理。
- `strata_cli/cli.py:829-835` — `--output jsonl --json` の拒否時に失敗イベントを出力する経路。
- `docs/cli/README.md`（調査対象リポジトリ側）— `strata components update` の option scope 注記と `--json` の索引リンク。
