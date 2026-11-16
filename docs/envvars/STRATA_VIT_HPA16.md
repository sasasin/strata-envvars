# `STRATA_VIT_HPA16`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

HIP 版の Strata 独自 vision GPU tower で、16-bit の重み行列積を「積和は float32、出力は入力行列と同じ F16/BF16」にしてから float32 に戻す経路を選ぶ。通常の hipBLAS 経路は float32 出力を直接書くため、この設定では出力の丸め位置と一時バッファが変わる。値を読むのは `VitGpu::load`、積を実行するのは `VitGpuImpl::gemm`（`tools/vision/own/vit_gpu.cu`）。CUDA、CPU、Metal、SYCL の実装にはこの変数の読み取り箇所がない。`STRATA_VIT_OWN_HIP` または `STRATA_VISION_HIP` で HIP tower を含むビルドが必要である（`tools/vision/own/CMakeLists.txt:24-35,127-136`）。

## 値と判定

HIP ビルドの `VitGpu::load` が `std::getenv` で設定有無を調べ、設定されていれば `std::atoi(e) != 0` を gfx1151 の既定値を含む状態へ代入する。unset は既定値を保ち、空文字を含む設定済みの値は `atoi` の結果で上書きする。文字列全体の妥当性検査、範囲検査、警告はない（`tools/vision/own/vit_gpu.cu:911-943`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| HIP、`VitGpu::load` の実行 GPU が gfx1151 | ON（`m.hpa16 = true`） | `1`, `2`, `-1`, `1tail` | `0`, `0anything`, 空文字, `true`, `tail` |
| HIP、その他の GPU | OFF（初期値 false） | `1`, `2`, `-1`, `1tail` | `0`, `0anything`, 空文字, `true`, `tail` |
| HIP 以外のビルド | 該当なし | 該当なし | この変数を読むコードがなく、効果なし |

`atoi` は先頭の空白と符号を許し、先頭の整数部分を変換するため、`"  +1tail"` は非ゼロ、整数に変換できない文字列や空文字は 0 になる。負の非ゼロ整数も有効。数値の後ろは検査しない。コードに上限・下限や不正値時の別 fallback はない（`tools/vision/own/vit_gpu.cu:940`）。

## 有効になる条件

- `STRATA_VIT_HPA16` の判定自体は HIP ビルドでのみ行われる。HIP の GPU tower が使われない CPU 読み取りや、CUDA / Metal / SYCL の tower には効かない（`tools/vision/own/CMakeLists.txt:24-35,127-136`; `tools/vision/own/own_reader.cpp:49-73,89-127`）。
- tower の選択はこの変数では行わない。`own_reader_run` の GPU 経路で `VitGpu::load` に到達したときに限り読み取られる。`--vision` / `STRATA_VISION_TOWER` によって mtmd が選ばれた場合は対象外（`tools/vision/own/own_reader.cpp:37-42,84-87,116-125`）。
- 重み積の HPA16 経路には、`kind_a != CUDA_R_32F` と一時出力バッファの容量条件も必要。F32 入力の積はこの分岐を通らず float32 出力の hipBLAS 経路へ進む（`tools/vision/own/vit_gpu.cu:748-775`）。重みの F16/BF16 の持ち方は `STRATA_VIT_BF16_AS_F16` とカード既定値でも変わるが、この変数の値をその設定が上書きするわけではない（同:701-734,920-940）。
- hipBLASLt がビルドに含まれ、`STRATA_VIT_LT` が非ゼロで重み積の形状を処理できる場合、`gemm` は先に float32 出力の hipBLASLt 積を実行して終了するため、この HPA16 の hipBLAS 分岐には到達しない。hipBLASLt がその形状を処理できず fallback した場合は HPA16 条件が評価される（`tools/vision/own/vit_gpu.cu:483-487,752-764`; `tools/vision/own/CMakeLists.txt:132-136`）。
- `STRATA_VIT_HPA16_ATT` は attention の P*V 積用の別設定であり、この変数だけでは切り替わらない（`tools/vision/own/vit_gpu.cu:624-630,643-665,940-944`）。

## 実行時の詳細

