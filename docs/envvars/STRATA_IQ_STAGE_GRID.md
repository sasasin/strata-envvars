# `STRATA_IQ_STAGE_GRID`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP と SYCL の IQ kernel 実装で、対象の i-quant codebook/grid を shared/local memory に staging する経路を有効にする。未設定を含む既定は有効で、`0` で staging を止める。これは kernel 選択・メモリー配置の切替であり、環境変数を読むコードにはモデル出力や計算結果を別の値にする処理はない。CUDA/HIP 実装は `engine/src/kernels/cuda/iq_kernels.cu`、SYCL 実装は `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp` にある（後者は SYCL CMake target に登録されている）。[engine/src/kernels/cuda/iq_kernels.cu:995-995,3696-3707,3791-3804,4541-4571](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu) [engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:44](../../../../Niko1221/Strata/engine/sycl/CMakeLists.txt) [engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:1251,3954-3966,4219-4227,6053-6067](../../../../Niko1221/Strata/engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp)

CUDA/HIP 側で compile-time の対象になる format は type 16, 17, 18, 21, 22, 29 と trellis type 144-146。SYCL 側は type 16, 17, 22, 29。対象外の format にはこの staging 分岐を適用しない。CUDA/HIP 側の grouped gate/up 経路では `STRATA_OLD_IQ_MMVQ` や format ごとの split 設定によって旧 kernel が選ばれる場合があり、SYCL grouped gate/up では `STRATA_EXPERT_SPLIT` が有効でない場合にこの staging 分岐へ進まない。単一 matrix-vector/matrix-matrix (MMVQ) 側は両実装とも、対象 format について別の `STRATA_IQ_STAGE_GRID_MMVQ=1` がなければ staging しない。[engine/src/kernels/cuda/iq_kernels.cu:990-995,3791-3804,4541-4567](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu) [engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:1251,3931-3938,4219-4227,6053-6067](../../../../Niko1221/Strata/engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp)

## 値と判定

両 backend は `std::getenv` で読み、数値変換や文字列全体の比較はしない。未設定なら有効。設定済みの場合は先頭 byte が `'0'` なら無効、それ以外は有効。空文字も有効である。したがって `0`, `0anything`, `00` は無効、`1`, `true`, `false`, `anything`, ` 0` は有効。大文字小文字・空白・数値としての妥当性を検査しない。負数 `-1` も先頭が `'-'` のため有効。[engine/src/kernels/cuda/iq_kernels.cu:3696-3700](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu) [engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3954-3959](../../../../Niko1221/Strata/engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp)

| 条件（build/backend） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP `iq_kernels.cu` | 有効 | 空文字、`1`、`true`、`-1`、` 0` | `0`、`0anything` |
| SYCL `iq_kernels.dp.cpp` | 有効 | 空文字、`1`、`true`、`-1`、` 0` | `0`、`0anything` |

## 有効になる条件

