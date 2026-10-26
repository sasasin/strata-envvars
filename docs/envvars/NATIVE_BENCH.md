# `NATIVE_BENCH`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL版の単体診断プログラム `native_expert_parity` で、通常の比較処理に加えて GPU の `native_expert_grouped` を複数 expert・entry の構成で反復実行し、1 layer 呼び出し当たりの時間と expert bytes 換算の帯域を出力します。通常の Strata エンジンの設定ではありません。

## 値と判定

値の parse はありません。`std::getenv("NATIVE_BENCH") != nullptr` だけを判定するため、未設定なら追加計測を行わず、設定されていれば値が空文字、`0`、`false` などでも追加計測を行います。大文字小文字や数値としての妥当性も検査しません。

## 有効になる条件

- `sycl/src/kernels/native_expert_parity.cpp` にある SYCL 版のプログラムが実行され、その layer が expert tensor と対応形式の検査を通って GPU 比較処理まで到達する必要があります。tensor 不在または native format 不対応で `continue` した layer では、この変数は読み取られません。
- SYCL の CMake 構成では `STRATA_NATIVE_EXPERTS` が有効なときに `native_expert_parity` ターゲットを作ります。
- CUDA/CPU側の `src/kernels/native_expert_parity.cpp` にこの変数の読み取りはなく、通常の `strata` エンジンや他の実行経路でも参照されません。ソース全体の完全一致検索では読み取り箇所はSYCL版の1箇所です。

## 実行時の詳細

各対象 layer で通常の grouped GPU 比較を完了し、その結果を host にコピーした後に環境変数を確認します。有効な場合、同じ expert blob を GPU 上の異なる10個の領域に複製し、各 expert に4 entry、合計40 entry を割り当てます。entry の token index は3-token入力を繰り返し参照します。計測前に一度実行して queue を待ち、その後20回 `native_expert_grouped` を実行してから再度待ち、経過時間を20で割ります。

stdout には `GPU grouped: 10 experts x 4 entries: ... ms per layer call (... GB/s of expert bytes)` の形式で、layerごとの時間と、10個分の blob byte 数をその時間で割った値を出力します。計測後に追加確保した device memory を解放します。この分岐は通常の比較結果や合否判定を書き換えるものではありませんが、プログラム内で追加のGPU計算とメモリ確保を行います。

環境変数は対象 layer ごとの計測分岐で都度 `getenv` されます。コード内に値を static cache する処理や環境変数を書き換える処理はありません。

## 文書との照合

`docs/A770_SPEED_SPEC.md` はこの変数を使う `native_expert_parity` の測定を、実 GGUF 行の10 experts × 4 entries のGPU grouped計測として説明しています。文書に記載された時間はその資料の Coder IQ1_M / A770 条件での結果であり、ここでは別環境へ一般化しません。

## 根拠

- 読み取り、分岐、10 experts × 4 entries、20反復、出力、後片付け: `sycl/src/kernels/native_expert_parity.cpp:219-289`
- layerの入力検査と、未対応時に分岐を飛ばす処理: `sycl/src/kernels/native_expert_parity.cpp:49-60`
- SYCLビルドにおけるターゲット条件: `sycl/CMakeLists.txt:421-426`
- CUDA/CPU版の単体プログラムが別実装であること: `src/kernels/native_expert_parity.cpp:1-7`
- 記載された測定条件: `docs/A770_SPEED_SPEC.md:630-640`
