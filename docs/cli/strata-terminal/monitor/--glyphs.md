# `strata monitor --glyphs`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata monitor` |
| オプション | `--glyphs` |
| parser | `strata_cli/monitor_commands.py` |

## 役割

対話 monitor のグラフ、メーター、枠などに使う文字セットを選びます。選べる値は `auto`、`unicode`、`braille`、`ascii` です。値を省略した場合は `auto` です。短縮 alias はありません（`strata_cli/monitor_commands.py:49-59`）。

## 使い方

```sh
strata monitor --glyphs ascii
strata monitor --glyphs braille
```

このオプションは `strata monitor` のオプションです。`strata launch` が開く monitor も同じ `MonitorApp` を基底として使いますが、この文書の parser scope は `strata monitor` です（`strata_cli/cli.py:488-493`、`strata_cli/launch/monitor_ext.py:1-8,39-48`）。

## 値と既定値

| 値 | 動作 |
| --- | --- |
| `auto`（既定） | 出力 encoding、`TERM`、Windows の従来型コンソールかどうかから選びます。通常は Unicode を出力できる場合 `unicode`、`TERM=dumb` または encoding がない・Unicode を encode できない場合は `ascii` です。従来型 Windows コンソールでは `unicode` または内部値 `solid` を選びます（`strata_cli/monitor.py:26-45`）。 |
| `unicode` | Unicode のブロック文字、細分化された sparkline、丸みのある枠などを使います。 |
| `braille` | 履歴グラフで Braille パターンを使い、2サンプルを1セルにまとめます。 |
| `ascii` | ASCII の `.#`、`.:-=+*@` 等を使い、ASCII 対応の枠にします。 |

`auto` の判定では `STRATA_GLYPHS` 環境変数も参照されます。`ascii` / `legacy` は ASCII を選び、`solid` は内部値 `solid` を選びます。`STRATA_GLYPHS=unicode` は従来型コンソール判定を無効化します。従来型 Windows コンソールでは Cascadia Mono が使用可能なら現在のコンソール窓に設定を試みて Unicode 表示にし、そうでなければ `solid` 表示にします（`strata_cli/consoleinfo.py:24-36,118-140,143-177`、`strata_cli/monitor.py:26-45`）。コマンドラインで `--glyphs` に `auto` 以外を明示した場合は、その値を `choose_glyphs` がそのまま採用します（`strata_cli/monitor.py:26-29`）。

## 実行時の動作

値は `MonitorApp` に渡され、起動時に stdout の encoding と `TERM` を使って解決されます（`strata_cli/monitor_commands.py:214-229`、`strata_cli/monitor.py:108-143`）。対話 monitor の Overview では、標準サイズで描く dashboard / overview renderer に渡されます。ダッシュボードの sparkline は `ascii` なら ASCII ramp、`braille` なら Braille、その他は Unicode ramp を使い、バーと枠も ASCII 指定に応じて切り替わります（`strata_cli/monitor.py:190-231`、`strata_cli/dashboard.py:166-187,743-752`、`strata_cli/overview.py:202-239,302-312`）。

`braille` の場合、sparkline は幅あたり最大2倍の履歴サンプルを読み、各セルに連続2サンプルを表します（`strata_cli/dashboard.py:166-187,190-203`）。Overview の専用 renderer では `braille` は独立分岐せず、`ascii` と内部値 `solid` 以外として Unicode ramp を使います（`strata_cli/overview.py:202-222,302-308`）。

`--once` または `--output json` / `--json` の経路では snapshot を取得し、JSON または固定幅のテキスト Overview を出力します。これらの経路は `MonitorApp` を起動せず、`--glyphs` は出力に反映されません。JSON 出力にはグラフ描画もありません（`strata_cli/monitor_commands.py:191-213`）。

## 適用条件と相互作用

- `--glyphs` は対話 monitor の描画だけに関係し、サーバー設定や telemetry の取得内容は変更しません。monitor は read-only client として登録されています（`strata_cli/monitor_commands.py:49-60,107-113`）。
- 対話 monitor は TTY が必要です。TTY でない場合は `--once` などを使うようエラーになります。`--once` / JSON では前述の通りこの文字セット指定は適用されません（`strata_cli/monitor_commands.py:191-194,203-229`）。
- `auto` は `TERM=dumb`、stdout encoding がない場合、または必要な Unicode 文字を encode できない場合に ASCII に fallback します（`strata_cli/monitor.py:26-45`）。
- 選択値以外は `argparse` の `choices` 検証で拒否されます。独自の後段 validation はありません（`strata_cli/monitor_commands.py:58`）。

## 出力と失敗

このオプション固有の標準出力、警告、終了コード変更はありません。未知の値は parser の引数エラーとなり、対話 monitor は `--once` なしで TTY がなければ終了コード `2` 相当のエラーを返します（後者は `--glyphs` 以外にも適用される monitor の起動条件です。`strata_cli/monitor_commands.py:189-194`）。

## 根拠

- `strata_cli/monitor_commands.py:49-60` — `strata monitor` parser、選択肢と既定値。
- `strata_cli/monitor_commands.py:189-240` — validation、one-shot / 対話経路、描画アプリへの値の受け渡し、失敗処理。
- `strata_cli/monitor.py:26-45,108-143,181-231` — `auto` の解決、monitor 初期化、各 renderer への引き渡し。
- `strata_cli/dashboard.py:166-187,190-220,743-752` — 通常 dashboard の sparkline と Braille 描画。
- `strata_cli/overview.py:202-239,302-312` — Overview の sparkline、バー、ASCII / solid / Unicode 描画。
- `strata_cli/consoleinfo.py:24-36,118-177` — 従来型 Windows コンソールの判定、フォント切替と style 決定。
- `strata_cli/cli.py:488-493`、`strata_cli/launch/monitor_ext.py:1-8,39-48` — コマンド登録と launch monitor との関係。
