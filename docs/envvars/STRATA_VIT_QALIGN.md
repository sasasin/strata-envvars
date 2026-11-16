# `STRATA_VIT_QALIGN`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

own vision tower の GPU 実装で、通常 attention が一度に処理する query 行数 `QC` を指定値の倍数に切り下げる診断用設定です。CUDA/HIP の `tools/vision/own/vit_gpu.cu` と Metal の `tools/vision/own/vit_metal.mm` が同じ調整を行います。設定はスコア行の padding 幅や画像 token 数を変えず、attention query の chunk 分割に使われます（`vit_gpu.cu:469-472,1076-1079`、`vit_metal.mm:118-121,542-545`）。

この変数を読むのは own tower の GPU reader に限られます。`--gpu` を付けず CPU reader を使う場合、または `--tower mtmd` を使う場合には、これらの読み取り箇所に入りません（`own_reader.cpp:103-138`、`strata_vision.cpp:107-112,161-170`）。

## 値と判定

CUDA/HIP と Metal の両方で `std::getenv` が非 null の場合に `std::atoi` で `int` に変換し、結果が `1` 以上なら `q_align` に保存します。未設定では `q_align=0` のままです。空文字、`0`、`0anything`、負値、先頭が数値でない文字列（例: `true`）は変換結果が 0 となり無効です。`atoi` は文字列全体の妥当性を検査しないため、`8tail` は 8 として受理されます。前後の空白や符号も `atoi` の整数変換に従います。無効値は警告なしで無視されます（`vit_gpu.cu:469,1007`、`vit_metal.mm:118,471`）。

| 実行経路 | unset | 設定時に有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA/HIP own GPU tower、通常 attention | `q_align=0`。画像 patch 数 `N` が 16384 以下なら alignment 1、超えるなら 64 | `atoi` の結果が 1 以上。例: `1`, `8`, `8tail` | 空文字、`0`, `0anything`, `-4`, `true` など `atoi` の結果が 0 以下 |
| Metal own GPU tower | 同上 | 同上 | 同上 |

`q_align` が 1 以上なら、画像サイズにかかわらず自動値（大きな画像の 64 を含む）をその指定値で置き換えます。正の値に power-of-two、上限、patch 数の約数という制約はありません。`std::atoi` が `int` の表現範囲を超える入力に対して安全な範囲検査を行うコードはありません（`vit_gpu.cu:469-472,1007`、`vit_metal.mm:118-121,471`）。

## 有効になる条件

- own tower が GPU reader として選ばれ、GPU reader が `VitGpu::load` を実行すること。`strata-vision` では `--gpu` が必要で、`--tower auto` の場合は backend と mmproj が own reader に対応するときに own が選ばれます（`own_reader.cpp:49-72,114-125`、`strata_vision.cpp:137-170`）。
- CUDA または HIP build では `STRATA_VISION_CUDA` または `STRATA_VISION_HIP` が選ばれ、Metal build では macOS で `STRATA_VISION_METAL` が有効であること（`tools/vision/CMakeLists.txt:20-32,97-108,131-144`）。
- CUDA の通常 attention、または Metal の attention であること。HIP の fused attention `m.fa` が有効な場合は `QC`/`qa` の計算を通らず、`qf` による別の query 分割で実行するため、この変数は fused 経路に作用しません（`vit_gpu.cu:1076-1083,1085-1105`）。
- own CPU tower、mtmd reader、および SYCL GPU reader には、この名前を読む実装がありません。候補名の全参照検索で実際の読み取りは上記 CUDA/HIP と Metal の2箇所だけでした。

## 実行時の詳細

値は `VitGpu::load` の重み読み込み後、初期の GPU work buffer 確保前に読み込まれ、`VitGpuImpl::q_align` に保存されます。そのため、プロセス起動後でも load が始まる前に環境を設定しておけば反映されますが、load 後の環境変更は反映されません。CLI 引数や別の環境変数による上書き処理はありません（`vit_gpu.cu:895-900,1001-1008`、`vit_metal.mm:368-375,466-473`）。

通常 attention ではまずスコア buffer の容量などから `QC` を求めます。`q_align > 1` かつ `QC < N` かつ `QC >= q_align` のときだけ、`QC -= QC % q_align` で `q_align` の倍数以下へ切り下げます。その `QC` ごとに query rows の score 計算、softmax、value 積を行い、最後の chunk は `min(QC, N-q0)` 行です。したがって、`QC >= q_align` でない場合や `QC == N` の場合は切り下げず、端数の最後の chunk も指定倍数とは限りません（`vit_gpu.cu:1074-1079,1105-1117`、`vit_metal.mm:542-567`）。

変数の読み取り自体は score buffer の容量を変更しません。容量不足時の CUDA/HIP・Metal の小さい score chunk への fallback や allocation error は `size_buffers` の別処理であり、この変数専用の fallback ではありません（`vit_gpu.cu:780-827`、`vit_metal.mm:251-280`）。

## ログと測定値

`STRATA_VIT_QALIGN` 固有の有効・無効値ログや測定値出力はありません。値が無効でもこの設定についての警告は出ません。別の reader load／warm-up 失敗は `own_reader.cpp:92-110,121-125,160-165` の起動エラー経路に入り、`--tower auto` の場合は `strata_vision.cpp:168-175` が stderr に `strata-vision: Strata's picture reader did not start (...)` を出して mtmd reader に切り替えますが、これらは `STRATA_VIT_QALIGN` の値を検査した結果ではありません。

## 根拠

- `tools/vision/own/vit_gpu.cu:469-472,1007-1008` — CUDA/HIP の値保存、既定 alignment と padding helper。
- `tools/vision/own/vit_gpu.cu:1074-1117` — query chunk の算出、条件付き切り下げ、通常/fused attention 分岐。
- `tools/vision/own/vit_metal.mm:118-121,471-473,542-567` — Metal の値保存と通常 attention の chunk 処理。
- `tools/vision/own/own_reader.cpp:49-72,103-138`、`tools/vision/strata_vision.cpp:107-112,137-175` — own reader の選択、GPU/CPU 経路、起動失敗時の fallback。
- `tools/vision/CMakeLists.txt:20-32,97-108,131-144` — GPU backend build 条件。
