# `STRATA_VIT_NPAD`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Strata 独自の GPU vision tower が attention score 行に使う leading dimension（`Np`）の丸め幅を診断用に上書きする。画像ごとの patch 数 `N` を `Np = ceil(N / 幅) * 幅` に丸め、CUDA/HIP では score バッファ容量の計算、attention GEMM の行 stride と softmax の行 stride に、Metal では同じ score バッファ・行 stride に使う。GPU score 行の余白を変えるもので、画像の patch 数や出力 token 数そのものを変える設定ではない（`tools/vision/own/vit_gpu.cu:469-472,797-802,1074-1115`; `tools/vision/own/vit_metal.mm:118-121,259-261,542-566`; `tools/vision/own/own_reader.cpp:182-199`）。

対象は `strata_vit_own` の GPU バックエンドが選択され、独自 tower が実際にロードされる経路に限られる。CUDA/HIP は `vit_gpu.cu`、macOS Metal は `vit_metal.mm` で読み取る。CMake 上、これらはそれぞれ CUDA、HIP、Apple Metal の build 条件で組み込まれる。CPU tower と SYCL tower にこの変数の読み取りはない（`tools/vision/own/CMakeLists.txt:13-22,24-44,46-54,56-70,120-137,140-164`; `tools/vision/own/vit_sycl.cpp:424-479`）。

## 値と判定

CUDA/HIP と Metal の両方で `std::getenv` が非 null の場合に `std::atoi` で整数へ変換し、`v >= 8 && v % 8 == 0` のときだけ `n_pad = v` に設定する。`atoi` は文字列全体の厳密な検証ではなく、先頭の整数として読める部分を変換する。したがって末尾の文字は無視され、整数部分がない文字列は 0 となる。空文字も設定済みとして読み取りに入るが、変換結果 0 のため採用されない。大文字小文字による判定はない（`tools/vision/own/vit_gpu.cu:1006`; `tools/vision/own/vit_metal.mm:470`）。

| 条件 | 未設定 | 採用される値の例 | 不採用となる値の例 |
| --- | --- | --- | --- |
| CUDA / HIP own GPU tower、または Metal own GPU tower | `n_pad=0` のまま。画像 patch 数 `N > 16384` なら幅 64、それ以外は幅 8 | `8`, `16`, `64`, `16junk`（`atoi` の結果 16） | 空文字、`0`, `7`, `9`, `-8`, `true`, `9junk` |
| CPU / SYCL / 外部 mtmd reader | この変数を読むコードなし | 該当なし | 該当なし |

採用値に上限チェックや clamp はない。正の 8 の倍数であれば採用される。無効値はエラーや警告を出さず、上記の既定幅へ戻る。設定値と画像サイズに応じて `Np` が増えるため、score バッファの確保量も増え得る（`tools/vision/own/vit_gpu.cu:470-472,797-802,815-825`; `tools/vision/own/vit_metal.mm:119-121,259-261,273-280`）。

## 有効になる条件

- own vision tower の GPU 実装が使われること。CUDA/HIP build は `vit_gpu.cu`、Metal build は macOS の `vit_metal.mm` を使う。CPU 経路では `VitGpu::load` を通らず、この変数は参照されない（`tools/vision/own/CMakeLists.txt:120-164`; `tools/vision/own/own_reader.cpp:114-149`）。
- 独自 tower が選ばれ、対象モデルの GPU tower がサポートされていること。own reader の GPU load 成功後にだけ、この値はその tower の計算へ反映される。load 失敗や own tower を使わない経路では適用されない（`tools/vision/own/own_reader.cpp:49-72,114-125`）。
- `STRATA_VIT_QALIGN` は別に読み取られ、attention query chunk の丸め幅を制御する。`STRATA_VIT_NPAD` は score 行の幅、`STRATA_VIT_QALIGN` は query chunk 数に適用されるため、片方の値がもう片方を上書きする関係ではない（`tools/vision/own/vit_gpu.cu:1006-1007,1076-1079`; `tools/vision/own/vit_metal.mm:470-471,542-545`）。
- HIP の fused attention (`m.fa`) が選ばれた場合、通常の score GEMM / softmax ループは使われず `Np` に基づく QC も使わない。ただし `size_buffers` は score buffer `d_S` を確保するため、NPAD はその確保量の計算には残る（`tools/vision/own/vit_gpu.cu:797-825,1076-1105`）。

