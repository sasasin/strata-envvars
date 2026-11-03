# `strata components engines --force`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 値を取らないフラグ。`store_true`。 |

## 役割

このコマンドでは `--force` は parser に登録されていますが、導入済み engine の一覧処理に再試行・強制処理はありません。`strata components engines --force` と指定しても、`--force` なしの場合と同じ一覧を出します。これは共通 option 群 `_common()` を `engines` parser に適用しているため受理されるものの、一覧経路では値を使わないためです。

## 使い方

```sh
strata components engines --force
```

一覧表示に `--force` は不要です。JSON 形式で出す場合は `--output json` または `--json` を使えます。

## 値と既定値

値は不要で、指定時は真、未指定時は偽です。文字列値は受け付けません。`argparse` の `store_true` で宣言されているため、同じフラグを複数回指定しても真のままです（`strata_cli/update_cmd.py:53`）。

## 実行時の動作

`_common()` が `--force` を含む共通引数を登録し、`strata components engines` にも適用します（`strata_cli/update_cmd.py:47-56,82-83`）。CLI は `components engines` を `update_cmd.run()` に振り分け（`strata_cli/cli.py:2136-2138`）、`run()` は共通の `Context` に `force` 値を渡します（`strata_cli/update_cmd.py:254-256`）。しかし `engines` は続いて `_engines_command()` に分岐し、`lib.list_engines(ctx)` の結果を表示して戻ります（`strata_cli/update_cmd.py:272-273,358-377`）。一覧処理は導入済み package の情報を読み取ります（`strata_control/engine_library.py:180-195`）。この経路では `ctx.force` を参照しません。

同じ `Context.force` は updater の更新判定では、失敗済み version の再試行などに使われます（`strata_control/updater.py:637-642,1098-1105`）。その更新効果は `strata components engines` には適用されません。

## 適用条件と副作用

このフラグは一覧コマンドでは効果を持たず、engine の download、切替、削除、test start を起こしません。一覧処理は engine の状態やファイル情報を読むほか、稼働中かどうかを確認します（`strata_cli/update_cmd.py:361-364`、`strata_control/engine_library.py:180-195`）。`--force` によって適用条件や表示対象が変わる処理は確認できません。

## 出力とエラー

`--force` 固有の警告やエラーはありません。通常の人向け出力は導入済み engine の一覧と「何も変更していない」旨です（`strata_cli/update_cmd.py:368-377`）。JSON 系出力では一覧オブジェクトを成功結果として出力します（`strata_cli/update_cmd.py:364-367`）。`--force` は一覧処理で validation に使われず、他の失敗経路を変える根拠も確認できません。

## 根拠

- parser 宣言と `engines` への共通 option 適用: `strata_cli/update_cmd.py:47-56,82-83`
- CLI から updater command への分岐、force 値の Context 格納、一覧分岐: `strata_cli/cli.py:2136-2138`、`strata_cli/update_cmd.py:254-256,272-273,358-377`
- 一覧処理の読み取り動作: `strata_control/engine_library.py:180-195`
- `--force` が更新判定で使われる箇所（この文書のコマンドとは別経路）: `strata_control/updater.py:637-642,1098-1105`
