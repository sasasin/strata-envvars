# `--model-config`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--model-config` |
| 別名 | なし |
| 値 | 1つの文字列。parser に型変換・選択肢・ファイル検証の指定はない |

## 役割

このオプションは `strata components rollback` で受理されますが、現行の rollback 処理では使われません。共通 parser の help は「テスト起動に使う run config」と説明していますが、rollback は前回保持されたエンジンを切り替えるだけで、テスト起動を実行しません。そのため、このコマンドに `--model-config` を付けても、モデル設定の読み込み、検証、エンジン切り替えへの影響はありません。

## 使い方

```sh
# 構文例。実行すると前回保持されたエンジンへの切り替えを行います。
strata components rollback --model-config /path/to/RUN_CONFIG.json
```

## 値と既定値

値は必須の位置値で、`RUN_CONFIG.json` は help 表示用の metavar です。省略時は `None` になります。parser には `type`、`choices`、必須性の指定がなく、値のパスや JSON 内容は検証しません。値を付けずに指定した場合は argparse の引数解析エラーになります。

ただし rollback の処理は `ctx.run_config` を読み取らないため、値を省略した場合も指定した場合も rollback の動作は同じです。ファイルが存在しない、または JSON でない値を渡しても、このオプションを理由とするファイル読み込みエラーは発生しません。

## 実行時の動作

共通 parser が `--model-config` を登録し、`run()` はその値を `Context.run_config` に格納します。`components rollback` 分岐はその Context を `updater.rollback_engine()` に渡しますが、`rollback_engine()` が参照するのはコンポーネント状態の `previous`、保持されたエンジンの manifest と検証結果、および現在のエンジンです。run config は参照しません。

ロールバックは保持されたエンジンを検証後、`switch_engine()` で切り替えます。切り替え時には engine の pin、active/previous/skipped 状態、履歴を更新し、必要に応じて保存済み tuning preset を再確認対象としてマークします。`--model-config` はこれらの選択や状態更新に関与しません。rollback 分岐ではネットワークからの取得も行いません。

## 適用条件と副作用

このオプション自体には副作用がありません。コマンド本体は `--model-config` の有無にかかわらず、前回のエンジンがなければ失敗し、存在すれば保持エンジンを検証して切り替えます。稼働中の engine がある場合の待機判定は rollback の `--wait` によるもので、モデル設定ファイルには依存しません。

## 出力とエラー

`--model-config` の値に起因する出力やエラーはありません。rollback 本体は前回エンジンがない場合や、すでにそのエンジンへ戻っている場合に終了コード `2` の `UpdateError`、保持エンジンが使用不能な場合に終了コード `5` の `UpdateError` を返します。成功時は human 出力または `--output json/jsonl` に結果を出します。これらは rollback の状態による経路であり、run config の値には依存しません。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56` — 共通 parser の定義。`--model-config` は `default=None`、metavar `RUN_CONFIG.json` で登録され、型・選択肢の指定がない。help はテスト起動用と説明する。
- `terminal/strata_cli/update_cmd.py:80-81` — `rollback` parser に共通引数を登録する。
- `terminal/strata_cli/update_cmd.py:318-340` — 値を `Context.run_config` に渡し、その後 rollback 分岐から `rollback_engine()` を呼び、結果を出力する。
- `terminal/strata_control/updater.py:408-429` — Context の `run_config` は「test start」用として定義されている。
- `terminal/strata_control/updater.py:1776-1798` — rollback が `previous` エンジンを検証し `switch_engine()` を呼ぶ処理。`ctx.run_config` の参照やテスト起動はない。
- `terminal/strata_control/updater.py:1723-1773` — エンジン切り替えに伴う pin・状態・履歴の更新と preset のマーク。