## 実行時の詳細

値は GPU tower の `VitGpu::load` 中、重みを読み込んだ後に一度だけ取得し、`VitGpuImpl::n_pad` に保存する。Metal も同様に load 時に `m.n_pad` へ保存する。初期バッファ確保・warm-up より前に設定される。その後の encode は保存済み値で `Np` を計算し、大きな画像でバッファを拡張するときも同じ値を使う。画像ごと、リクエストごとに環境を再読込するコードはなく、プロセス稼働中に環境値を変えても既にロード済み tower には反映されない（`tools/vision/own/vit_gpu.cu:895-908,1006-1008`; `tools/vision/own/vit_metal.mm:466-473`; `tools/vision/own/own_reader.cpp:120-125,151-169,171-194`）。

既定では `n_pad=0` がサイズ別ルールを選ぶ印であり、`N <= 16384` は 8、`N > 16384` は 64 へ丸める。採用された環境値があると、この大小条件にかかわらず指定幅を使う。`Np` は score tensor の leading dimension になり、行ごとの score/probability 領域の stride と容量に反映される。attention query chunk の大きさは別途 score memory budget などから決まり、`STRATA_VIT_QALIGN` が設定されている場合はその値でも整列される（`tools/vision/own/vit_gpu.cu:470-472,797-803,1076-1079`; `tools/vision/own/vit_metal.mm:119-121,259-262,542-550`）。

環境変数を設定したこと自体を示すログはない。必要な GPU work buffer が確保できず tower load が失敗すると、own reader は起動エラーを返し、通常のプロトコルでは `ERR cannot load the vision encoder <mmproj> (<error>)` を stdout に出す。own reader が `auto` 選択から起動された場合は、その失敗理由を呼び出し元に返して mtmd reader へ移る経路がある（`tools/vision/own/own_reader.cpp:89-100,120-125`; `tools/vision/own/vit_gpu.cu:815-825`; `tools/vision/own/vit_metal.mm:273-280`）。

## ログと測定値

NPAD の有効・無効や採用値を表示する専用ログはない。無効値についても警告はなく、既定の丸め規則を使う。score buffer の確保失敗時、CUDA/HIP では大きな score budget から既定の小さい budget へ再試行する経路があり、それでも確保できなければ load 失敗となる。Metal でも大きい budget の確保失敗時に小さい budget を試し、再度失敗すると load 失敗になる（`tools/vision/own/vit_gpu.cu:815-825`; `tools/vision/own/vit_metal.mm:273-280`）。

`docs/DETAILS.md` の vision 設定表には NPAD の説明や、この変数の測定値は記載されていない（`docs/DETAILS.md:984-1016`）。ソース内コメントは NPAD と QALIGN を診断用と呼び、両方を設定する旨を記すが、上記の値の判定と反映は実コードに基づく（`tools/vision/own/vit_gpu.cu:465-472`）。この調査では build、GPU 実行、性能測定は行っていない。

## 根拠

- 候補一覧の名前: `docs/envvars/000_envvers.md:2245`。
- 全ての実コード読み取り箇所: `tools/vision/own/vit_gpu.cu:1006`; `tools/vision/own/vit_metal.mm:470`。
- デフォルト幅・丸め式: `tools/vision/own/vit_gpu.cu:469-472`; `tools/vision/own/vit_metal.mm:118-121`。
- buffer サイズと attention stride: `tools/vision/own/vit_gpu.cu:780-825,1074-1115`; `tools/vision/own/vit_metal.mm:251-280,542-566`。
- backend の build 条件: `tools/vision/own/CMakeLists.txt:13-70,120-164`。
