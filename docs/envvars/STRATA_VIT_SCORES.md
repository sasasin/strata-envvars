# `STRATA_VIT_SCORES`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Strata 同梱の own vision tower が GPU で画像を encode するとき、attention のスコア用バッファ `d_S` の容量を指定する診断・調整用設定。値は「各 attention chunk に保持するスコア要素数」を Mi 要素単位で指定する。スコア要素と同じ chunk の query 数が変わるため、GPU メモリ使用量と attention の chunk 分割に影響する。CPU の own tower と mtmd reader では読まれない。読み取りは CUDA/HIP の `vit_gpu.cu`、Metal の `vit_metal.mm`、SYCL の `vit_sycl.cpp` にある各 GPU tower の `load` 内で行われる（`tools/vision/own/vit_gpu.cu:895-1009`、`tools/vision/own/vit_metal.mm:432-479`、`tools/vision/own/vit_sycl.cpp:425-483`）。

この own tower は単独の `strata-vision-own` としても、`strata-vision --tower own` の reader としても使われる。ビルド時に CUDA、HIP、SYCL、または macOS の Metal backend を含める必要がある（`tools/vision/own/own_main.cpp:1-5`、`tools/vision/own/CMakeLists.txt:13-70,120-164`）。Strata の `docs/DETAILS.md` は製品の画像 reader の選択を説明するが、この変数の詳細は記載していない（`docs/DETAILS.md:986-1013`）。

## 値と判定

各 GPU backend は `std::getenv` で設定有無を見て、値があれば `std::atoi` で `int` に変換する。変換結果が `1` 以上の場合だけ `kScoreElems = (size_t)v << 20` とし、`scores_env = true` にする。入力文字列全体の検証、末尾文字の検査、大文字小文字の扱いはない。従って `"2junk"` や先頭空白付き `" 2"` は `atoi` が返す `2` として受理され、`"1.5"` は `1` として受理される。`"true"`、空文字、`"0"`、`"0anything"`、負数、数値に変換できない文字列は `atoi` が `0` 以下を返すため設定は有効にならない。正値の上限 clamp はない。整数型の範囲を超える入力についてコードは検査・保証していない。

| 条件（build/backend） | unset または変換結果 < 1 | 有効値（例） | 無効値（例） |
|---|---|---|---|
| CUDA/HIP (`vit_gpu.cu`) | 通常 8 Mi 要素。NVIDIA Pascal (compute capability 6.x) では該当する行列形式のとき 32 Mi 要素 | `1` → 1 Mi、`32` → 32 Mi | `0`、`-1`、`true`、空文字 |
| Metal (`vit_metal.mm`) | 8 Mi 要素 | `1` → 1 Mi、`32` → 32 Mi | 同上 |
| SYCL (`vit_sycl.cpp`) | 32 Mi 要素 | `1` → 1 Mi、`32` → 32 Mi | 同上 |

各 backend の初期値と CUDA の Pascal 上書き後に環境値を適用する順序は、`tools/vision/own/vit_gpu.cu:459-464,895-909,994-1008`、`tools/vision/own/vit_metal.mm:109-121,466-473`、`tools/vision/own/vit_sycl.cpp:291-298,474-479` にある。Mi 要素はコード上の `1 << 20` 要素であり、バッファは要素あたり 2 byte なので、例えば 8 Mi 要素は 16 MiB 分に相当する。

## 有効になる条件

- 実行する reader が Strata の own GPU tower であること。CPU tower はこの変数を参照しない。`own_reader_run` は GPU 選択時に `VitGpu::load` を呼び、CPU 選択時は `VitCpu` / `VitRef` をロードする（`tools/vision/own/own_reader.cpp:114-140`）。
- 実行バイナリに対象 backend がビルドされており、own tower の GPU reader が選択されること。`strata-vision` では `--gpu` と `--tower own`（または `STRATA_VISION_TOWER=own`）が該当する。`strata-vision-own` では `--gpu` を指定する（`tools/vision/strata_vision.cpp:94-112,141-173`、`tools/vision/own/own_main.cpp:1-5,22-31`）。
- CUDA/HIP の fused attention が選ばれている場合、容量はロード時に確保されるものの、encode 中の attention は fused kernel 経路を使い `d_S` を使わない。HIP で fused attention が使えるかはカードと head size 等の条件で決まり、`STRATA_VIT_FA` も選択に関係する（`tools/vision/own/vit_gpu.cu:902-928,945-954,1074-1105`）。
- 画像サイズ `N`（patch 数）が 16,384 を超えるとき、未設定・無効値なら backend 別の large default が選ばれる。CUDA/HIP は 512 Mi、Metal/SYCL は 256 Mi 要素。正の有効値を設定すると `scores_env` が立ち、この大画像用既定容量も指定容量に置き換わる（`tools/vision/own/vit_gpu.cu:462-464,797-802`、`tools/vision/own/vit_metal.mm:115-120,257-261`、`tools/vision/own/vit_sycl.cpp:293-297,379-386`）。
- `STRATA_VIT_SCORES_LARGE` は `N > 16,384` の大画像用容量だけを `atol` で別途上書きする。正の `STRATA_VIT_SCORES` が有効なら `scores_env` により large 容量は選ばれず、この変数の指定も適用されない。`STRATA_VIT_SCORES` が未設定または無効値なら、large の既定値または `STRATA_VIT_SCORES_LARGE` の正値が使われる（CUDA/HIP: `tools/vision/own/vit_gpu.cu:462-464,1003-1005,801-802`、Metal: `tools/vision/own/vit_metal.mm:115-117,468-469,260-261`、SYCL: `tools/vision/own/vit_sycl.cpp:293-297,477-478,385-386`）。
- 指定容量が小さくても、実際の要素数は全体の score 数を超えず、また少なくとも 64 query 分を確保する式で決まる。従って `STRATA_VIT_SCORES` は厳密な確保量の上限ではない（CUDA/HIP: `tools/vision/own/vit_gpu.cu:797-802`、Metal: `tools/vision/own/vit_metal.mm:257-261`、SYCL: `tools/vision/own/vit_sycl.cpp:379-386`）。

