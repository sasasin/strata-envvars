# `STRATA_VIT_FA_UNITS`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

HIP 版の Strata 独自 Vision tower で fused attention が有効な場合に、attention kernel 1 launch あたりで処理する query × key × head の組数の上限を決める。値は `VitGpu::load` でモデルをロードするときに `fa_units` に設定され、`VitGpu::encode` が画像 token 数に応じた query chunk 幅を計算するために使う。CPU、CUDA、SYCL、Metal の attention 経路には適用されない（`tools/vision/own/vit_gpu.cu:624-640,895-955`; backend ごとのソース選択は `tools/vision/own/CMakeLists.txt:120-163`）。

## 値と判定

HIP build の `VitGpu::load` だけが `std::getenv` で読み、設定されている場合 `std::atoll` で `long long` に変換する。変換値が `1LL << 20`（1,048,576）以上の場合だけ採用し、それ未満なら既定値の `1LL << 29`（536,870,912）のままにする。未設定も既定値。空文字、数値で始まらない文字列、`0`、`1`、負数は `atoll` の結果が下限未満なので採用されない（`tools/vision/own/vit_gpu.cu:631-637,945-955`）。

`atoll` は文字列全体の厳密な数値検証ではなく、10進数の先頭部分を変換する。したがって先頭空白や符号の後に下限以上の数値があれば受理され、数値の後ろの文字は無視される。例えば `1048576`, `+1048576`, ` 1048576`, `1048576junk` は採用される一方、`1048575`, `-1048576`, `true`, `false`, 空文字は採用されない。大文字小文字や真偽値の文字列としての解釈はない。上限 clamp や変換エラーの個別処理もなく、`atoll` の結果だけを下限比較する（同:954）。

| 条件 | unset | 設定時に採用される値（例） | 下限判定で不採用となる値（例） |
|---|---|---|---|
| HIP build で `VitGpu::load` を実行 | `536870912` | 変換結果が `1048576` 以上。例: `1048576`, `1048576junk` | 変換結果が `1048576` 未満。例: 空文字, `0`, `1`, `1048575`, `-1048576`, `true` |
| HIP 以外の build / GPU 以外の経路 | この変数を読まない | 該当なし | 該当なし |

## 有効になる条件

- HIP backend を含む `strata-vision-hip`（または同じ HIP 構成の own-reader 実行ファイル）で GPU reader を使う必要がある。HIP build では `vit_gpu.cu` を HIP 言語としてビルドし `STRATA_VIT_HIP` を定義する（`tools/vision/own/CMakeLists.txt:127-131`）。
- Strata 独自 reader を選び、GPU を使う必要がある。`strata-vision` では `--gpu` が GPU path を選び、`--tower mtmd` は独自 reader を選ばない。`--tower own` は明示選択、`auto` は対応可否によって reader を決める（`tools/vision/strata_vision.cpp:89-112,137-170`; `tools/vision/own/own_reader.cpp:49-73,114-125`）。
- fused attention 自体が有効である必要がある。`STRATA_VIT_FA` が設定されていれば `atoi(...) != 0` で選択され、未設定なら gfx1151 で wave size 32 かつ head dimension が 96 以下・8 の倍数の場合に既定で要求される。要求後も実機が gfx11、wave size 32、head dimension 96 以下かつ 8 の倍数でない場合は `m.fa` は有効にならず、この変数は chunk 分割に使われない（`tools/vision/own/vit_gpu.cu:912-928,945-954`）。
- `auto` 選択では対応可否により mtmd reader が選ばれる場合がある。特に Windows HIP で gfx1151 以外は `own_reader_supported` が mtmd を優先する。`--tower own` を明示した場合は `auto` の選択を経ず own reader を起動する（`tools/vision/own/vit_gpu.cu:870-892`; `tools/vision/own/vit_gpu.h:44-47`; `tools/vision/strata_vision.cpp:137-145,161-175`）。

## 実行時の詳細

変数は各 GPU reader プロセスが `own_reader_run` から `VitGpu::load` を呼んだときに一度読み取られ、`m.fa_units` に保存される。後続の encode ごとに環境を再読込せず、プロセス起動後の環境変更はこの reader のロード済み GPU context には反映されない（`tools/vision/own/own_reader.cpp:114-125,143-149`; `tools/vision/own/vit_gpu.cu:895-955`）。

`m.fa` が有効な encode では、`qf = max(64, fa_units / (N * H))` を出発点に 64 query 単位へ切り下げ、画像 token 数 `N` を超えない chunk 数へ上限をかける。実際には `q0` を `qf` ずつ進め、最後の launch は残り token 数だけを処理する。よってこの環境変数は fused attention の query 分割、すなわち 1 launch の大きさと launch 回数を変える。`m.fa` が false の場合は通常の score product / softmax / value product 経路に入り、この変数の値は参照されない（`tools/vision/own/vit_gpu.cu:1074-1105`）。

fused attention launch の CUDA/HIP エラーは `sync_err("the fused attention")` が `err` に記録し、own reader の warm-up 失敗なら `ERR the vision encoder failed its warm-up (...)` を stdout に出して起動失敗となる。`auto` で own reader の起動前に stdout がまだ書かれていない場合は stderr に `strata-vision: Strata's picture reader did not start (...); reading pictures with llama.cpp's reader` と出し、mtmd reader に移る（`tools/vision/own/vit_gpu.cu:1101-1103`; `tools/vision/own/own_reader.cpp:91-110,150-169`; `tools/vision/strata_vision.cpp:168-175`）。

## ログと測定値

この変数を読み取っただけではログを出さない。`STRATA_VIT_PROF` が設定されているとき、fused attention が有効なら encode 後に stderr へ `vit-prof fa: longest fused-attention launch %.2f ms (STRATA_VIT_FA_UNITS %lld)` を出し、その encode 中の最長 launch 時間と採用された `fa_units` を示す。`STRATA_VIT_PROF` は最初の encode で設定有無を static cache する（`tools/vision/own/vit_gpu.cu:1028-1035,1152-1159`）。

## 根拠

- 環境変数の既定値と HIP 側の読み取り・下限判定: `tools/vision/own/vit_gpu.cu:624-640,895-955`
- query chunk の計算、fused attention launch、失敗判定: `tools/vision/own/vit_gpu.cu:1074-1105`
- HIP build での `vit_gpu.cu` 組み込み: `tools/vision/own/CMakeLists.txt:127-131`
- reader の GPU load と encode の呼び出し: `tools/vision/own/own_reader.cpp:114-125,143-149`
- `--gpu` / `--tower` と reader 選択・fallback: `tools/vision/strata_vision.cpp:89-112,137-175`; `tools/vision/own/own_reader.cpp:49-73,91-169`
- profiler 出力: `tools/vision/own/vit_gpu.cu:1028-1035,1152-1159`
