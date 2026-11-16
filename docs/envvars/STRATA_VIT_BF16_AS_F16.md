# `STRATA_VIT_BF16_AS_F16`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Strata 同梱の own Vision GPU reader が、GGUF 内の BF16 重み行列を GPU に載せる形式と、対応する積の入力値の精度を切り替える診断用 override です。`vit_gpu_bf16_mode` が環境値をモード番号へ変換し、`VitGpu::load` がその番号を `bf16_mode` に保存します。対象は `tools/vision/own/vit_gpu.cu` の CUDA/HIP 実装です。通常の Strata テキスト生成エンジンの設定ではありません（`tools/vision/own/vit_gpu.cu:477-481, 895-930`）。

モード `0` は BF16 重みを BF16 のまま保持し、モード `1` は重みを F16 に格納して積の入力を BF16 相当に丸め、モード `2` は重みを F16 に格納して入力も F16 にします。切り替わるのは BF16 型の行列の格納・積入力です。F16 型や他の型の重みをこの変数が選び直す処理はありません（`tools/vision/own/vit_f16.h:16-20`, `tools/vision/own/vit_gpu.cu:694-746`）。

## 値と判定

GPU reader は `std::getenv` の結果を `vit_gpu_bf16_mode` に渡します。未設定ならカード既定値をそのまま使います。設定時は先頭の ASCII space と tab だけを飛ばし、任意の `+` / `-` の後に続く十進数字を読みます。数字が一つもなければ `v=0` のままです。数字列の後ろは検証せず無視します。数値が `0` ならモード 0、`2` ならモード 2、それ以外ならモード 1 です。`true` など数値でない文字列、空文字、数字のない符号だけは 0 として扱われます。大文字小文字の比較はありません。10進変換は `atoi` 等ではなく helper 内の手書きループです（`tools/vision/own/vit_f16.h:23-35`, `tools/vision/own/vit_gpu.cu:929`）。

| 条件（build / GPU） | unset | 有効になる値（例） | その他の例と判定 |
|---|---|---|---|
| CUDA GPU reader | モード 2（K_HF） | `0` → 0、`1` → 1、`2` → 2 | `""`、`true`、`x` → 0。`0anything` → 0、`2junk` → 2、`12`、`-1` → 1 |
| HIP GPU reader、gfx1151（Strix Halo） | モード 1（K_BH） | `0` → 0、`1` → 1、`2` → 2 | 上記と同じ変換規則 |
| HIP GPU reader、gfx1151 以外 | モード 2（K_HF） | `0` → 0、`1` → 1、`2` → 2 | 上記と同じ変換規則 |

符号の直後に数字がなければ 0（例: `+`、`-`）。先頭の space/tab は許容します（` 2` → 2）が、改行やその他の空白を読み飛ばしません（先頭が改行なら数字なしとして 0）。数字列の後の文字は無視するため、全体が数値文字列かの検証はありません。負数は `-0` だけ 0 となり、`-2` を含むそれ以外はモード 1 です。パーサーは 1,000,000 を超えた桁で走査を止めますが、0 と 2 以外は同じモード 1 になるため、その後の違いはありません（`tools/vision/own/vit_f16.h:25-35`）。

## 有効になる条件

- `strata-vision` または standalone `strata-vision-own` が own Vision reader を使い、GPU 経路であることが必要です。GPU 実装は CUDA または HIP build で `vit_gpu.cu` を組み込んだ場合に限られます（`tools/vision/own/CMakeLists.txt:13-44, 120-138`）。
- `strata-vision` では `--tower mtmd` を選ぶと own reader を使いません。`--tower own` または `auto` で own reader が選ばれた場合に対象になります。選択既定値は `STRATA_VISION_TOWER` と `auto` の判定で決まり、明示的な `--tower` が優先します（`tools/vision/strata_vision.cpp:94-112`, `tools/vision/own/own_reader.cpp:49-72, 84-87`）。
- GPU 実行には `--gpu` が必要です。own reader が CPU で動く場合、この変数を読む GPU load 経路には入りません（`tools/vision/own/own_reader.cpp:114-136`）。
- 効果があるのはアップロード対象 tensor が GGUF BF16 型の場合だけです。GGUF F16、F32、Q8_0 の各分岐は別の型選択・変換を行います（`tools/vision/own/vit_gpu.cu:694-734`）。
- HIP gfx1151 では環境変数が未設定のときモード 1 を選ぶ初期化があります。設定があれば、この値変換がその既定値を上書きします（`tools/vision/own/vit_gpu.cu:911-929`）。
- CUDA と gfx1151 以外の HIP は初期値がモード 2 です（`tools/vision/own/vit_gpu.cu:479, 904-929`）。
- SYCL と Metal の own Vision 実装にはこの名前の読み取り箇所がありません。候補一覧にある一方、現行コード上この設定の効果を受ける実装ではありません（SYCL の別実装: `tools/vision/own/vit_sycl.cpp:35-39, 341-347`; 候補一覧: `docs/envvars/000_envvers.md:2230`）。