## 実行時の詳細

環境値は own GPU tower の `load` 中、重みのロード後かつ `size_buffers` による初期 work buffer 確保前に読み取られる。ロード時に `kScoreElems` と `scores_env` に保存し、各画像でバッファを確保・拡張するときに使うため、プロセス実行中の環境変更を再読込する経路はない。CLI 引数による同名設定や別変数からの上書きもない（CUDA/HIP: `tools/vision/own/vit_gpu.cu:895-1009`、Metal: `tools/vision/own/vit_metal.mm:432-479`、SYCL: `tools/vision/own/vit_sycl.cpp:425-483`）。

バッファ計算では、対象画像の patch 数 `N` が 16,384 以下なら `kScoreElems`、それを超え、かつ `scores_env` が false なら large default を `budget` とする。実際の容量 `sp_elems` は `min(heads * N * Np, max(budget, heads * Np * 64))` で決まり、attention の query chunk 幅は概ね `sp_elems / (heads * Np)` となる（CUDA/HIP: `tools/vision/own/vit_gpu.cu:797-802,1074-1079`、Metal: `tools/vision/own/vit_metal.mm:257-261,542-546`、SYCL: `tools/vision/own/vit_sycl.cpp:384-386,548-552`）。

大画像向け既定容量の確保に失敗した場合、コードは通常容量 `kScoreElems` で一度だけ再試行する。正の `STRATA_VIT_SCORES` を指定した場合は `budget == kScoreElems` となるため、この再試行条件を満たさず、指定容量の確保失敗はロード失敗になる。CUDA/HIP・SYCL は `size_buffers` が false を返し、Metal も `d_S` が確保できなければ false を返す（`tools/vision/own/vit_gpu.cu:815-826`、`tools/vision/own/vit_sycl.cpp:392-404`、`tools/vision/own/vit_metal.mm:273-280`）。

## ログと測定値

`STRATA_VIT_SCORES` 自体の値や確保容量を出すログは見つからなかった。確保失敗時は backend のエラーが伝播し、reader の起動時なら `cannot load the vision encoder <path> (<reason>)` となる。明示的な own 起動では `ERR <message>` を stdout に出して起動失敗コードで終了する。`auto` 選択の起動前に失敗した場合は `start_error` に理由を返し、`strata-vision` が `Strata's picture reader did not start (%s); reading pictures with llama.cpp's reader` を stderr に出して mtmd reader を開始する（`tools/vision/own/own_reader.cpp:89-110,121-125`、`tools/vision/own/own_reader.h:20-22`、`tools/vision/strata_vision.cpp:164-173`）。

## 根拠

- 候補一覧にあることと実際の読み取り箇所: `docs/envvars/000_envvers.md:2250-2251`、`tools/vision/own/vit_gpu.cu:1003`、`tools/vision/own/vit_metal.mm:468`、`tools/vision/own/vit_sycl.cpp:477`。
- backend と standalone / linked build: `tools/vision/own/CMakeLists.txt:13-70,120-164`、`tools/vision/own/own_main.cpp:1-5`。
- 値変換、既定値、chunk サイズ、fallback: 上記「値と判定」「実行時の詳細」に併記した各 backend の行。
- 選択・失敗の reader 経路および一般的な vision reader の資料: `tools/vision/strata_vision.cpp:94-112,141-173`、`tools/vision/own/own_reader.cpp:89-169`、`tools/vision/own/own_reader.h:20-27,43-47`、`docs/DETAILS.md:986-1013`。
