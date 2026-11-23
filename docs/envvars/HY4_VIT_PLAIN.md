# `HY4_VIT_PLAIN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP build の GPU VisionEncoder で、WMMA を使わない場合に ViT の GEMM と attention が選ぶカーネル経路を切り替える。未設定なら `use_fdot2` が有効になり、fdot2 GEMM / attention を使う。設定されていれば `use_fdot2` が無効となり、通常の `k_gemm` / `k_attn` を使う。`HY4_VIT_PLAIN` は文字列の値ではなく設定有無で plain 経路を強制するスイッチである。`VisionEncoder::load()` が設定有無を調べて `use_fdot2` を保存し、`gemm()` と `encode()` 内の attention 分岐がその状態を参照する（`engine/src/hy4flash/run/hy4_vision.hip.h:641-648,820-858,969-984`）。

これは画像の ViT 計算経路に関する設定で、テキスト専用リクエストには関係しない。GPU image shard をロードして encode する offline `--images` 経路、serve の画像リクエスト、および同梱 vision test が利用する同じ encoder に適用される（`engine/src/hy4flash/run/hy4_main.hip.cpp:718-729`、`engine/src/hy4flash/run/hy4_serve.hip.h:431-452`、`engine/src/hy4flash/run/hy4_vision_test.hip.cpp:68-74`）。

## 値と判定

`getenv("HY4_VIT_PLAIN")` の結果を真偽判定している。文字列の parse、数値変換、空文字判定はない。HIP の GPU ロードで WMMA が選ばれていない場合、環境変数が未設定（`getenv` が null）なら `use_fdot2=true`、何らかの値が設定されていれば `use_fdot2=false` となる（`engine/src/hy4flash/run/hy4_vision.hip.h:641-647`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP GPU build、`use_wmma=false` | fdot2 GEMM / attention | 値は問わない。例: `1`、`0`、`true`、`false`、空文字、`0anything` のいずれも plain 経路 | なし。値の内容を検証しない |
| HIP GPU build、`use_wmma=true` | WMMA | 値は問わないが、この変数では経路は変わらず WMMA のまま | なし |
| CUDA build または CPU fallback | この変数を読まず、通常の plain または CPU 処理 | 該当なし | 該当なし |

大文字小文字、前後の空白、数値としての妥当性は見ない。空文字も「設定あり」として扱う。したがって `HY4_VIT_PLAIN=0` や `HY4_VIT_PLAIN=false` も plain を選ばせる。`HY4_VIT_NOWMMA` は別の先行条件で、WMMA を無効にしたうえで本変数が未設定なら fdot2、設定済みなら plain になる（`engine/src/hy4flash/run/hy4_vision.hip.h:633-647`）。

## 有効になる条件

- Strata の HIP 実装（`HY4_CUDA=0`）であること。`HY4_VIT_PLAIN` の読み取りと fdot2 kernel の選択は `#if !HY4_CUDA` の内側にある。CUDA build では読み取りがコンパイル対象外となり、`use_fdot2` は初期値 `false` のまま plain kernel を使う（`engine/src/hy4flash/run/hy4_gpu.h:17-23,324-352`、`engine/src/hy4flash/run/hy4_vision.hip.h:170-171,641-643,837-849`）。
- VisionEncoder が画像用 shard を GPU にロードすること。CPU fallback は `HY4_VIT_CPU`、`force_cpu`、VRAM 条件、または GPU shard の `hipMalloc` 失敗で選ばれ、`load()` は `HY4_VIT_PLAIN` の読み取りより前に CPU モードで return する。この経路では本変数は参照されない（`engine/src/hy4flash/run/hy4_vision.hip.h:604-629,641-648`）。
- HIP で WMMA が選ばれていないこと。`HY4_MMA && !HY4_CUDA` build では GPU の architecture が `gfx11` または `gfx12` で、かつ `HY4_VIT_NOWMMA` が未設定なら `use_wmma=true` となり、本変数の設定有無にかかわらず WMMA 経路が優先される（`engine/src/hy4flash/run/hy4_vision.hip.h:633-643,822-836,969-984`）。
- `HY4_MMA` が無効な build では WMMA 選択ブロックが存在しないため、HIP GPU load 時は本変数の設定有無で fdot2 と plain が分かれる。RDNA2 (`gfx103x`) は `hy4_gpu.h` が `HY4_MMA=0` とする（`engine/src/hy4flash/run/hy4_gpu.h:335-352`）。
- 実際に画像を encode すること。offline 実行では `recs` が空でなければ load/setup し、serve では画像付き request (`has_images`) のとき load/setup する。serve 起動時に `--vision` shard の probe は行うが、encoder のロードは最初の画像 request 時である（`engine/src/hy4flash/run/hy4_main.hip.cpp:718-725`、`engine/src/hy4flash/run/hy4_serve.hip.h:355-364,431-445`）。

