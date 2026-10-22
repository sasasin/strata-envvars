# `STRATA_GLYPHS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata の端末 UI が使う文字表示を選びます。主な対象は `strata monitor` と起動画面の矢印・区切り線・チェック記号・グラフ文字です。Windows の従来型コンソールを自動判定する処理にも影響します。GPU 計算やサーバーの生成処理には関与しません。

## 値と判定

すべての読み取り箇所で、値は `strip().lower()` により前後空白を除去して小文字化されます。空文字・空白だけの値、および以下にない値は、各呼び出し側で強制指定として扱われません。

| 正規化した値 | `legacy_console()` の判定 | `strata monitor` の自動選択 | 起動画面 (`Glyphs`) |
|---|---|---|---|
| `ascii`, `legacy` | 従来型コンソール扱いを強制 | 従来型扱いのとき ASCII | ASCII |
| `solid` | 従来型コンソール扱いを強制 | `solid`（Overview はブロック表示、他のテキストビューは ASCII） | 従来型扱いを強制し、自動でフォントを切り替えない。従来型スタイル時は通常 ASCII フォールバック |
| `unicode` | 従来型コンソール扱いを解除 | Unicode。ただし `TERM=dumb` または出力 encoding がない場合は ASCII | 通常の Unicode 可否判定に従う。端末が `dumb` なら ASCII |
| 未設定、空、その他 | 強制しない | 自動判定 | 自動判定 |

文字列の一致は正規化後の完全一致です。たとえば ` ASCII ` は `ascii` と同じですが、`ascii-extra` は一致しません。`STRATA_GLYPHS` 自体は数値変換をしません。

## 有効になる条件

- `strata monitor` は `choose_glyphs()` に渡された引数が `auto` のときだけ環境変数から文字種を自動選択します。引数が `auto` 以外ならその要求を返すため、CLI 側の明示指定が環境変数による選択に優先します。ただし `consoleinfo.legacy_console()` は別途呼ばれ、従来型コンソール判定や余白、フォント処理に環境変数が影響する場合があります。
- 自動選択で `TERM=dumb` または stdout encoding が空なら、従来型コンソール判定より先に ASCII になります。Unicode 候補文字列を encoding にできない場合も ASCII へ戻ります。
- `legacy_console()` の強制値は OS 判定より先に処理されます。そのため `ascii`, `legacy`, `solid` は非 Windows でも従来型扱いにし、`unicode` は Windows の従来型コンソールでも従来型扱いを解除します。値がその他の場合、非 Windows は `False`、Windows は `WT_SESSION`, `TERM_PROGRAM`, `ConEmuANSI`, `ANSICON` と `TERM` の接頭辞 (`xterm`, `screen`, `tmux`, `vt`) によって判定されます。
- 画面の文字を出力可能かどうかは別判定です。`unicode` の指定でも非対応 encoding なら monitor は ASCII を使い、起動画面も encoding への encode が失敗すれば ASCII の記号を使います。

## 実行時の詳細

`strata monitor` は `MonitorApp` の初期化時に `choose_glyphs()` を一度呼び、選択を `glyph_choice` に保持します。概要画面にはその値を渡し、`solid` は詳細テキストビューで ASCII に置き換えます。classic console の追加スタイルは `consoleinfo.classic_style()` が初回呼び出し時に `_cached` へ保存します。したがって、このプロセス内で初期化後に環境を変更しても、保持済みの選択やスタイルは自動再計算されません。

起動画面は `Glyphs()` 作成時に `unicode_ok()` を使って記号セットを決めます。`legacy_console()` と `classic_style()` では `STRATA_GLYPHS` を呼び出し時に読み直しますが、`classic_style()` の結果はキャッシュされます。従来型 Windows コンソールで強制値がなく、Cascadia Mono が利用可能なときは `classic_style()` の経路が現在のコンソールウィンドウのフォント切替を試みます。`ascii` / `legacy` / `solid` はこの自動切替を抑止します。これはその呼び出し側の設定効果であり、環境変数自体がフォント API を呼ぶわけではありません。

## 根拠

- `strata_cli/consoleinfo.py:24-35`: 値の正規化、強制値、従来型コンソール判定。
- `strata_cli/consoleinfo.py:143-178`: スタイル決定、強制値時のフォント切替抑止、初回結果のキャッシュ。
- `strata_cli/monitor.py:26-45,138-143,181-184,198-212`: monitor の自動選択、選択値の保持と各ビューへの適用。
- `strata_cli/launch/widgets.py:43-72`: 起動画面での Unicode 可否と記号セット。
- `docs/TERMINAL_LAUNCH.md:55`: 従来型 Windows コンソール向け表示と変数の概要。詳細な値判定は現行ソースに基づく。
