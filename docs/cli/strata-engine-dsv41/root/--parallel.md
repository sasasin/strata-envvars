# `strata-dsv41 --parallel`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（トップレベル） |
| オプション | `--parallel` |
| 別名 | なし |
| 値 | 1〜8 の会話数（整数として `atoi` 変換） |

## 役割

`--serve` で同時に保持する会話枠数を指定します。各会話は独立した状態と KV を持ち、複数の `GEN` 要求を異なる `rid` で並行処理できます。GPU メモリを会話枠ごとに追加で使います。option の説明と `Options::seqs` の既定値 1 は parser の使用先ヘッダーにあります（`src/dsv41/ds4_main.cpp:120,2583-2589`、`src/dsv41/ds4_model.hpp:74-76`）。

## 使い方

モデル pack を指定して engine の server protocol を起動します。以下はエンジンが標準入力から `GEN` 要求を受け取る形です。

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --serve --parallel 4
```

`--parallel` 自体は `--serve` の有無を parser で検査しませんが、複数会話の request dispatch は `serve()` 内だけにあります。通常の一回実行で複数会話を処理する指定ではありません（`src/dsv41/ds4_main.cpp:2583-2589,2629`）。

## 値と既定値

- 未指定時は `Options::seqs = 1` で、単一会話の従来動作です。`--parallel 1` も同じく追加の会話状態を割り当てません（`src/dsv41/ds4_model.hpp:74-76`、`src/dsv41/ds4_model.cu:6961-6964`）。
- 指定値は `std::atoi` で変換され、変換結果が 1 未満または 8 より大きいと `--parallel takes 1 to 8` を stderr に出して終了コード 2 になります（`src/dsv41/ds4_main.cpp:2583-2588`）。数値として厳密に解釈されない文字列の扱いは `atoi` の変換結果に依存します。たとえば非数値は 0 となり範囲外で拒否されます。
- 値が欠けている場合は `--parallel needs a value` を stderr に出し、`exit(2)` します（`src/dsv41/ds4_main.cpp:2513-2518,2583-2584`）。同じ option を複数回指定した場合、parser は各回の値を順に代入し、最後の値が残ります（`src/dsv41/ds4_main.cpp:2511-2518,2583-2584`）。

## 実行時の動作

parser の値は `Options::seqs` に渡り、モデル読み込み中に会話ごとの window ring、圧縮 KV 等の追加 buffer を確保します。会話数分の状態は会話ごとに保持されます（`src/dsv41/ds4_main.cpp:2583-2584`、`src/dsv41/ds4_model.cu:6960-7011`）。

`--serve` で実際の会話数が 2 以上なら、起動時に `READY <context> stop multi=<数>` を stdout に出し、stderr に複数会話 protocol の案内を出します。複数会話モードでは `GEN` に `rid=<id>` が必要で、応答行にはその `rid` が付きます。`STOP <rid>` は対象 request を止め、引数なしの `STOP`、`QUIT`、入力終端は全 request を止めます（`src/dsv41/ds4_main.cpp:513-520,1495-1502,1550-1551` と `:134-145,182-200`）。

空いている会話枠がなければ新しい `GEN` は待ち行列に入ります。会話枠は、prompt 状態をより多く再利用できる idle 枠、空の枠、最後に最も長く使われていない枠の順で割り当てます。複数 request が同時に decode する step は `Model::step_multi` 経由となり、この経路では DSpark draft を行いません（`src/dsv41/ds4_main.cpp:1495-1502,1518-1525,1657-1665`）。

## 適用条件と副作用

- 複数会話用 buffer はモデル読み込み時に GPU 上へ追加確保されます。追加 VRAM の必要量は要求数やモデル構成に依存し、ソースだけから固定値は出せません（`src/dsv41/ds4_model.cu:6973-7011,7050-7055`）。
- 要求数分の確保に失敗すると、確保済みの追加枠を保ち、要求を実際に確保できた数へ減らします。stderr に要求数・確保数・allocation error と縮小案内（`--max-context` または `--reserve-mib`）が出ます。1 枠までしか確保できない場合は追加状態を解放して単一会話へ戻します（`src/dsv41/ds4_model.cu:7013-7049`）。このため `READY` の `multi=` 値や server の実会話数は指定数より小さくなることがあります（`src/dsv41/ds4_main.cpp:516-519,1518-1520`）。
- `--multi-check` と併用すると、`--parallel 2..8` および `--ids` が必須です。条件不足は stderr に `--multi-check needs --parallel 2..8 and --ids` を出し終了コード 2 になります。この経路は会話間の計算結果を比較する検査用です。`--serve` も指定した場合は model load 後に `serve()` が先に呼ばれ、`check_multi()` は実行されません（`src/dsv41/ds4_main.cpp:2590,2609-2611,2629,2668-2669`）。
- `strata-dsv41` の実行ファイル自体は `STRATA_BUILD_DSV41=ON` かつ `STRATA_HIP_GFX906` でない build 条件の CMake target です（`CMakeLists.txt:934-944`）。Release の各 backend での利用可否は別途 build / package 条件によります。

## 出力とエラー

範囲外の値、値の欠落、`--multi-check` の前提不足、未知 option は終了コード 2 です。未知 option は `unknown option <値>` と usage を stderr に出します（`src/dsv41/ds4_main.cpp:2513-2517,2585-2588,2596-2599,2609-2611`）。モデル読み込みが失敗した場合は `maya-ds4: <error>` を stderr に出し終了コード 1 です（`src/dsv41/ds4_main.cpp:2621-2625`）。

正常な `--serve` 起動は `READY` 行などを stdout に、mode の案内を stderr に出します。GPU 不足で会話数を縮小する場合も stderr に理由を出し、縮小後にモデルが読み込めれば server 起動を続けます（`src/dsv41/ds4_main.cpp:516-520,1550-1551`、`src/dsv41/ds4_model.cu:7037-7049`）。

## 根拠

- `src/dsv41/ds4_main.cpp:115-123` — usage 上の値と `--serve` での用途。
- `src/dsv41/ds4_main.cpp:2511-2518,2583-2589` — parser、値変換、範囲検査、欠落値の失敗経路。
- `src/dsv41/ds4_model.hpp:74-76` — `Options::seqs` の既定値と会話状態の説明。
- `src/dsv41/ds4_model.cu:6960-7058` — 会話状態の割当て、VRAM 不足時の縮小、実会話数。
- `src/dsv41/ds4_main.cpp:513-520,1495-1502,1518-1551,1657-1665` — server protocol、会話枠、複数会話 decode。
- `src/dsv41/ds4_main.cpp:2609-2611,2621-2629` — `--multi-check` の条件と起動分岐。
- `CMakeLists.txt:934-944` — DSV41 CLI target の build 条件。

調査範囲はこの checkout のソースです。CLI `--help` の実行や build は行っていません。`atoi` が受理する数値以外を含む文字列の細かな解釈は C ライブラリ実装に委ねられるため、Strata 独自の仕様としては断定していません。
