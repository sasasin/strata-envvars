# `PIPE_INFO`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

Metal の診断用実行ファイル `expert_parity` が、構築した gate/up と down の Metal pipeline の情報を標準出力に追加します。Strata 本体の推論経路を制御する環境変数ではありません。

## 値と判定

値の内容は parse せず、`std::getenv("PIPE_INFO")` が null かどうかだけを判定します。

| 状態 | 動作 |
|---|---|
| 未設定 | pipeline 情報を追加表示しない |
| 設定あり | 値が空文字や `0` を含め、pipeline 情報を追加表示する |

空白、大文字小文字、数値としての妥当性は関係しません。

## 有効になる条件

この参照は `metal/tests/expert_parity.cpp` に一箇所だけあります。Metal 診断プログラムの pipeline 作成処理で評価されるため、Strata の通常実行ファイルや CUDA/HIP/SYCL の実行経路には適用されません。Metal の CMake 設定は `tests/*.cpp` を実行ファイルとして登録しており、このソースもその対象です。

## 実行時の詳細

`make` lambda が gate/up および down pipeline を生成した後に環境変数を確認します。未設定でなければ stdout に `pipelines: gu ... max threads ... tg mem ... | dn ... max threads ... tg mem ...` を出力します。表示するのは両 pipeline の名前、最大 thread 数、静的 threadgroup memory の値です。設定値自体は出力せず、pipeline の選択や計算内容も変更しません。設定は `make` の呼び出しごとに読み直されます。

## 根拠

- `metal/tests/expert_parity.cpp:412-424` — pipeline を作成し、`PIPE_INFO` の設定有無を判定して標準出力へ詳細を出す。
- `metal/tests/expert_parity.cpp:498,650,658,663,665` — `make` lambda の呼び出し箇所。
- `metal/CMakeLists.txt:41-46` — `tests/*.cpp` を実行ファイルとして登録。
- `metal/tests/expert_parity.cpp:1-18` — ファイルが Metal routed-expert parity / speed 診断用であることを示す説明。
