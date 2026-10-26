# `GEMV_PROBE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal の `gemv_parity` ベンチマークで、GEMV kernel の計算経路を切り替えて測定する診断用フックです。`strata` の通常の Metal 推論エンジンが環境変数 `GEMV_PROBE` を読む実装は見つかりませんでした。環境変数を読むのは `metal/tests/gemv_parity.cpp` のベンチマーク部分です。

## 値と判定

`gemv_parity` は環境変数が未設定なら function constant 9 に `0` を渡し、設定されていれば `std::atoi()` の結果を渡します。`atoi` は文字列全体の妥当性を検証しないため、数値の先頭部分を整数として読みます。空文字や整数に変換できない文字列は `0` になります。たとえば `2tail` は `2`、`false` は `0` として扱われます。設定の有無だけでは有効化されません。

| 渡される整数 | GEMV kernel の動作 |
|---|---|
| `0` または `1, 2, 3` 以外 | 通常の unit 外側ループを使う。未設定時の既定もこれ。 |
| `1` | 最初の token 以降で activation (`x`) の load を省略し、前 token の値を使う。shader コメントは誤った値になると明記。 |
| `2` | 最初の token 以降で積和への加算を省略する。shader コメントは誤った値になると明記。 |
| `3` | row を外側、token を内側にした別ループで計算する。各 row の unit を decode した後、token ごとに activation を読み込む。 |

function constant 自体の既定値も、呼び出し側が constant 9 を指定しない場合は `0` です。`atoi` のため、先頭の空白や符号を含む整数表記も変換対象になります。大文字小文字の比較は行いません。

根拠: `metal/tests/gemv_parity.cpp:302`, `metal/kernels/gemv.metal:18-22,46-69`。

## 有効になる条件

- macOS の Metal 用テスト／ベンチマーク `gemv_parity` のベンチマーク処理で参照されます。`--one` はベンチマーク経路を選択します。通常の parity 経路は `--bench` がなければ先に実行して戻るため、この環境変数を読みません。また `--gguf` の parity 経路もベンチマーク部分より前に戻ります。根拠: `metal/tests/gemv_parity.cpp:75-97,102-163,164-241,243-303`。
- Metal のテスト実行ファイルは `metal/CMakeLists.txt` が `metal/tests/*.cpp` から作成します。根拠: `metal/CMakeLists.txt:41-47`。
- 製品の Metal engine は GEMV pipeline 作成時に function constant 0（token 数）だけを指定し、constant 9 は指定しません。shader 側では未指定 constant 9 を `0` にします。そのため `GEMV_PROBE` はこの engine 経路に影響しません。根拠: `metal/src/engine/window.cpp:152-158,675-683`; `metal/kernels/gemv.metal:18-22`。

## 実行時の詳細

ベンチマーク部は `GEMV_PROBE` を整数化し、Metal pipeline 作成時に function constant index 9 として渡します。shader は値 `1` と `2` で token 0 以降の処理を意図的に省略し、値 `3` では GEMV のループ順を変更します。値 `1` と `2` は正しい出力との比較を目的とする設定ではなく、誤答を許容した測定用です。値 `3` は別のループ構成を測るものですが、ソースにはこの設定での性能・精度保証は記載されていません。

ベンチマーク経路では各 tile を warm-up した後に5回測定し、中央値を計算して結果を表示します。環境変数はその pipeline を組み立てるたびに `getenv()` で参照されます。実行中に値を書き換えた場合の反映は、ベンチマークコードに再評価・変更処理がないため、確認できません。根拠: `metal/tests/gemv_parity.cpp:287-325`。

## 根拠

- `metal/tests/gemv_parity.cpp:1-6,75-97,164-241,243-325` — parity／bench の分岐、`GEMV_PROBE` の読み取りと pipeline への設定、測定処理。
- `metal/kernels/gemv.metal:18-22,46-69` — function constant 9 の既定値と probe 分岐、値1・2が誤った値を作る処理。
- `metal/CMakeLists.txt:41-47` — Metal test source から各テスト executable を作る設定。
- `metal/src/engine/window.cpp:152-158,675-683` — 製品 engine の pipeline cache と GEMV pipeline 作成。constant 9 は渡していない。
