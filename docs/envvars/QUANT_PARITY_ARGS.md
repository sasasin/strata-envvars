# `QUANT_PARITY_ARGS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`engine/tests/quant/run_oracle.sh` が、この値を量子化 oracle 実行ファイル `quant_parity` の追加コマンドライン引数として渡す。モデル推論・サーバー・通常の Strata 実行を設定する変数ではなく、スクリプトから量子化比較の対象や出力方法を指定する用途である。同スクリプトはビルドした `quant_selftest` と `quant_parity` を flavour ごとに実行し、`quant_parity` の失敗で最終終了コードを非ゼロにする（`engine/tests/quant/run_oracle.sh:31-47`）。

## 値と判定

シェルは `${QUANT_PARITY_ARGS:-}` で未設定または空文字を空に展開する。値全体の検証や引用符の再解釈はせず、展開箇所が非引用なので Bash の IFS による単語分割と pathname expansion を受ける。したがって `--rows 64` は通常 `--rows` と `64` の二引数になる一方、値の中に書いた引用符は空白を保護する引用符として機能しない。空白だけの値は引数を生まないが、スクリプトの後続条件では「空文字ではない」値として扱われる（`engine/tests/quant/run_oracle.sh:38-44`）。

| `QUANT_PARITY_ARGS` の状態・展開後 | `run_oracle.sh` の扱い |
|---|---|
| 未設定または空文字 | `quant_parity` に追加引数なし。golden ファイルが存在すれば、別途 `--regen-check` も実行する。 |
| `--rows 64` など認識可能な引数列 | その単語列を `quant_parity` に渡す。空白の分割後に値がどのオプションへ結び付くかは同プログラムの argv 順序で決まる。 |
| 無効な引数、値の不足 | `quant_parity` が `quant_parity: unknown argument <引数>` を出して終了コード 2 を返す（`engine/tests/quant/quant_parity.cpp:642-653`）。 |
| 空白だけ | `quant_parity` へは追加引数なし。ただし環境変数文字列自体は空ではないため、`run_oracle.sh` は `--regen-check` を追加実行しない（`engine/tests/quant/run_oracle.sh:38-44`）。 |

`quant_parity` が認識する引数は `--rows N`、`--type NAME`、`--verbose`、`--golden FILE`、`--dump-group KEY`、`--write-golden FILE`、`--regen-check`。オプション名は文字列全体の完全一致で比較する。`--rows` の値は `std::atoi` で変換し、数値全体の妥当性確認、範囲検査、clamp はない。例えば `64tail` は 64、`tail` は 0、`-1` は -1 になる。`--type` 等の文字列値はそのまま受け取り、型名は後段で完全一致比較される（`engine/tests/quant/quant_parity.cpp:642-653, 708-718`）。

同じ値を設定するオプションを複数回渡した場合、argv を左から読むループで後の値が前の値を上書きする。`--verbose` と `--regen-check` は真偽値を有効にするだけで、後続引数で解除する手段はない（`engine/tests/quant/quant_parity.cpp:642-649`）。

## 有効になる条件

- `engine/tests/quant/run_oracle.sh` が呼び出されること。通常の engine 起動やサーバーモードがこの変数を読むコードは確認できない（参照箇所全体: `engine/tests/quant/run_oracle.sh:6,38-42`、`engine/tests/quant/make_golden.sh:21`）。
- 引数の内容が実行したい `quant_parity` の CLI 形式に合うこと。`--rows` の指定値は比較に使う行数を変え、既定は 24。golden の基準行数 24 と異なる場合、golden leg は有効にならず、`--regen-check` も `rows != 24` で失敗する。`--write-golden` は `--type` または 24 以外の `--rows` と併用すると拒否される（`engine/tests/quant/quant_parity.cpp:125, 683-707, 721-725`）。
- 実行対象の flavour や CPU によって比較経路が変わる。`run_oracle.sh` は OS/CPU 名から既定 flavour を選ぶか、引数で指定された flavour を使い、CUDA/HIP を無効にして CPU oracle をビルドする（`engine/tests/quant/run_oracle.sh:18-35`）。これは環境変数自体の値判定ではなく、スクリプトの実行条件である。
- `QUANT_FORCE_ISA` が空でなければ、スクリプトは別途 `STRATA_FORCE_ISA` を設定して `quant_parity` を起動する。これは `QUANT_PARITY_ARGS` とは独立した追加条件である（`engine/tests/quant/run_oracle.sh:39-40`）。
- `make_golden.sh` 経由では、呼び出し側の値にかかわらず各 flavour 実行の環境へ `--write-golden $ROOT/gcc-$f.txt` を設定して `run_oracle.sh` を呼ぶ。従ってその経路ではこの引数が golden 断片の生成を選ぶ（`engine/tests/quant/make_golden.sh:18-24`）。

## 実行時の詳細

`run_oracle.sh` は各 flavour のループ内で値を展開する。環境値を数値などへキャッシュする処理はなく、シェルによる引数化は各 flavour の `quant_parity` 起動時に行われる。値を起動後に親環境側で変更しても実行中シェルの環境には反映されない。`quant_parity` の C++ 実装には `QUANT_PARITY_ARGS` の直接読み取りはなく、受け取った `argv` をオプション解析する（`engine/tests/quant/run_oracle.sh:23,38-40`; `engine/tests/quant/quant_parity.cpp:637-653`）。

引数により、比較行数・対象型・詳細表示・golden 入力ファイル・行ダンプ・golden 出力ファイル・再生成確認を選べる。`--write-golden FILE` は全グループを基準行数で実行した後に FILE を書き、書けなければ終了コード 2。golden の不一致は実行内容に応じて失敗として報告され、通常は最終終了コード 1 となる（`engine/tests/quant/quant_parity.cpp:708-735, 779-789`）。

値が未設定または空文字のとき、golden ファイルが存在すればスクリプトは `quant_parity --regen-check` も実行する。任意の非空文字（空白だけを含む場合も含む）を設定するとこの追加チェックは抑止される。追加チェックの終了コード 77 はスクリプト上では失敗扱いにせず、それ以外の非ゼロ値は失敗として集約する（`engine/tests/quant/run_oracle.sh:41-46`）。

## ログと測定値

スクリプトは起動前に `=== flavour <flavour>: quant_parity <値>` を出力する。未知引数は `quant_parity: unknown argument <引数>`、不正な `--write-golden` の組み合わせは `quant_parity --write-golden: refused with --type or --rows (the golden file holds every group at --rows 24)` を出す。`quant_parity` の終了コードは `run_oracle.sh` が flavour 間で集約し、最終的な成功・失敗として返す（`engine/tests/quant/run_oracle.sh:38-47`; `engine/tests/quant/quant_parity.cpp:650-653, 721-725`）。性能測定値はこの変数の挙動に該当しない。

## 根拠

- `engine/tests/quant/run_oracle.sh:6, 38-46` — 候補の説明、値の展開、空値時の再生成確認。
- `engine/tests/quant/make_golden.sh:18-24` — この変数を `--write-golden` に設定して oracle スクリプトへ渡す呼び出し。
- `engine/tests/quant/quant_parity.cpp:637-653` — argv の既定値、オプション解析、`atoi`、不明引数の終了経路。
- `engine/tests/quant/quant_parity.cpp:683-725, 779-789` — golden 比較条件、行数制約、書き出し、最終結果と終了コード。
