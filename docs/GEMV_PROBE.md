# `GEMV_PROBE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

この名前は通常の Strata 実行ファイルの環境設定ではなく、Metal の GEMV ベンチマーク `metal/tests/gemv_parity.cpp` が `gemv.metal` に渡す関数定数を選ぶためのテスト用フックです。調査対象内でこの環境変数を読むのはベンチマークコードだけです。`metal/kernels/gemv.metal` は環境変数を読まず、ベンチマークから渡された関数定数に応じて GEMV の計算経路を変えます。

## 値と判定

ベンチマークは `getenv("GEMV_PROBE")` が null なら関数定数 9 に `0` を渡し、設定されていれば `atoi` の結果を渡します。文字列全体の検証はありません。`atoi` の規則により、先頭空白と符号に続く数値接頭部が変換され、数値接頭部のない値（空文字を含む）は `0` になります。たとえば `2tail` は `2`、`-3` は `-3`、`junk` は `0` です。

| 変換値 | ベンチマーク GEMV kernel の挙動 |
|---|---|
| `0`（未設定時の既定値を含む） | 基準経路。通常どおり各 token の入力を読み、積和を行う |
| `1` | 2 token 目以降で入力ベクトルを再ロードせず、token 0 で読んだ値を使う。kernel コメントは誤った値になると明記 |
| `2` | 2 token 目以降で積和を行わない。kernel コメントは誤った値になると明記 |
| `3` | row を外側、token を内側に回す別ループ順で計算する |
| その他 | kernel 内の `1`, `2`, `3` の条件に一致せず、基準経路を使う |

## 有効になる条件

`metal/tests/gemv_parity.cpp` の通常の parity 経路や `--gguf` 経路では関数定数 9 を渡さないため、この環境変数はそれらの経路に反映されません。環境変数を読むのは、ベンチマーク経路で各設定の pipeline を作る箇所です。`--one` は `bench = true` にするため対象です。値は CLI 引数ではなく `getenv` から取得され、ほかの Strata 設定との優先順位はありません。

## 実行時の詳細

ベンチマーク経路では候補 tile ごとに pipeline を作るときに環境変数を読み、`Constants().i(9, ...)` で Metal の function constant index 9 に値を渡します。読み取り結果は C++ 側で static cache されず、pipeline 作成のたびに評価されます。Metal kernel では未定義の関数定数を 0 として扱い、値 1 と 2 は token 0 以外の計算を意図的に崩すため、正確性確認用の設定ではなくベンチマーク用プローブです。値 3 は行と token のループ順を切り替えます。

## 根拠

- `metal/tests/gemv_parity.cpp:1-6,75-100,164-188,243-245,287-303`: このファイルが parity とベンチマーク経路を持ち、環境変数を読む pipeline 作成がベンチマーク側にあること。
- `metal/tests/gemv_parity.cpp:302`: unset 時の `0`、設定時の `atoi`、index 9 への値の注入。
- `metal/kernels/gemv.metal:18-22`: index 9 の function constant と、未定義時の 0。
- `metal/kernels/gemv.metal:46-69`: 値 3 の別ループ順、値 1/2 の分岐、および誤った値になるというコードコメント。

この結果は、指定された調査境界で本番コードが `GEMV_PROBE` を読む実装を確認できず、テスト用コードのみで使われることを示します。ベンチマークや Metal 実行は行っていません。
