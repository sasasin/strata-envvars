# `--status-file`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets recheck` |
| オプション | `--status-file` |
| 別名 | なし |
| 値 | JSON ステータスを書き込むファイルパス（文字列） |

## 役割

プリセットの再チェック中の進捗と完了結果を JSON ファイルに記録します。CLI の parser では省略可能で、既定ではファイルを作りません。Terminal CLI とデスクトップアプリの共通コードにある進捗ファイル機構で、再チェックの測定条件や判定基準は変えません。`strata presets recheck` の parser がこのオプションを定義し、`_recheck` がその値をステータス書き込み関数に渡します（`strata_cli/tune_commands.py:82-90,411-446`）。

## 使い方

```sh
strata presets recheck <preset> <profile-or-config.json> --status-file ./recheck-status.json
```

`<preset>` は保存済みプリセット、2つ目の位置引数はそのプリセットが属するプロファイル名または run configuration JSON です（`strata_cli/tune_commands.py:82-88`）。例の出力先は現在の作業ディレクトリからの相対パスです。

## 値と既定値

- 値を1つ取ります。型変換、選択肢、パス形式の検査は parser に指定されていません。省略時は `None` で、ステータスファイルへの書き込みを行いません（`strata_cli/tune_commands.py:82-90,149-152`）。
- 同じオプションを複数回指定した場合の独自処理はありません。標準の `argparse` の単一値引数として最後に解析された値が使われます（`strata_cli/tune_commands.py:82-90`）。
- 空文字列も parser では拒否されませんが、書き込み関数は偽値のパスを指定なしと同様に扱います（`strata_cli/tune_commands.py:149-152`）。

## 実行時の動作

再チェックの各 progress callback で受け取った情報を `state` に追加し、指定先へ JSON として書き込みます。完了後は `state` を `done` にし、判定結果を `result` に入れてもう一度書き込みます。進捗 callback は再チェック中の測定開始時に呼ばれ、通常の payload には `stage`、`message`、`elapsed_s` が含まれます。長いプロンプト速度の再測定が必要なら、追加の callback も発生します（`strata_cli/tune_commands.py:430-442`; `strata_control/autotune.py:907-910,918-935`）。

各書き込みでは `<指定パス>.tmp` に UTF-8 JSON を書き、`strata_control.atomic.replace` で指定パスへ置き換えます。したがって既存の指定先は更新時に置換されます。親ディレクトリを作成する処理はなく、相対パスはプロセスの作業ディレクトリ基準です（`strata_cli/tune_commands.py:149-157`）。

`--output human` / `--output json` は同じ `presets recheck` parser に属する別オプションで、既定は `human` です。`--output json` の場合、進捗文は標準エラーにも出さず、最終結果は標準出力へ JSON で出ますが、指定されたステータスファイルへの記録は続きます（`strata_cli/tune_commands.py:53-55,82-90,426-446`）。

## 適用条件と副作用

- `--status-file` を指定しても、プリセットが現 PC と大きく異なる場合の hard-stale 拒否や、再チェックの実行条件は変わりません。hard-stale の場合はステータスファイルへ書く前にエラーを返します（`strata_cli/tune_commands.py:414-420,430-434`）。
- 書き込み時の `OSError` は無視されます。たとえば親ディレクトリがない、または書き込み権限がない場合、ステータス記録は失敗しても、その失敗自体は再チェック処理を中断しません。成功結果の記録後には `presets.record_recheck` がプリセット保存データも更新するため、ステータスファイルはその保存データの代替ではありません（`strata_cli/tune_commands.py:149-157,437-442`; `strata_control/presets.py:412-429`）。
- 最初の progress callback より前に失敗した場合は、初期状態 `{ "state": "running" }` がファイルへ書かれる保証はありません。書き込み失敗時に `.tmp` ファイルを削除する処理もありません（`strata_cli/tune_commands.py:430-442,149-157`）。

## 出力とエラー

書き込み成功時のファイル内容は JSON で、進捗時は初期の `state: running` と callback の項目、完了時はさらに `state: done` と `result` を含みます。JSON の末尾改行や整形出力は行いません（`strata_cli/tune_commands.py:149-157,430-442`）。

ステータスファイルの `OSError` は利用者向けエラーや終了コードになりません（同上）。一方、再チェックの前提処理で発生した `OSError` / `ValueError` は `presets_command` により `strata: <message>` を標準エラーに出して終了コード `2`（例外に `exit_code` があればその値）となり、`PresetError` は終了コード `5` です。`--output json` では同じエラー情報を `{ "schema_version": 1, "ok": false, "error": ... }` として標準出力に出します（`strata_cli/tune_commands.py:103-108,342-347`）。

## 根拠

- parser と option scope: `strata_cli/tune_commands.py:49-55,82-90`。`strata presets recheck` に定義され、`strata tune auto` にある同名オプションとは別 parser / 別コマンドです。
- 書き込みと例外処理: `strata_cli/tune_commands.py:149-157,411-446,342-347`。
- 再チェック callback の発生条件: `strata_control/autotune.py:885-935`。
- プリセット保存への副作用: `strata_control/presets.py:412-429`。
