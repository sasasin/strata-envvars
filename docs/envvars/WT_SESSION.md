# `WT_SESSION`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`WT_SESSION` は Strata CLI が Windows Terminal などの端末セッションを見分けるための印として扱う。Strata は値の内容を利用せず、空でない値かどうかだけを見る。読み取り箇所は `terminal/strata_cli/launch/cmd.py` の `_can_ask()` と `terminal/strata_cli/consoleinfo.py` の `legacy_console()`（`terminal/strata_cli/launch/cmd.py:570-584`、`terminal/strata_cli/consoleinfo.py:24-35`）。

- `strata launch` では、画面を開けない状況でも入力可能なセッションとして plain な質問に進めるかの判定材料の一つになる。`WT_SESSION` だけで TUI の起動可否や質問の実施を決めるわけではない（`terminal/strata_cli/launch/cmd.py:847-866, 937-944`）。
- Windows のクラシックコンソール判定では、非空の `WT_SESSION` を「クラシックではない」側にする。この判定はモニターや launch 画面のグリフ選択に使われる。値が空でない場合、他の条件がなければ Strata のクラシックコンソール向け書体変更やソリッド表示は選ばれない（`terminal/strata_cli/consoleinfo.py:24-35, 158-178`、`terminal/strata_cli/monitor.py:26-45, 139-144`、`terminal/strata_cli/launch/widgets.py:43-57`）。

## 値と判定

どちらの読み取りも Python の `os.environ.get("WT_SESSION")` 相当で、文字列全体の比較や数値変換はしない。Python の真偽値判定により、未設定と空文字は偽、長さが 1 文字以上の値は真となる。`"0"`、`"false"`、空白だけの文字列も非空なら真。大文字小文字、数値形式、前後空白の検証はない（`terminal/strata_cli/launch/cmd.py:580,583`、`terminal/strata_cli/consoleinfo.py:33-35`）。

| 条件 | unset / 空文字 | 非空値の例 | 判定への効果 |
|---|---|---|---|
| `_can_ask()` のセッション印 | 偽 | `1`、`0`、`false`、空白 | 他の3つの印と同列の OR 条件。1つでも真ならセッション印の条件を満たす。 |
| Windows の `legacy_console()` | unset は他の印・`TERM` 判定へ進む。空文字も偽 | `1`、`0`、`false`、空白 | `STRATA_GLYPHS` による強制がない場合、非空ならクラシックコンソール判定を偽にする。 |

launch の `_can_ask()` では `WT_SESSION` と `MSYSTEM`、`TERM_PROGRAM`、`TERM` を OR で確認する。Windows の `legacy_console()` では `WT_SESSION`、`TERM_PROGRAM`、`ConEmuANSI`、`ANSICON` のいずれかが真ならクラシック判定を偽にし、それらが偽の場合も `TERM` が `xterm`、`screen`、`tmux`、`vt` のいずれかで始まると偽にする。`TERM` の前方一致は大文字小文字を区別する（`terminal/strata_cli/launch/cmd.py:580,583`、`terminal/strata_cli/consoleinfo.py:33-35`）。

## 有効になる条件

