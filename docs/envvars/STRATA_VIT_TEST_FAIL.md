# `STRATA_VIT_TEST_FAIL`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`strata-vision` の独自 vision tower（own tower）が起動時に通る GPU 準備・encoder load・GPU warm-up の地点で、指定地点の失敗を意図的に起こすテスト用 hook である。環境値を `own_reader_inject_failure()` が地点名と完全一致で照合し、合致した分岐は実際の GPU 不在・load 失敗・warm-up の GPU メモリ不足に似た起動失敗を返す。画像処理の選択・計算・出力を設定する変数ではない。読取関数は `tools/vision/own/own_reader.cpp:44-47`、注入箇所は同 `:116-125`, `:128-138`, `:150-165`。

この hook は `own_reader.cpp` が含まれる `strata_vit_own` に実装され、`strata-vision` と `strata-vision-own` の両方が同ライブラリをリンクする（`tools/vision/CMakeLists.txt:124-129,166-168`; `tools/vision/own/CMakeLists.txt:74-77,168-171`）。ただし `strata-vision` でも own reader を起動しない場合は参照されない。

## 値と判定

`std::getenv` で取得した値全体を `std::string` にして、呼出側が渡す地点名 (`gpu`, `load`, `warmup`) と大文字小文字を区別して完全一致比較する。数値変換、trim、部分一致はない（`tools/vision/own/own_reader.cpp:44-47`）。未設定は不一致、空文字も不一致。たとえば `load` だけが load 地点で一致し、`LOAD`、`load `、`1`、`true`、`0anything` はどの地点にも一致しない。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| own reader の GPU build で `--gpu` を指定 | 注入なし | `gpu`、`load`、`warmup`（到達した地点に限る） | 空文字、`1`、`true`、別地点名、大小文字違い、余分な文字 |
| CPU 経路（GPU build かどうかを問わず `--gpu` なし） | 注入なし | `load` | 空文字、`gpu`、`warmup`、その他 |
| GPU backend なしの build で `--gpu` を指定 | 注入なし。この build の GPU 不可エラーが先に返る | なし | すべて |

`gpu` と `warmup` の呼出しは `STRATA_VIT_GPU` 定義下にあり、`load` は GPU 経路では GPU load 成功後、CPU 経路では CPU tower load 成功後に照合する（`tools/vision/own/own_reader.cpp:103-110,114-138,150-165`）。このため、mmproj の読み込み・geometry 検証が先に失敗した場合や、GPU load が自然に失敗した場合は後続地点の注入判定に到達しない。

## 有効になる条件

- own reader が起動すること。`strata-vision` では `--tower mtmd` のときは使われず、`auto` が own を選んだ場合か、`--tower own` の場合に実行される。`auto` は mmproj/backend 対応状況で reader を選び、対応しないと mtmd を選ぶ（`tools/vision/strata_vision.cpp:137-144,161-170`）。
- `gpu` は `STRATA_VIT_GPU` 付き build かつ `--gpu` の場合のみ判定される。GPU backend を含まない build で `--gpu` を指定したときは、注入 hook より前に GPU 非対応エラーとなる（`tools/vision/own/own_reader.cpp:103-105,114-119`）。
- `warmup` は GPU 経路で GPU load 成功後の起動時 warm-up に限る。CPU 経路には warm-up 分岐がない（同 `:150-165`）。
- `load` は own tower の初期 load が成功してその直後まで進んだときに有効。CPU では `STRATA_VIT_CPU=ref` の有無にかかわらず選択済み tower の load 後、GPU では `VitGpu::load` 後に判定する（同 `:123-138`）。
- own reader が起動時に失敗した場合の fallback は `strata-vision` の `auto` 選択かつ model 指定がある場合に限る。`--tower own` や own-only `strata-vision-own` では fallback せず、失敗を返す（`tools/vision/strata_vision.cpp:138-143,161-175`; `tools/vision/own/own_main.cpp:31-41`）。

## 実行時の詳細

変数は起動時に一括 parse/cache されない。`own_reader_inject_failure(point)` が呼ばれるたびに `getenv` を行い、その時点での値を地点名と比較する。コード内にこの変数を変更する処理や子プロセスへ値を渡す処理はない。地点チェックは reader の起動処理中だけで、`READY` 後の各画像リクエストでは呼ばれない（`tools/vision/own/own_reader.cpp:44-47,89-110,116-165,168-194`）。

- `gpu`: GPU 実利用可能性を調べる前に失敗扱いにし、メッセージ `this picture reader found no GPU (injected for a test: STRATA_VIT_TEST_FAIL)`、終了コード `3` を作る（同 `:116-120`）。
- `load`: GPU または CPU の tower load 成功後に失敗扱いにし、`cannot load the vision encoder <mmproj> (injected for a test: STRATA_VIT_TEST_FAIL)`、終了コード `1` を作る（同 `:123-138`）。GPU load 後の注入では確保済みメモリは return 時に解放される（同 `:125`）。
- `warmup`: 2048×2048 の warm-up 画像を準備する前に `out of GPU memory (injected for a test: STRATA_VIT_TEST_FAIL)` をエラー文字列へ設定し、warm-up 失敗として終了コード `1` を作る（同 `:150-165`）。
- 失敗時、`start_error` が渡されていれば `own_reader_run` は stdout に書かず `kOwnStartFailed` を返す。通常の `strata-vision --tower auto` で own tower 起動後に失敗すると、stderr に `strata-vision: Strata's picture reader did not start (<理由>); reading pictures with llama.cpp's reader` を出し、mtmd reader を起動する。`start_error` がない明示的 own 経路では stdout に `ERR <理由>` を出して該当コードを返す（同 `:92-100`; `tools/vision/strata_vision.cpp:168-175`）。

## 根拠

- 環境読み取りと完全一致判定: `tools/vision/own/own_reader.cpp:44-47`
- 各注入地点、条件、失敗文言・コード: `tools/vision/own/own_reader.cpp:103-105,114-138,150-165`
- `auto` による own 選択、失敗時 fallback、明示経路の処理: `tools/vision/strata_vision.cpp:137-175`
- 実行ファイルと共有ライブラリの構成: `tools/vision/CMakeLists.txt:124-129,166-168`; `tools/vision/own/CMakeLists.txt:74-77,168-171`