gfx1151（`gcnArchName` が `gfx1151` または機能接尾辞付き）では、`load` がまず `m.hpa16` を true にし、その後、環境変数が存在すれば `atoi` の結果で上書きする。したがって unset は gfx1151 の既定 ON を維持し、`STRATA_VIT_HPA16=0` や空文字は OFF にする。他の HIP GPU は unset で OFF、非ゼロ値を設定すれば ON を要求できる。gfx 判定は `tools/vision/own/vit_gpu.h:37-43`、既定値と上書き順は `tools/vision/own/vit_gpu.cu:911-943`。

値は GPU tower のロード時に読み取られ、`m.hpa16` に保持される。encode ごとの再読込や static cache はなく、同じロード済み tower で環境を後から変更しても反映されない。別の tower をロードするとその `load` で改めて判定される（`tools/vision/own/vit_gpu.cu:895-943`）。

HPA16 が選ばれ、hipBLASLt が先に処理しておらず、入力型とバッファ容量が条件を満たすと、`gemm` は `cublasGemmEx` に入力型と同じ 16-bit 出力型、`VIT_COMPUTE_32F` を指定する。その結果を `k_widen16` で F16/BF16 から float32 に戻して後続処理へ渡す。対象は QKV、出力投影、FFN、merger の重み積など `gemm` を使う重み行列積であり、attention の P*V は別フラグの `bgemm` 経路である（`tools/vision/own/vit_gpu.cu:748-775,1054-1059,1067-1072,1119-1145`）。

このスイッチが ON の場合、`size_buffers` は HPA16 用の追加出力バッファを確保する。確保に失敗すると `VitGpu::load` / `encode` は失敗を返し、`own_reader_run` は vision encoder のロード失敗として扱う。通常の float32 出力積への自動 fallback はこの確保失敗時には行われない（`tools/vision/own/vit_gpu.cu:780-828,1001-1008,1021-1023`; `tools/vision/own/own_reader.cpp:92-100,124`）。

## ログと測定値

HPA16 または `STRATA_VIT_HPA16_ATT` のいずれかが有効なら stderr に次の形式を出す。両方が無効ならこの行は出ない。文言は設定値の個別表示ではなく、有効な積の種類を示す（`tools/vision/own/vit_gpu.cu:942-944`）。

```text
vit-hpa16: 16-bit results with float32 accumulation for the weight products
```

両フラグが有効なときは `the weight products and the attention's P*V product`、attention 側だけなら `the attention's P*V product` が末尾に入る。BLAS 呼び出し失敗時は `gemm` が `the BLAS matrix product failed (status N)` をエラー文字列にする。GPU tower のロード失敗は、`start_error` が渡されていない場合 `own_reader_run` が stdout に `ERR cannot load the vision encoder <mmproj> (<reason>)` を出して flush し、コード 1 を返す。`start_error` がある場合はそこへエラーを格納し `kOwnStartFailed` を返す（`tools/vision/own/vit_gpu.cu:758-769`; `tools/vision/own/own_reader.cpp:92-100,124`）。

ソースコメントは gfx1151 の測定として、18 枚・1,024 token の Qwen3.8 で mtmd-HIP 比 0.54–0.83（中央値 0.66）、Qwen3.6 で 0.57–0.91（中央値 0.67）と記録している。コメントには OS と量子化条件が示されていないため、これらは記載された条件内のソースコメント上の値であり、他環境へ一般化できない（`tools/vision/own/vit_gpu.cu:912-918`）。

`docs/DETAILS.md:990-1002` は画像読み取りの選択肢や reader の概略を記載しているが、`STRATA_VIT_HPA16` の判定や HIP の積の詳細は説明していない。

## 根拠

- `tools/vision/own/vit_gpu.cu:624-630,748-775` — HPA16 の用途、重み積の分岐、16-bit 出力を float32 に戻す処理。
- `tools/vision/own/vit_gpu.cu:780-828,895-943` — バッファ確保、gfx1151 既定値、環境値の読み取りとログ。
- `tools/vision/own/vit_gpu.cu:1054-1072,1119-1145` — 重み積の呼び出し箇所。
- `tools/vision/own/CMakeLists.txt:24-35,127-136` — HIP / CUDA / hipBLASLt のビルド条件。
- `tools/vision/own/own_reader.cpp:37-42,49-73,84-127` — tower 選択、GPU tower のロードと失敗経路。
- `tools/vision/own/vit_gpu.h:37-47` — gfx1151 の識別。
- `docs/DETAILS.md:990-1002` — 利用者向けの画像読み取り概略との照合。
