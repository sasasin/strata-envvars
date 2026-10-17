# `QSA_ATTN`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`QSA_ATTN` は Strata 本体の環境設定ではなく、Metal 開発用の検証・計測プログラムで QSA attention カーネルの版を選ぶテスト用フックです。確認できた参照は `metal/tests/qsa_parity.cpp` と `metal/tests/token_chain.cpp` のみです。製品実行ファイル側にこの変数を読むコードは見つかりませんでした。

## 値と判定

両プログラムとも、`getenv("QSA_ATTN")` が null なら `1`、設定されていれば `std::atoi()` の結果を使います。文字列全体の妥当性確認はなく、`atoi` が数値として読めない値（空文字を含む）は `0` になります。数値の後ろにある文字も変換結果の判定には使われません。

| 判定後の値 | 選択される attention | merge |
|---|---|---|
| `1` | `qsa_attn` | `qsa_merge` |
| `2` | `qsa_attn2` | `qsa_merge2` |
| その他（unset の既定値 `1` を除く） | `qsa_attn3` | `qsa_merge` |

したがって `QSA_ATTN=0`、空文字、数値として読めない文字列は版3を選びます。`2junk` のように先頭部分が数値として読める文字列は版2です。コードコメントは `qsa_parity.cpp` で「default 3」と記載していますが、実際の未設定時の式は `1` なので、動作はコードに従い版1です。

## 有効になる条件

この変数が使われるのは Metal のテスト/ベンチマーク実行時だけです。`metal/CMakeLists.txt` は `metal/tests/*.cpp` を `mtl_rt` にリンクする実行ファイルとして列挙しており、`qsa_parity` と `token_chain` はそのテストソースです。Metal の Strata エンジン本体には同名の読み取り箇所がありません。

## 実行時の詳細

各プログラムの `main()` 冒頭で値を一度読み、そこで選んだ pipeline を後続の dispatch に設定します。`qsa_parity` は合成入力による段階別 parity 確認とカーネル計測を行います。`token_chain` は GGUF の重みを使った Metal decode 計測ハーネスで、選択した attention pipeline を QSA dispatch に使い、版2の場合は dispatch grid も版2用に切り替えます。環境変数を後から変更して再評価するコードはありません。

## 根拠

- `metal/tests/qsa_parity.cpp:30-47,117-132` — 読み取り、未設定時の値、attention/merge pipeline の選択、dispatch。
- `metal/tests/token_chain.cpp:59-70,243-249,474-491` — 読み取り、pipeline の選択、版2用 grid、decode 計測内での使用。
- `metal/CMakeLists.txt:32-47` — Metal kernel 用 parity/bench プログラムを `metal/tests/*.cpp` からビルドする構成。
- `rg -n 'QSA_ATTN'` によるリポジトリ全体の参照確認では、上記2つのテストソース以外に環境変数の読み取りはありませんでした。