- 対象 backend の IQ kernel 実装が build に含まれ、実行経路が対象 format の該当 kernel に到達する必要がある。これは CLI 専用設定ではなく kernel 内の process environment 設定である。[engine/sycl/CMakeLists.txt:44](../../../../Niko1221/Strata/engine/sycl/CMakeLists.txt)
- CUDA/HIP の grouped gate/up では `launch_gu` が split IQ format の multi kernel を選ぶことが条件。旧 kernel が選択される場合は staging しない。type 18 と 21 の staging には別途 `STRATA_IQ_STAGE_TABLES` が必要で、trellis type 144-146 には `tq_stage_on()` / `tq_sub8_on()` の条件もある。[engine/src/kernels/cuda/iq_kernels.cu:3713-3744,3746-3761,4541-4571](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)
- SYCL の grouped gate/up は split multi 経路（`STRATA_EXPERT_SPLIT` が on で、旧 kernel が選ばれない経路）で対象 type の staging に分岐する。対象 format は IQ type 16, 17, 22, 29。[engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:1251,3933-3938,6053-6067](../../../../Niko1221/Strata/engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp)
- CUDA/HIP と SYCL の MMVQ では `STRATA_IQ_STAGE_GRID_MMVQ` の先頭 byte が `'1'` の場合だけ、この変数が有効であることを前提に staged kernel を選ぶ。`STRATA_IQ_STAGE_GRID=0` のときはこの別設定も効かない。[engine/src/kernels/cuda/iq_kernels.cu:3701-3707,3791-3804](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu) [engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3960-3966,4219-4227](../../../../Niko1221/Strata/engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp)
- CUDA/HIP trellis staging は `tq_stage_on()` が HIP では false を返すため、`STRATA_IQ_STAGE_GRID` だけでは有効にならない。CUDA でも別の `STRATA_TQ_STAGE`、GPU compute capability などにより staging の有無が決まる。[engine/src/kernels/cuda/iq_kernels.cu:3726-3744,3746-3761](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu)
- 検索した直接読み取り箇所は CUDA/HIP と SYCL の二つで、環境値の CLI 引数・設定ファイルによる上書き、起動ラッパーからの値の書き換えは見つからなかった。

## 実行時の詳細

各 translation unit の namespace-scope `bool` の dynamic initialization 時に一度読み、結果を `g_stage_grid` に保持する。`g_stage_grid_mmvq` もその値を使って同時に初期化される。関数ごとの再読込やリクエストごとの評価ではないので、プロセス内で後から環境を変更してもこの判定には反映されない。別プロセスとして起動した場合は、そのプロセスの環境から評価される。[engine/src/kernels/cuda/iq_kernels.cu:3696-3707](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu) [engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3954-3966](../../../../Niko1221/Strata/engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp)

既定有効のとき、CUDA/HIP の grouped gate/up launcher は対象 format で staged template を選ぶ。ただし IQ3_XXS / IQ3_S (type 18 / 21) は `stage_tables_on()` が別途 true でないと staging を行わず、trellis formats は `tq_stage_on()` 条件に従う。SYCL の grouped gate/up launcher も対象 type で `launch_gu_multi<TG, true>` を呼ぶ。MMVQ は別変数の opt-in がない限り、`STAGE_GRID=false` の multi kernel に進む。いずれも環境変数による kernel/staging 選択で、該当コードに値を変換する補正処理は見当たらない。[engine/src/kernels/cuda/iq_kernels.cu:3791-3804,4550-4567](../../../../Niko1221/Strata/engine/src/kernels/cuda/iq_kernels.cu) [engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4219-4227,6053-6067](../../../../Niko1221/Strata/engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp)

## ログと測定値

この変数を読み取る箇所や分岐には、値の有効・無効を示すログ、警告、エラー出力がない。資料では CUDA の Gyro trellis decode について RTX 3060 (12 GB) で Gyro-S 54.3→62.5 tokens/s (+15%)、Gyro-M 50.2→54.8 (+9%)、各 5 interleaved pairs と記載し、`STRATA_IQ_STAGE_GRID=0` で旧 lookup に戻るとしている。他世代のカードは未測定と明記されている。これは当該リリース資料の値であり、一般的な性能保証ではない。[docs/release-notes-0.2.2.md:9](../../../../Niko1221/Strata/docs/release-notes-0.2.2.md)

## 根拠

- `engine/src/kernels/cuda/iq_kernels.cu:995-995,3696-3707,3791-3804,4541-4571` — CUDA/HIP format 範囲、env parse、MMVQ と grouped gate/up 分岐。
- `engine/src/kernels/cuda/iq_kernels.cu:3713-3761` — 他の stage env と HIP / CUDA trellis 条件。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:1251,3954-3966,4219-4227,6053-6067` — SYCL format 範囲、env parse、MMVQ と grouped gate/up 分岐。
- `engine/sycl/CMakeLists.txt:44` — SYCL target への kernel source 登録。
- `docs/release-notes-0.2.2.md:9` — 条件付きの Gyro 測定記録。
