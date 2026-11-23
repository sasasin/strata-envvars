# `strata components engines --force`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。未指定時は `false`、指定時は `true`。 |

## 役割

現行 parser はこのコマンドで `--force` を受け付けますが、`engines` の一覧処理はフラグを参照しません。したがって、このスコープで指定しても失敗した engine の再試行や一覧内容の変更は起きません。`--force` の help 説明にある再試行用途は update 系の処理に対する説明であり、`engines` には適用されません（`terminal/strata_cli/update_cmd.py:47-56,82-83,337-338,445-465`）。

## 使い方

```sh
# インストール済み engine の一覧を表示する。--force を付けても一覧処理への効果はない
strata components engines --force
```

## 値と既定値

`argparse` の `action="store_true"` として登録され、値は不要です。省略時は偽、指定時は真になります。短縮別名は登録されていません。値を続けて渡す形式ではありません（`terminal/strata_cli/update_cmd.py:53`）。

## 実行時の動作

`engines` parser は `_common` を通じて共通引数として `--force` を登録します。実行時には値が `updater.Context.force` に格納されますが、コマンド分岐は `engine_library.list_engines(ctx)` を呼び、その処理はインストール済み engine の走査・適合性判定・一覧データの組み立てを行います。`list_engines` 以下の一覧処理には `ctx.force` の参照がなく、再試行や更新処理へ進む分岐もありません（`terminal/strata_cli/update_cmd.py:82-83,314-321,337-338,445-452`; `terminal/strata_control/engine_library.py:98-134,152-167`）。

同じ `_common` によって `--force` を受理する `strata update` や `strata components rollback` などでは `Context.force` が別の処理で利用されますが、その動作はこの `engines` 文書の適用範囲外です（`terminal/strata_cli/update_cmd.py:59-83`; `terminal/strata_control/updater.py:713-729`）。

## 適用条件と副作用

`--force` 自体に一覧処理上の副作用はありません。一覧コマンドは engine を切り替えず、ダウンロードも行いません。通常の一覧生成は components ディレクトリ内の package を読み、backend / platform / driver などに基づく適合性を調べ、実行中プロセスの使用状況も一覧用データに付けます（`terminal/strata_control/engine_library.py:98-128,139-167`）。

## 出力とエラー

このフラグに固有の出力・警告・実行時エラー経路はありません。人向け出力では engine 一覧を表示し「Nothing was changed.」と案内します。`--output json` または `--output jsonl` では一覧データを JSON で出力します。いずれも `--force` の有無を分岐条件にしていません（`terminal/strata_cli/update_cmd.py:56,305-306,445-465`）。値を付けて `--force true` のように書くと余分な引数となり、CLI の parser が usage error として終了コード 2 で拒否します（`terminal/strata_cli/cli.py:2325-2334`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56` — 共通 parser でのフラグ定義。`store_true` で値なし、既定値 `false`。
- `terminal/strata_cli/update_cmd.py:82-83` — `engines` に共通 parser 引数を登録。
- `terminal/strata_cli/update_cmd.py:314-321` — CLI 値を `Context.force` に格納。
- `terminal/strata_cli/update_cmd.py:337-338,445-465` — `engines` の分岐、一覧呼び出し、人向け / JSON 出力。分岐内で force を参照しない。
- `terminal/strata_cli/cli.py:2325-2334` — 未認識引数の parser error 経路。
- `terminal/strata_control/engine_library.py:98-134,139-167` — 一覧の走査・適合性判定・使用状態の集約。`ctx.force` は参照しない。
- `terminal/strata_control/updater.py:713-729` — `ctx.force` が failed / rollback 済み engine の update 判定で使われる箇所。`engines` からは呼ばれない。