## 実行時の詳細

`VisionEncoder::load()` はすでにロード済みで条件を満たすと即時 return するため、保持中の encoder では環境を読み直さない。初回または unload 後の GPU load では、shard を device に転送し、（該当 build なら）architecture と `HY4_VIT_NOWMMA` から WMMA の使用を決め、その後 `HY4_VIT_PLAIN` の有無から `use_fdot2` を決める。したがってプロセス実行中に環境値を変えても既存 encoder の選択は変わらず、unload 後に再 load した場合にだけ再評価される（`engine/src/hy4flash/run/hy4_vision.hip.h:604-607,632-648,650-657`）。

serve は各画像 request で load を試み、encode 後に CPU fallback、総 VRAM が 15 GiB 未満、または空き VRAM が 4 GiB 未満なら unload する。それ以外では encoder を保持するため、後続画像 request で再 load されない限り同じ `use_wmma` / `use_fdot2` 状態を使う。offline の画像経路は画像 encode 後に `venc.unload()` する（`engine/src/hy4flash/run/hy4_serve.hip.h:431-451`、`engine/src/hy4flash/run/hy4_main.hip.cpp:721-729`）。

各画像は `VisionCtx::setup()` から `VisionEncoder::encode()` に渡され、ViT の layer ごとの GEMM と attention が保存済みフラグに従う。`use_fdot2=true` なら `k_gemm_fdot2` と `k_attn_fdot2`、false なら `k_gemm` と `k_attn` が選ばれる。WMMA が true の場合は GEMM と attention の WMMA 分岐が優先される。ソース上で確認できる効果はこの kernel dispatch の切り替えであり、速度や出力品質の差はこの調査では測定していない（`engine/src/hy4flash/run/hy4_vision.hip.h:820-858,957-984`、`engine/src/hy4flash/run/hy4_vision.hip.h:1126-1144`）。

## ログと測定値

GPU shard load が成功すると stderr に `[vision] shard loaded to the GPU: ... (wmma)`、`(fdot2)`、または `(plain)` のいずれかが出る。これはロード時に決まった kernel mode の観測手段である。本変数専用の警告・無効値エラーはなく、測定値も記載しない（`engine/src/hy4flash/run/hy4_vision.hip.h:646-648`）。

CPU fallback 時は `[vision] shard loaded on CPU (low-VRAM fallback): ...` と出て、GPU mode の suffix は出ない（`engine/src/hy4flash/run/hy4_vision.hip.h:624-630`）。

## 根拠

- 変数の読み取り、WMMA との順序、GPU load 時ログ: `engine/src/hy4flash/run/hy4_vision.hip.h:604-648`
- fdot2 / plain GEMM dispatch と attention dispatch: `engine/src/hy4flash/run/hy4_vision.hip.h:820-858,969-984`
- encoder のロード済み判定、unload、画像 encode 呼び出し: `engine/src/hy4flash/run/hy4_vision.hip.h:604-607,650-657,1126-1144`
- HIP/CUDA および RDNA2 build macro: `engine/src/hy4flash/run/hy4_gpu.h:17-23,324-352`
- offline / serve での画像時ロードと保持条件: `engine/src/hy4flash/run/hy4_main.hip.cpp:718-729`、`engine/src/hy4flash/run/hy4_serve.hip.h:355-364,431-451`
- 同梱 vision test の encoder load: `engine/src/hy4flash/run/hy4_vision_test.hip.cpp:68-74`
