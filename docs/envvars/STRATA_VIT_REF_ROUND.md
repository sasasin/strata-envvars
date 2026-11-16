# `STRATA_VIT_REF_ROUND`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Strata の vision encoder の own tower で、16-bit 重み型（BF16 または F16）に合わせた丸めを診断用に有効にする。CPU 高速経路 (`VitCpu`) と CPU 参照経路 (`VitRef`) は行列積の入力側の活性値を丸め、GPU 経路 (`VitGpu`) は行列積の float32 結果を重みの型へ丸めて float32 に戻す。したがって同じ環境変数名でも backend 間で丸める位置は異なる。設定しない場合は丸めない。CPU では重みが F32 または Q8_0 展開値なら有効にならない。GPU は `K_F32` の積を除外する guard がある CUDA/HIP 実装を含め、GGUF の F32 / Q8_0 行列を BF16 / F16 に変換して積を行うため、丸めもその変換後の16-bit型で行う (`tools/vision/own/vit_cpu.cpp:184-192`, `tools/vision/own/vit_ref.cpp:197-201`, `tools/vision/own/vit_gpu.cu:694-734,771-778`, `tools/vision/own/vit_sycl.cpp:331-352,360-370`, `tools/vision/own/vit_metal.mm:146-164,237-247`)。

対象は `strata-vision` に組み込まれた own tower (`--tower own` または `auto` が own を選んだ場合) と `strata-vision-own`。通常の `--tower mtmd` 経路には作用しない。`strata-vision` の `--tower` 指定は環境変数 `STRATA_VISION_TOWER` による既定選択を上書きし、`auto` は backend・モデル対応状況で own / mtmd を決める (`tools/vision/strata_vision.cpp:94-112,137-175`; `tools/vision/own/own_main.cpp:1-5,13-41`)。

## 値と判定

全読み取り箇所で C/C++ の `std::getenv` と `std::atoi` を使用し、変換結果がゼロ以外なら有効。CPU 高速経路はさらに空文字を除外してから `atoi` する。`atoi` は文字列全体の厳密な検証ではないため、先頭の空白と符号を許し、数値の後ろにある文字列を検査しない。たとえば `" 1tail"` は有効、`"0tail"` は無効、`"true"` や空文字は無効。`"-1"` などゼロ以外の整数も有効。数値として読めない先頭なら `atoi` は 0 を返す。CPU は最初の QKV 重み型を使って BF16 / F16 のどちらで丸めるかを決める。GPU は各積でその積の重み型を参照する。

| 経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CPU 高速 `VitCpu` | 丸めなし | `atoi(value) != 0` かつ重み型が BF16 / F16。例: `1`, `-1`, ` 1tail` | 空文字、`0`, `0tail`, `true`, 数値として始まらない文字列。重みが F32 / Q8_0 展開値の場合は設定値によらず丸めなし |
| CPU 参照 `VitRef` | 丸めなし | `atoi(value) != 0` かつ先頭 QKV 重み型が BF16 / F16 | 空文字、`0`, `0tail`, `true`, 数値として始まらない文字列。対象型以外では丸めなし |
| CUDA / HIP `VitGpu` | 丸めなし | `atoi(value) != 0`。各行列積の結果を GPU 側の重み型へ丸める。GGUF の F32 / Q8_0 行列もロード時に BF16 / F16 化される | 空文字、`0`, `0tail`, `true`, 数値として始まらない文字列 |
| SYCL / Metal `VitGpu` | 丸めなし | `atoi(value) != 0`。各行列積の結果を GPU 側の重み型へ丸める。GGUF の F32 / Q8_0 行列もロード時に BF16 / F16 化される | 空文字、`0`, `0tail`, `true`, 数値として始まらない文字列 |

実装位置: CPU 高速経路は `vit_cpu_round_kind`、CPU 参照経路は `VitRef::load`、CUDA/HIP は `VitGpu::load`、SYCL は対応する `VitGpu::load`、Metal は同名の `VitGpu::load`。いずれも値の範囲チェックや文字列全体の妥当性検査はしない (`tools/vision/own/vit_cpu.cpp:180-192`, `tools/vision/own/vit_ref.cpp:197-201`, `tools/vision/own/vit_gpu.cu:1001`, `tools/vision/own/vit_sycl.cpp:475`, `tools/vision/own/vit_metal.mm:466`)。

## 有効になる条件

