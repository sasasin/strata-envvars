# `strata doctor --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata doctor` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。オプション一覧と使い方を表示する |

## 役割

`strata doctor` の利用法と、その parser で受け付けるオプションを表示する。`-h` は同じ help action の短縮別名。

## 使い方

```sh
strata doctor --help
strata doctor -h
```

## 値と既定値

値は不要で、既定値や入力値の validation はない。`doctor` は `argparse` の `add_parser` で作られ、独自に help を無効化していないため、標準の `-h` / `--help` が追加される。実際の help 表示には `--profile PROFILE`、`--components`、`--live`、`--output {human,json}` に加えて、後段で追加される `--json` と `--quiet` も含まれる（`strata_cli/cli.py:109-113, 508-515`）。

## 実行時の動作

help action は usage とオプション説明を標準出力に表示して終了する。通常の診断処理は `_doctor` が profile を解決し、component inspection を実行するが（`strata_cli/cli.py:1023-1045`）、help 表示ではそこへ進まない。コマンド分岐から `_doctor` を呼ぶのは引数解析後の通常実行時である（`strata_cli/cli.py:2138-2139, 2217-2237`）。

この checkout で `python strata.py doctor --help` を実行し、上記の option 群が表示され終了コード 0 となることを確認した。これは同一 revision の CLI help 出力であり、実装根拠は parser 定義である。

関連する注意として、help に表示される `--components` は parser で受理されるが、現在の `_doctor` はこの値を参照せず、component inspection を常に呼び出す（`strata_cli/cli.py:111, 1023-1028`）。この option の説明にある「default」と実装上の振る舞いは区別される。

## 適用条件と副作用

help action 自体は診断、GPU probe、component inventory を実行しない。`--live` の GPU query は `_doctor` に渡される通常実行時の経路にある（`strata_cli/cli.py:112, 1027-1028`）。

起動経路全体では、`strata.py` が parser より先に handover 判定を行い、source checkout では installed Control への handover を行わない（`strata.py:30-42`; `strata_cli/handover.py:126-134`）。また `main` は引数解析前に `adopt_user_defaults()` を呼ぶ。この関数は Windows でプロセス token の既定 owner / DACL を設定し、Windows 以外では何もしない（`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-357, 372-385`）。この副作用は help action 自体による診断ではない。

## 出力とエラー

確認した help 出力は標準出力に表示され、終了コードは `0`。help の標準出力には usage と各 option の説明が含まれる。未知引数は通常の parser error 経路で usage / error を出し、`argparse` の `error` により終了する（`strata_cli/cli.py:2223-2231`）。その失敗時の終了コードは標準 `argparse` の挙動に従い `2`。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser とサブコマンド parser の構成。
- `strata_cli/cli.py:109-113` — `doctor` parser と明示的な引数。
- `strata_cli/cli.py:508-515` — `doctor` を含む one-shot parser 群への `--json` / `--quiet` 追加。
- `strata_cli/cli.py:1023-1045` — doctor の実処理、出力と結果に応じた終了コード。
- `strata_cli/cli.py:2217-2237` — 起動時処理、引数解析、未知引数処理、通常実行への分岐。
- `strata_cli/cli.py:2138-2139` — doctor の通常実行を `_doctor` に委譲。
- `strata.py:30-42`、`strata_cli/handover.py:126-134` — CLI entry point と checkout 時の handover 条件。
- `strata_control/private_files.py:349-357, 372-385` — Windows の既定 token owner / DACL 設定と非 Windows での no-op。
