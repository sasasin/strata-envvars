# `CHAIN_CTAB`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

この名前を読むコードは `metal/tests/token_chain.cpp` にだけあります。`token_chain` は実モデルの重みを使って Metal の decode dispatch を組み立て、GPU 時間を測るテスト用プログラムです。通常の Strata Metal エンジンが読む設定ではありません。

このテストプログラムでは、routed gate/up の量子化テーブルを Metal function constant 経由で参照する経路と、threadgroup にコピーして使う経路を切り替えます。これは `token_chain` の dispatch 選択だけに作用します。

## 値と判定

値の数値変換や先頭文字判定はせず、環境変数全体が文字列 `"0"` と一致するかを比較します。

| 値 | `ctabf` | `token_chain` の経路 |
|---|---:|---|
| 未設定 | `true` | function constant 23 を有効にする |
| 空文字 | `true` | function constant 23 を有効にする |
| `0` | `false` | threadgroup copy 側を選ぶ |
| その他（例: `1`, `00`, `false`, `0x`） | `true` | function constant 23 を有効にする |

文字列比較なので、大文字小文字や数値形式の解釈はありません。判定は `main()` 内で一度行い `const bool` に保存されます。

## 有効になる条件

`metal/tests/token_chain.cpp` から実行される `token_chain` の routed gate/up dispatch に限られます。`metal/CMakeLists.txt` は `tests/*.cpp` を個別の実行ファイルとして作成しており、`token_chain.cpp` もそのテスト用ターゲットです。`CHAIN_CTAB` を設定しても `strata` エンジンの設定は変わりません。

エンジン側には別の環境変数 `STRATA_METAL_CTAB` を読む `metal_ctab()` があり、同じ function constant 23 を設定します。したがって `CHAIN_CTAB` とエンジンの Metal 実行経路の設定名を混同しないでください。

## 実行時の詳細

`token_chain` は `ctabf` に応じて pipeline cache key に `#ct` を付けるかを決め、`mtl::Constants().b(23, ctabf)` で function constant 23 の値を渡します。Metal kernel 側ではこの値が真のとき量子化 grid と sign table を constant 配列から読み、偽のとき threadgroup copy 側を使います。ソースコメントは両経路が同じ値を使うと説明しています。

この環境変数自体についてのログ出力、プロセス起動後の再読み込み、子プロセスへの転送は確認できません。`token_chain` の実行結果や性能差はこの調査では測定していません。

## 根拠

- `metal/tests/token_chain.cpp:1-8,59-82`: プログラムの用途と `main()`。実重みを使う Metal dispatch の計測用であり、環境判定は `main()` の中で行われる。
- `metal/tests/token_chain.cpp:186-188,579-590`: `CHAIN_CTAB` の完全一致判定と、routed gate/up pipeline key・function constant 23 への反映。
- `metal/kernels/quant.metal:72-84,348-404`: function constant 23 の宣言、constant table を使う helper、および threadgroup table loader の分岐。
- `metal/CMakeLists.txt:1-9,41-47`: `tests/*.cpp` を個別実行ファイルにする構成。
- `metal/src/engine/window.cpp:68-76,970-978`: エンジン側の別名 `STRATA_METAL_CTAB` を読む処理と、その値を function constant 23 に渡す箇所。