- **launch の plain 質問経路:** TTY 入出力でない等により `interactive` が偽で、選択肢がまだなく、`--plan` でないことが前提。さらに `--output json`、`--no-tui`、カタログ不在のいずれでもなく、`_can_ask()` が真である必要がある。`_can_ask()` は stdin が閉じていないことを確認し、`CI` または `STRATA_NO_PROMPT` が真なら `WT_SESSION` を含む各端末印を調べる前に偽を返す。`strata_cli.noinput` が利用可能なら、stdin が null device（Windows の NUL を含む）と判定された場合も偽を返す。したがって `WT_SESSION` が非空でもこれらの条件で質問経路には進まない（`terminal/strata_cli/launch/cmd.py:570-584, 847-866`、`terminal/strata_cli/noinput.py:16-24`）。
- 質問経路に進んだ場合は、screens 用 package 不足の案内がすでに出ていなければ画面非対応の説明を出し、`Start it now? Models can be tens of GB to download. [Y/n]` を尋ねる。空入力、`y`、`yes` は続行し、それ以外は `Nothing was changed.` を出して終了コード 0。EOF はエラー文を stderr に出し、終了コード 2（`terminal/strata_cli/launch/cmd.py:863-866, 937-944, 759-764`）。この経路では machine / `--no-tui` は先に除外される。
- **クラシックコンソール判定:** `os.name == "nt"` または `sys.platform == "win32"` が必要。非 Windows では `WT_SESSION` に関係なく `legacy_console()` は偽。Windows でも `STRATA_GLYPHS` を空白除去・小文字化した値が `ascii`、`legacy`、`solid` なら強制的に真、`unicode` なら強制的に偽となり、これらの指定が `WT_SESSION` より先に判定される（`terminal/strata_cli/consoleinfo.py:24-35`）。
- Windows でクラシックと判定されると、モニターの自動グリフ選択は `STRATA_GLYPHS=ascii|legacy` なら ASCII、`solid` ならソリッド、その他は Cascadia Mono へ切り替えできたとき Unicode、それ以外はソリッドを選ぶ。launch widgets もクラシック時に Unicode が使えるかを判定する。非クラシック時はモニターが出力 encoding で描画文字を encode できるかにより Unicode または ASCII を選び、`TERM=dumb` または encoding なしなら ASCII（`terminal/strata_cli/monitor.py:26-45`、`terminal/strata_cli/launch/widgets.py:43-57`）。

## 実行時の詳細

`_can_ask()` は `strata launch` の選択肢なし・非対話経路を選ぶ時点で呼ばれ、その呼び出しで環境を読み取る。プロンプト用の判定結果を保存するキャッシュはない。`legacy_console()` も呼び出しごとに環境を参照するが、Windows コンソールの詳細スタイルを返す `classic_style()` は最初の呼び出し結果をモジュール変数 `_cached` に保存し、以後は再判定しない。そのため、スタイルの初回確定後に環境を変更しても `classic_style()` の結果は更新されない。一方 `legacy_console()` 自体の結果は次の呼び出しで現在の環境を参照する（`terminal/strata_cli/launch/cmd.py:570-584`、`terminal/strata_cli/consoleinfo.py:24-35, 158-178`）。

読み取り箇所に `WT_SESSION` の値を子プロセスへ渡す・書き換える処理はない。関連機能は CLI 内の質問経路と画面描画の選択であり、モデル、GPU backend、サーバーモード、生成 token には作用しない（上記読み取り箇所と呼び出し先: `terminal/strata_cli/launch/cmd.py:847-866`、`terminal/strata_cli/monitor.py:26-45, 139-144`、`terminal/strata_cli/launch/widgets.py:43-57`）。

## ログと測定値

`WT_SESSION` を理由として専用のログや警告を出す処理はない。質問経路に入ったときの画面非対応案内は `no_screens_words()` が出力するが、その文面は OS / `MSYSTEM` から作られ、`WT_SESSION` の値は表示しない（`terminal/strata_cli/launch/cmd.py:559-567, 863-866`）。性能測定値は該当しない。

## 根拠

- `terminal/strata_cli/launch/cmd.py:559-584, 847-866, 937-944` — 画面非対応案内、`_can_ask()` の読み取りと条件、呼び出し側および plain 質問。
- `terminal/strata_cli/launch/cmd.py:759-764` — launch エラーの stderr / JSON 出力と終了コード。
- `terminal/strata_cli/noinput.py:16-24` — null device と pipe / file の区別。
- `terminal/strata_cli/consoleinfo.py:24-35, 158-178` — Windows クラシック判定、環境変数の優先とスタイル結果の cache。
- `terminal/strata_cli/monitor.py:26-45, 139-144` — モニターの glyph 選択とコンソール状態の利用。
- `terminal/strata_cli/launch/widgets.py:43-57` — launch 画面の Unicode glyph 判定。
