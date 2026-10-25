# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile validate` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 取らない真偽フラグ。指定すると有効 |

## 役割

profile の検証成功時に表示する人間向け案内を抑制します。検証自体や終了コードは変えません。索引上の対象スコープは `strata profile validate` です。

## 使い方

```sh
strata profile validate office --quiet
```

`office` は保存済み profile 名です。profile 名は小文字 `a-z` で始まり、小文字英数字・`_`・`-` を使う1〜64文字に限られます（`strata_control/profiles.py:25,48-55`）。

## 値と既定値

値は不要で、`store_true` により指定時は真になります。個別の profile parser ではなく one-shot parser 群へ追加され、既定値は `argparse.SUPPRESS` です。未指定時は `main()` が `getattr(..., False)` として扱います。短縮別名はありません（`strata_cli/cli.py:81-83,508-515,2236`）。

## 実行時の動作

`strata profile validate` は保存 profile を読み、参照 run config を読んで有効な launch plan を組み立てます。検証には profile の schema・ID・絶対パス・override、run config の JSON 構造、override の範囲と組み合わせ、および API key の形式などが含まれます（`strata_cli/cli.py:958-969,1015-1020,782-826,745-779`; `strata_control/profiles.py:120-147`）。検証後は既定の human 出力として `Profile <name> is valid at revision <revision>` を表示しますが、`--quiet` 指定時は成功した one-shot コマンドの stdout を捕捉して表示しません（`strata_cli/cli.py:535-542,1015-1020,2217-2248`）。

`--output json` または alias の `--json` と併用した場合、JSON レコードは抑制されません。`main()` は出力形式が JSON のとき quiet の stdout 捕捉を行わず、`_success()` は `ok: true` を含む JSON を出力します（`strata_cli/cli.py:513-515,535-542,2232-2237`）。

## 適用条件と副作用

このフラグは one-shot parser の共通追加対象であり、`profile validate` では有効です。`store_true` のため値を付ける形式ではありません。重複指定は同じ真値のままです（`strata_cli/cli.py:508-515`）。

`--quiet` 自体は profile や run config を変更せず、サーバーも起動しません。validate は profile と run config を読み、launch plan を計算します（`strata_cli/cli.py:1015-1020,782-826`）。ただし保存 profile の読込は、アクセス拒否時に `read_bytes_repairing()` を通してアクセス権を修復し再試行する場合があります（`strata_control/profiles.py:150-166`; `strata_control/private_files.py:476-484`）。

## 出力とエラー

human 出力では、成功時の案内は `--quiet` で表示されません。失敗時のエラーは stderr に残り、終了コードも維持されます。quiet の共通処理は `_run()` の結果が失敗なら捕捉済み stdout があれば stderr に戻し、64 KiB を超えて切り詰めた場合は省略通知も stderr に出します。通常の validate 失敗は `ValueError` 系を `_error()` が処理し、human 形式では `strata: <message>` を stderr に出します（`strata_cli/cli.py:527-532,2166-2183,2196-2208,2241-2248`）。

`--output json` の失敗ではエラー JSON が出力され、quiet でも抑制されません（`strata_cli/cli.py:527-532,2172-2173,2232-2237`）。profile の不在・読込失敗、run config の不正、値の矛盾などが失敗要因になります。例えば profile 読込の不在・I/O・形式エラーは終了コード5、通常の profile validation error は既定で2です（`strata_control/profiles.py:30-35,120-147,150-166`）。

## 根拠

- `strata_cli/cli.py:81-83` — `profile validate` parser と positional name、出力形式の定義。
- `strata_cli/cli.py:508-515` — one-shot parser 群に対する `--json` / `--quiet` の追加。`--quiet` は `store_true`、既定値 `SUPPRESS`。
- `strata_cli/cli.py:958-969,1015-1020` — profile の読込と validate 時の plan 構築、成功メッセージ。
- `strata_cli/cli.py:745-826` — 実効値の validation、衝突条件、launch plan の構築。
- `strata_cli/cli.py:527-542,2119-2173,2217-2248` — 成功・失敗出力、quiet の捕捉と JSON 例外。
- `strata_control/profiles.py:25,48-55,120-166` — profile 名、schema、run config、読込失敗の規則。
- `strata_control/private_files.py:476-484` — profile 読込時にアクセス権を修復して再試行する処理。
