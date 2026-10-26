# `DS4_QUANT_SINGLE`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek V4.1 GGUF エンジンの一部 GEMV 処理で、複数 job の activation を int8 に丸める GPU kernel の起動方法を切り替えます。未設定なら複数 job をまとめた kernel を1回起動し、設定されていれば job ごとに単独 kernel を起動します。量子化の計算式と出力先は同じです。

## 値と判定

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | まとめた `q8_quant_multi_kernel` を起動 |
| 設定あり | 各項目について `q8_quant` を呼び、項目数分の kernel を起動 |

`std::getenv(...) != nullptr` だけを判定するため、値の文字列は解釈しません。`1`、`0`、任意の文字列、空文字のいずれも設定ありとして単独起動になります。数値変換、大小比較、無効値時の fallback はありません。

## 有効になる条件

- `strata-dsv41` のビルドに含まれる DeepSeek V4.1 エンジンが必要です。CMake では `STRATA_BUILD_DSV41` が有効で、`STRATA_HIP_GFX906` ではない場合にこの実行ファイルと `src/dsv41/ds4_gguf.cu` がビルド対象になります。機能は既定でビルド対象外です。
- `mv()` が、低ビット GGUF (`kFmtGG`) または Q8_0 (`kFmtQ8_0`) の job を処理し、量子化キューが空でない場合に限り効果があります。BF16、MXFP4 の job だけの場合はキューが空のままなので、変数は参照されません。
- `quant_flush()` に到達する前にエラーで戻る経路や、キューが空の呼び出しでは判定しません。

## 実行時の詳細

`mv()` は対象 job ごとに `quant_add()` で入力 pointer、stride、row 数、幅、および出力 scratch 領域をキューに記録し、同一入力の重複は通常まとめて共有します。`quant_flush()` はキュー数が0なら戻ります。キューがあると、未設定の既定経路では最大幅・最大 row 数で3次元 grid を作り、`blockIdx.z` で項目を選ぶ `q8_quant_multi_kernel` を1回起動します。設定時は各 item に `q8_quant` を呼び、item ごとの grid で起動します。いずれも同じ stream に投入されます。

両 kernel は各 row の32個単位で `max(abs(x)) / 127` を scale とし、値を scale で割って最近接偶数丸め (`__float2int_rn`) した int8 値を書き込みます。multi kernel のコメントは、単独 kernel と同じ演算で、出力 bytes も一致すると説明しています。したがって、このスイッチの実装上の違いは起動のまとめ方です。速度差の測定値は確認できませんでした。

判定結果は `quant_flush()` 内の `static const bool` に保存されます。最初の非空キュー処理で一度評価され、その後プロセス内で環境変数を変更しても再判定されません。ログ出力はありません。

## 根拠

- `CMakeLists.txt:797-811` — DeepSeek V4.1 エンジンの任意ビルド条件と実行ファイルへの GPU ソース登録。
- `src/dsv41/ds4_gguf.cu:186-202` — 単独量子化 kernel と grid 起動。
- `src/dsv41/ds4_gguf.cu:204-229` — 複数 item 用 kernel と同一演算である旨の実装コメント。
- `src/dsv41/ds4_gguf.cu:231-258` — キュー、環境変数判定、単独起動とまとめ起動の分岐。
- `src/dsv41/ds4_gguf.cu:1129-1207` — GEMV job の分類、低ビット GGUF/Q8_0 での量子化キュー登録と flush。
- `docs/DETAILS.md` に `DS4_QUANT_SINGLE` の設定説明または性能測定値は見当たりませんでした。
