# `CHAIN_ALBE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

Metal の `token_chain` ベンチマークで、GDN 層の `ssm_alpha` と `ssm_beta` の GEMV を1回の `gemv_cat` dispatch にまとめるかを切り替えます。Strata の Metal エンジン本体からこの変数を読む箇所はなく、通常の生成処理を切り替える設定ではありません。

## 値と判定

`token_chain` の `main()` 内で `std::getenv("CHAIN_ALBE") != nullptr` と判定します。値の文字列や内容は parse しません。

| 状態 | `albe` | 動作 |
|---|---:|---|
| 未設定 | `false` | `ssm_alpha` と `ssm_beta` を別々の `gemv2` dispatch にする |
| 設定あり（空文字を含む） | `true` | 2つの重みを1つの `gemv_cat` dispatch に渡す |

数値、先頭文字、大文字小文字の検査はありません。`CHAIN_ALBE=0` も、空文字や任意の文字列も有効側です。

## 有効になる条件

この分岐は `metal/tests/token_chain.cpp` のベンチマーク実行時に限られます。`metal/CMakeLists.txt` は macOS 専用プロジェクトで、`tests/*.cpp` から実行ファイルを作るため、対象ターゲットは `token_chain` です。Strata の通常の Metal エンジンでは `ssm_alpha` と `ssm_beta` を別々に dispatch しており、`CHAIN_ALBE` を参照しません。

## 実行時の詳細

変数は `token_chain` 起動後、引数処理と GGUF/Metal context の初期化を経て、dispatch 列を組み立てる際に一度読みます。各層のうち `l % 4 != 3` の GDN 層で、未設定なら `ssm_alpha.weight` と `ssm_beta.weight` を別々に `gemv2` へ渡します。設定ありなら両方のテンソルを取得し、`gemvc_<型>_32_1_4` pipeline を選んで1 dispatch を組み立て、出力先 `al` / `be` に渡します。どちらも後続の GDN step に同じ2つの出力バッファを使います。

ベンチマークは最後に dispatch 数、重みと state のバイト数、decode step の GPU 時間などを表示します。変数の値そのものを示すログはありません。実機での速度差はこの調査では測定していません。

## 根拠

- `metal/tests/token_chain.cpp:1-4,59-68` はこのプログラムを実モデル重みを使った decode step の timing と説明し、数値チェックではないとしています。
- `metal/tests/token_chain.cpp:180-184` で `CHAIN_ALBE` を設定有無だけで判定しています。
- `metal/tests/token_chain.cpp:395-424` で GDN 層ごとの fused / unfused dispatch を組み立てます。
- `metal/tests/token_chain.cpp:644-659` で dispatch 集計と GPU timing を表示します。
- `metal/CMakeLists.txt:1-2,32-47` は Metal プロジェクトを macOS 専用とし、`tests/*.cpp` から個別 executable を作ります。
- `metal/src/engine/window.cpp:693-695` は通常の Metal engine の対応箇所で、alpha と beta を個別の GEMV に追加しています。
