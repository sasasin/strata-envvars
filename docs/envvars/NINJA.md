# `NINJA`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`NINJA` は、macOS / Apple Silicon 向け DeepSeek-V4.1-Flash engine の build/package スクリプト `packaging/mac/build_dsv41_engine.sh` が Ninja 実行ファイルの場所を選ぶために参照します。Strata の通常の実行ファイルやサーバーが読む箇所はありません。候補一覧には載っていますが、実際の適用範囲はこの開発・配布用スクリプトに限られます。

## 値と判定

| 状態 | 選ばれる値 |
|---|---|
| 未設定または空文字 | `command -v ninja` が返すパス。見つからなければ `$HOME/strata-mac/tools/bin/ninja` |
| 空でない値 | その値をそのまま使用 |

文字列や数値としての parse・検証はありません。`NINJA=0` や `NINJA=false` も特別な意味を持たず、その名前の実行ファイルを指します。空白を含む値も変数全体が引用されて実行されるため、値を「実行ファイルと引数」に分割する機能はありません。値を実行できない場合、明示的な fallback はありません。

## 有効になる条件

この変数を読むのは `packaging/mac/build_dsv41_engine.sh` だけです。同スクリプトは Apple Silicon 用 Metal engine component の構成・build・package を行うものとして記述されています。OS や backend を調べて `NINJA` を有効化する分岐はなく、Strata 本体の runtime、CLI、server mode、モデル状態には影響しません。

スクリプト引数 `--build` は build directory を変えますが、Ninja の選択には関与しません。`NINJA` が空でない場合は PATH 上の `ninja` より優先されます。未設定・空文字の場合に限り PATH 検索、それが失敗した場合に `$HOME` 配下の既定パスへ進みます。

## 実行時の詳細

スクリプトの引数処理後、build の開始前に一度値を設定します。実行中の環境変更を読み直す処理や cache はありません。

実行ファイル `$BUILD/strata_ds4` がまだ実行可能でない場合、スクリプトは CMake に `-DCMAKE_MAKE_PROGRAM="$NINJA"` を渡して build tree を構成します。その後は既存 binary の有無にかかわらず、選択したパスを `"$NINJA" -C "$BUILD" strata_ds4` として直接実行します。したがって環境変数は CMake の generator 名 `Ninja` を切り替えるものではなく、generator の実行ファイルを指定します。

CMake または Ninja の実行が失敗すると、スクリプトは `|| exit 1` で終了します。NINJA 固有の警告文や値のエラー検査はありません。失敗時の詳細は実行されたコマンド側の出力に委ねられます。変数は子プロセスに渡す設定としてではなく、スクリプト内でコマンドパスに展開されています。

## 根拠

- `packaging/mac/build_dsv41_engine.sh:1-8,19-20` — bash スクリプトであること、Apple Silicon 向け目的、`set -u`。
- `packaging/mac/build_dsv41_engine.sh:25-37` — CLI 引数処理と `NINJA` の unset/empty fallback、明示値の優先。
- `packaging/mac/build_dsv41_engine.sh:41-47` — binary がない場合の CMake 引き渡しと、常に行う Ninja 直接実行・失敗時終了。
- `docs/DEEPSEEK_MAC.md:85-95` — このスクリプトを使う engine packaging 手順と成果物の説明。