- own tower が選択されていること。`strata-vision` の `--tower mtmd` は対象外。明示的な `--tower own` は own を選び、`auto` は対応状況により選択し、開始前に own が失敗した場合は mtmd へ fallback する (`tools/vision/strata_vision.cpp:110-112,137-175`; `tools/vision/own/own_reader.cpp:49-72,89-110`)。
- CPU では GPU を使わない実行経路であること。通常は `VitCpu` が使われるが、別環境変数 `STRATA_VIT_CPU=ref` が完全一致すると `VitRef` が選ばれる。`--gpu` が指定された場合、この CPU 選択は通らず GPU 経路を使う (`tools/vision/own/own_reader.cpp:128-148`)。
- GPU 経路は対応 backend でビルドされている必要がある。CUDA、HIP、SYCL、Metal は別々の build 条件で選択され、Metal は macOS の場合だけ有効 (`tools/vision/own/CMakeLists.txt:13-64,120-164`)。
- CPU の丸めには少なくとも先頭 QKV 重みが BF16 または F16 である必要がある。CPU 高速経路はこの型をロード時に取得し (`tools/vision/own/vit_cpu.cpp:54-77,170-180`)、参照経路も GGUF の `v.blk.0.attn_qkv.weight` の型で判定する (`tools/vision/own/vit_ref.cpp:197-201`)。
- CLI 引数で丸め値を直接指定する機能はない。`--tower`、`--gpu`、`--threads` などは経路や実行条件を決めるが、この変数を上書きしない (`tools/vision/strata_vision.cpp:101-135`)。

## 実行時の詳細

値は各 tower オブジェクトの `load` 中に一度読み取られ、CPU 高速経路は `Impl::act_round`、CPU 参照経路は `act_round_`、GPU 経路は `round_out` に保存される。own reader は READY を出す前に tower を load し、その後の画像要求を同じ tower で処理するため、サーバープロセス稼働中に外部から環境変数を変えても既存 tower には反映されない。反映にはプロセスまたは tower の再ロードが必要 (`tools/vision/own/own_reader.cpp:106-149,168-194`; `tools/vision/own/vit_cpu.cpp:142-181`; `tools/vision/own/vit_ref.cpp:180-215`; `tools/vision/own/vit_gpu.cu:895-1008`; `tools/vision/own/vit_sycl.cpp:430-479`; `tools/vision/own/vit_metal.mm:368-479`)。

CPU 高速経路は層ごとに layer norm 後の活性値、QKV の RoPE 後の値、attention context、FFN の中間値、merger 入力を重み型へ丸める。CPU 参照経路も層と merger の活性値を丸め、QKV 出力は診断用に F16 へ丸める (`tools/vision/own/vit_cpu.cpp:299-317,365-395`; `tools/vision/own/vit_ref.cpp:292-315,349-370`)。GPU は各行列積の出力を丸め、CUDA/HIP では `w.kind != K_F32` の場合だけ適用する。ただし GPU の `upload_matrix` は GGUF の F32 を BF16、Q8_0 を F16 に変換しているため、それらの元ファイル型も通常はこの guard を通る16-bit重みとして扱われる (`tools/vision/own/vit_gpu.cu:694-734,766-778`; `tools/vision/own/vit_sycl.cpp:331-352,360-370`; `tools/vision/own/vit_metal.mm:146-164,237-247`)。

この変数専用のログ、警告、終了コードはない。通常の own tower 起動ログは `strata-vision: own tower (...) loaded ...`。own tower の起動失敗は `auto` 選択なら stderr に fallback 理由を出して mtmd を起動し、明示的な `own` では reader が `ERR ...` を返す経路がある (`tools/vision/own/own_reader.cpp:92-110,141-169`; `tools/vision/strata_vision.cpp:168-175`)。この変数が生成する数値の違い自体を示すログは見つからなかった。

比較用の `tools/vision/own/answers_gate.py` は `+round` 指定時に `export STRATA_VIT_REF_ROUND=1` を含む shell wrapper を作り、その環境で reader を起動する。これは比較 harness の環境設定であり、通常の設定既定値を変更するものではない (`tools/vision/own/answers_gate.py:62-80`)。

`docs/DETAILS.md` にはこの変数に関する記述は見つからなかった。測定値は本書に転記していない。`vit_cpu.cpp` のコメントには過去の画像集合での cosine 値の記載があるが、それは現在の一般的な性能・正確性保証を示すものではない (`tools/vision/own/vit_cpu.cpp:184-188`)。

## 根拠

- 候補名の全参照と実際の読み取り: `tools/vision/own/vit_cpu.cpp:180-192`, `tools/vision/own/vit_ref.cpp:197-201`, `tools/vision/own/vit_gpu.cu:1001`, `tools/vision/own/vit_sycl.cpp:475`, `tools/vision/own/vit_metal.mm:466`。
- tower の選択、開始条件、CPU 参照実装の選択: `tools/vision/strata_vision.cpp:94-175`, `tools/vision/own/own_reader.cpp:89-169`。
- backend ビルド条件: `tools/vision/own/CMakeLists.txt:13-64,120-164`。
- 比較用 wrapper による値の設定: `tools/vision/own/answers_gate.py:62-80`。