## 実行時の詳細

環境値は `VitGpu::load` の中で `std::getenv` により読み、ロードごとに `m.bf16_mode` に保存されます。読み取り結果は同じ `VitGpu` の重みアップロードに使われ、画像リクエストのたびには再読込しません。プロセス実行中に環境を変更しても、すでにロード済みの reader には反映されません（`tools/vision/own/vit_gpu.cu:895-930`, `tools/vision/own/own_reader.cpp:116-125`）。

BF16 tensor のロードでは、モード 0 は raw BF16 を読み込み BF16 のまま device にコピーします。モード 1 はホストで float 読み出しから F16 へ変換してコピーします。モード 2 は raw BF16 をコピーした後、GPU kernel で F16 に変換しますが、その行列に F16 の有限範囲外の重みが一つでもあれば当該行列は BF16 のまま保持します。したがってモード 2 でも全ての BF16 行列が F16 になるとは限りません（`tools/vision/own/vit_gpu.cu:694-743`; 判定: `tools/vision/own/vit_f16.h:54-64`）。

選ばれた kind は行列積の入力 dtype に使われ、GPU reader の Vision encoder 計算へ進みます（`tools/vision/own/vit_gpu.cu:746-755, 1066-1071, 1119-1144`）。既定の override はなく、この環境変数を CLI 引数や別の環境変数で後から上書きする分岐もありません。`STRATA_VIT_BF16_AS_F16` 自体について有効・無効を知らせるログはありません。

## ログと測定値

変数を設定したこと自体のログはありません。モード 2 で `STRATA_TRACE` が設定されている場合（値の内容ではなく設定有無を判定）、ロードした各 BF16 行列について `stderr` に `vit-f16 trace: ...` の形式で F16 で正確に保持できなかった重み数、F16 範囲外の数、最大誤差を出します。モード 2 以外ではこの行列別 trace 用記録は追加されません（`tools/vision/own/vit_gpu.cu:481, 701-710, 929-930, 989-993`）。

GPU 変換 kernel の起動エラーはロード失敗となり、エラー文面は `cannot load the vision encoder <mmproj> (the BF16 to F16 conversion failed on the GPU)` です。standalone reader や fallback しない経路では `own_reader_run` がこれを `stdout` に `ERR ` 付きで出します。`strata-vision` の own reader が起動前に失敗して fallback 可能な場合は、まだ `stdout` に出力せず、`stderr` に `strata-vision: Strata's picture reader did not start (<エラー>); reading pictures with llama.cpp's reader` を出して mtmd reader へ移ります（`tools/vision/own/vit_gpu.cu:739-742`, `tools/vision/own/own_reader.cpp:93-100, 124`, `tools/vision/strata_vision.cpp:161-175`）。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:2230`。
- 値の変換、未設定値の扱い: `tools/vision/own/vit_f16.h:16-35`。
- GPU・backend 既定値と環境値の読み取り: `tools/vision/own/vit_gpu.cu:473-481, 895-930`。
- BF16 tensor の kind 別ロード、GPU 変換と fallback: `tools/vision/own/vit_gpu.cu:694-746`、`tools/vision/own/vit_f16.h:54-64`。
- 呼び出しと reader 適用範囲: `tools/vision/own/own_reader.cpp:49-72, 89-136`; build 条件: `tools/vision/own/CMakeLists.txt:13-60, 120-138`。
- trace と失敗経路: `tools/vision/own/vit_gpu.cu:739-742, 989-993`; `tools/vision/own/own_reader.cpp:93-100, 124`; fallback: `tools/vision/strata_vision.cpp:161-175`。
