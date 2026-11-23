# `STRATA_VIT_CPU_VPACK`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

own vision tower の CPU fast 実装 (`VitCpu::encode`) で、attention に使う V を head ごとの連続配列 `VP[h][j][d]` にコピーして使うかを切り替える診断用設定です。通常の未設定時は packed 配列を使います。0 と判定される値を指定するとコピーを省き、元の QKV 行列から strided read します。切り替えるのは V の格納位置と読み出し stride で、attention の加算順は変えない実装です（`tools/vision/own/vit_cpu.cpp:289-297,327-354`）。

この変数を読むのは Strata 同梱の own CPU tower です。`own_reader_run` が CPU fast tower を選び `VitCpu::load` した後に encode する経路で有効です (`tools/vision/own/own_reader.cpp:128-149`)。`--tower mtmd` は別 reader、own tower の GPU 経路は `VitGpu` を使うため、この設定の対象外です (`tools/vision/strata_vision.cpp:161-170`, `tools/vision/own/own_reader.cpp:114-128,143-149`)。

## 値と判定

`VitCpu::encode` 内の関数局所 `static const bool` 初期化子で `std::getenv` を一度呼び、設定があり `std::atoi(e) == 0` の場合だけ packed V を無効にします。未設定なら有効です。空文字は設定済みでも `atoi` が 0 を返すため無効になります。文字列全体の妥当性検査はせず、`atoi` が先頭から変換した整数で判定します（`tools/vision/own/vit_cpu.cpp:292`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| own tower の CPU fast (`VitCpu`) | 有効 | `1`, `-1`, `2`, `1abc` など、`atoi` の結果が 0 以外 | `0`, `00`, `0anything`, `abc`, 空文字、空白だけなど、`atoi` の結果が 0 |

空白や符号は `atoi` の整数変換規則に従い、文字列全体・大文字小文字・真偽値語 (`true` / `false`) の検証はありません。したがって `true` は整数変換が 0 となり無効、`false` も無効です。整数に変換できる前置部分の後ろは判定に使われません (`tools/vision/own/vit_cpu.cpp:292`)。

## 有効になる条件

- own vision tower の CPU fast 実装を使うこと。own reader は CPU 時に、`STRATA_VIT_CPU=ref` の完全一致でない限り `VitCpu` をロードします (`tools/vision/own/own_reader.cpp:128-137`)。
- GPU reader (`o.gpu`) では `VitGpu::encode` に進むため、この CPU 実装の設定は参照されません (`tools/vision/own/own_reader.cpp:114-128,143-149`)。
- mtmd reader を選んだ場合も対象外です。`--tower` の選択は own reader の起動可否に関わりますが、この環境変数自体が tower 選択を上書きするコードはありません (`tools/vision/strata_vision.cpp:94-112,141-170`)。

## 実行時の詳細

設定は `VitCpu::encode` の最初の呼び出しで static 初期化され、同一プロセス内の後続 encode でも同じ値が使われます。起動後に環境を変更しても、初回 encode 後は反映されません。未設定・無効時 (`vpack == false`) は `VP` を要素数 0 で作成し、K 転置を作るループで V をコピーせず、attention の `Vh` を QKV 行列中の V の位置、stride `3 * D` で参照します。有効時は `H * N * HD + slack` 要素を確保し、各 head/token の V を連続配置へコピーして stride `HD` で読みます。どちらも同じ `ops.gemm` の V 積に渡されます (`tools/vision/own/vit_cpu.cpp:292-297,318-329,333-355`)。

ソースコメントはこの配置と query grouping の変更について「各 query row の和の順序」は同じで bit-identical と記しています。`STRATA_VIT_CPU_VPACK` による別の数値処理や CLI 引数上書きはコード上にありません (`tools/vision/own/vit_cpu.cpp:289-292`)。

## ログと測定値

この変数の判定・切り替えを知らせるログやエラー経路はありません。`STRATA_VIT_PROF` による stage 計時ログは別の設定で有効化されますが、VPACK の状態を表示しません (`tools/vision/own/vit_cpu.cpp:204-212,398-401`)。`docs/DETAILS.md` の Images 節は vision reader の選択や公開設定を説明していますが、この変数や V packing の測定値には触れていません (`docs/DETAILS.md:984-1016`)。

## 根拠

- `tools/vision/own/vit_cpu.cpp:289-297` — V packing の用途、値判定、static cache、バッファ確保。
- `tools/vision/own/vit_cpu.cpp:318-355` — V のコピー有無、読み出し配置と attention の積。
- `tools/vision/own/own_reader.cpp:114-149` — GPU と CPU の reader 分岐、`STRATA_VIT_CPU=ref` による CPU 実装選択。
- `tools/vision/strata_vision.cpp:94-112,141-170` — tower 選択と own reader 起動経路。
