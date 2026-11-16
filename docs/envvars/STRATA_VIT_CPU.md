# `STRATA_VIT_CPU`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`strata-vision` の own vision tower（`--tower own` または `auto` が own を選んだ場合）を CPU で実行するとき、CPU 実装を選ぶ。未設定時の通常経路は `VitCpu`、値を厳密に `ref` としたときは float32 の参照実装 `VitRef` になる。これは画像 encoder の計算実装の選択であり、どの tower を使うかを決める `--tower` / `STRATA_VISION_TOWER` とは別段階である。実際の読み取りと分岐は `tools/vision/own/own_reader.cpp:128-149`、reader のビルド登録は `tools/vision/own/CMakeLists.txt:74-77` にある。

## 値と判定

`own_reader_run` が CPU 経路に入るたびに `std::getenv` で値を読み、文字列全体を大文字小文字を区別して `ref` と比較する。数値変換や trim はしない。したがって `ref` だけが参照実装を選び、それ以外はすべて高速 CPU 実装 `VitCpu` を選ぶ（`tools/vision/own/own_reader.cpp:128-138`）。

| 実行条件 | unset | `VitRef` を選ぶ値 | `VitCpu` を選ぶ値 |
|---|---|---|---|
| own tower の CPU 経路 | `VitCpu` | 完全一致する `ref` | 空文字、`REF`、`Ref`、`fast`、`0`、`1`、`true`、` ref`、`ref `、`ref-extra` など、`ref` 以外すべて |
| own tower の GPU 経路（`--gpu`） | 選択判定をしない | 該当なし | 該当なし |
| `mtmd` tower | 選択判定をしない | 該当なし | 該当なし |

## 有効になる条件

- 実行ファイルが own tower を含み、reader が `own_reader_run` を呼ぶこと。`strata-vision` では `--tower own` が明示されるか、`--tower auto` が own を選んだ場合に呼ばれる。`--tower auto` の own 選択条件はモデル投影ファイルが指定され、`own_reader_supported` が現在の backend に対応すると判定すること（`tools/vision/strata_vision.cpp:137-145,161-170`、`tools/vision/own/own_reader.cpp:49-73,84-87`）。
- tower 選択では明示的な `--tower` が `STRATA_VISION_TOWER` の既定値より優先する。`--tower mtmd` を選ぶと `STRATA_VIT_CPU` の判定には到達しない（`tools/vision/strata_vision.cpp:94-113,137-170`）。
- `--gpu` を指定した own tower は GPU の実装を使い、CPU 選択分岐を通らないため、この変数は無視される。GPU backend がビルドにない場合は `--gpu` 起動が `this build has no GPU backend for the own tower (use --tower mtmd)` で失敗する（`tools/vision/own/own_reader.cpp:103-105,114-128`）。GPU backend の有無は `STRATA_VIT_GPU` ビルド分岐である（同 `:7-9,103-105,114-127`）。
- `strata-vision-own` も同じ `own_reader_run` を呼ぶため、この変数による CPU 実装選択を行う（`tools/vision/own/own_main.cpp:13-41`）。同ツールは `--tower` 引数を受け取って値を読み捨てるが、reader 自体を直接起動する（同 `:27-28,41`）。
- `--threads` は選択の優先順位を変えず、CPU 実装を選んだ後の thread 数を指定する。未指定または 0 以下の場合は hardware concurrency の半分を 1〜16 に収めた値になる（`tools/vision/own/own_reader.cpp:128-140`）。

## 実行時の詳細

`own_reader_run` はまず投影 GGUF と geometry を開いて検証する。その後、`o.gpu` が false のときだけ `STRATA_VIT_CPU` を読み、`ref` なら `VitRef`、それ以外なら `VitCpu` を生成してロードする。選択した実装を reader プロセス内で保持し、後続の `ENC` 要求に使う（`tools/vision/own/own_reader.cpp:106-149,171-194`）。値は static cache ではなく reader 起動時に一度読む。プロセス起動後に環境が変わっても、すでに選択された実装は切り替わらない。

投影 GGUF / geometry の検証または選択実装の load が失敗すると `cannot load the vision encoder ...` になり、明示 `--tower own` では stdout に `ERR ...` を出して終了コード `1` を返す。自動 tower 選択から own reader を起動し、まだ `READY` を返す前に失敗した場合は own reader が `kOwnStartFailed`（`100`）を返し、`strata-vision` が stderr に `strata-vision: Strata's picture reader did not start (%s); reading pictures with llama.cpp's reader` を出して mtmd reader に切り替える。GPU backend がない build で `--gpu` を使う場合は同じ fail 経路で終了コード `3` になる（`tools/vision/own/own_reader.cpp:92-110,114-138`、`tools/vision/own/own_reader.h:29-30`、`tools/vision/strata_vision.cpp:161-175`）。

同梱診断スクリプトでは、`gate_gpu.py` が CPU 参照 reader の子プロセスに `STRATA_VIT_CPU=ref` を上書きして渡す（`tools/vision/own/gate_gpu.py:80-94,169-177`）。`speed_pairs.py` は子プロセス環境を親から複製し、`--env-a` の既定値 `STRATA_VIT_CPU=fast` を上書き設定する（`tools/vision/own/speed_pairs.py:16-27,39-55`）。これらは親プロセス自体の環境値を変更せず、起動した reader がその値を一度読み取る。

## ログと測定値

選択した実装の種類（`VitCpu` / `VitRef`）を明示するログはない。own tower の CPU reader 起動時には共通して `strata-vision: own tower (%s, %d layers, width %d) loaded in %.1f s, %s` を stderr に出し、成功後は stdout に `READY %d own` を出す（`tools/vision/own/own_reader.cpp:141-142,168-169`）。各 `ENC` 要求は成功時に `OK %d %d %d %.0f`、画像読み込み・前処理・encode・出力ファイル失敗時に対応する `ERR ...` 行を stdout に出す（同 `:176-203`）。`STRATA_VIT_CPU` の選択肢間の性能値は、参照した `docs/DETAILS.md` および該当する Strata 資料に条件付きの測定値を確認できなかったため記載しない。

## 根拠

- `tools/vision/own/own_reader.cpp:128-149` — CPU/GPU 分岐、完全一致判定、実装生成、選択後の encode 経路。
- `tools/vision/own/own_reader.cpp:92-105,168-205` — 起動失敗の返し方、READY 後の要求処理と出力。
- `tools/vision/strata_vision.cpp:94-113,137-175` — `--tower` と `STRATA_VISION_TOWER` の優先関係、auto 選択と fallback。
- `tools/vision/own/own_reader.h:14-22,43-47` — reader 引数、auto 起動失敗の契約。
- `tools/vision/own/own_main.cpp:13-41` — standalone reader が共通 reader を呼ぶ経路。
- `tools/vision/own/gate_gpu.py:80-94,169-177`、`tools/vision/own/speed_pairs.py:16-27,39-55` — 診断用子プロセス環境への明示設定。
- `tools/vision/own/CMakeLists.txt:74-77` — `own_reader.cpp`、`vit_ref.cpp`、`vit_cpu.cpp` を own tower library に含める。
