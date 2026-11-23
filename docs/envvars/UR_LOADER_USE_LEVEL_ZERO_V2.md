# `UR_LOADER_USE_LEVEL_ZERO_V2`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata がこの変数の値を機能設定として解釈する実装はない。確認できた2つのSYCL実装は、プロセス環境にこの名前が存在しない場合だけ `"0"` を設定し、明示された値を保持する。コメントにはoneMKLとLevel Zero V2 adapterの組み合わせで発生したSIGSEGVへの回避策と記されているが、Strataが行うのは既定値の設定までであり、adapterの動作や回避効果は本書の対象外である（`engine/src/hy4flash/sycl/sy_main.cpp:79-84`、`engine/src/inkling2/sycl/ink_sy_common.h:63-69`）。

この処理があるのは、独立ビルドのHy4 SYCL runner `strata-hy4-sycl` と、Inkling2のSYCL backendである。CUDA/HIP/Metal版や他backendについて、この処理は確認できない（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:1-6,62-68`、`engine/src/inkling2/CMakeLists.txt:206-207`）。

## 値と判定

両実装とも `std::getenv` の戻り値が null かどうかだけを判定し、値の変換や検証はしない。unsetなら `"0"` を設定し、設定済みならその値を変更しない。したがって空文字も「設定済み」であり保持される。`0`、`1`、`true`、`false`、大文字小文字、空白、数値としての妥当性にStrata独自の判定はない。設定済みの文字列は、その内容にかかわらずStrataからそのまま残される（`engine/src/hy4flash/sycl/sy_main.cpp:82-84`、`engine/src/hy4flash/sycl/sy_common.h:33-39`、`engine/src/inkling2/sycl/ink_sy_common.h:46-52,65-68`）。

| 実装経路 | unset | 設定時に保持される値 | Strataが無効と判定する値 |
|---|---|---|---|
| Hy4 SYCL runner | `"0"` を設定 | 空文字、`0`、`1`、`true`、その他すべて | なし。値の判定なし |
| Inkling2 SYCL backend | `"0"` を設定 | 空文字、`0`、`1`、`true`、その他すべて | なし。値の判定なし |

POSIXでは `setenv(name, "0", 0)` を呼ぶ。Windows分岐ではunsetを確認してから `_putenv_s(name, "0")` を呼ぶ。いずれも設定済み値を上書きしない（`engine/src/hy4flash/sycl/sy_common.h:33-39`、`engine/src/inkling2/sycl/ink_sy_common.h:46-52`）。

## 有効になる条件

- Hy4では `engine/src/hy4flash/sycl/build_hy4_sycl.sh` でビルドするSYCL実行ファイルが対象。`main` 冒頭で設定有無を確認するため、`--serve`、通常実行、`--info`、`--version` 等のCLI分岐より前に処理される（`engine/src/hy4flash/sycl/sy_main.cpp:79-84,105-123`）。
- Inkling2ではSYCLソースが組み込まれたbackendが対象。CMakeは `STRATA_ENABLE_SYCL` が有効な場合にSYCL subdirectoryを追加する（`engine/src/inkling2/CMakeLists.txt:206-207`）。backendの早期初期化関数（GNU/Clangではconstructor priority 101）と初期化guard、実行時の `main`、GPU選択・列挙・queue初期化経路から同じ設定関数が呼ばれる（`engine/src/inkling2/sycl/ink_sycl_backend.cpp:18-28,65-70,94`、`engine/src/inkling2/sycl/ink_sy_main.cpp:101-103`、`engine/src/inkling2/sycl/ink_sy_common.h:82-99,119-127`）。
- CLI引数や別のStrata環境変数による上書き・優先順位はない。対象変数が既に設定されているとStrataは値を保持し、未設定時にだけ既定値を追加する。
- Strataのソースは設定値自体を読み取って分岐しないため、どの設定値が外部runtimeで有効になるかはここからは説明できない。

## 実行時の詳細

Hy4は `main` の最初で確認し、未設定なら `hy4s_setenv(..., "0", 0)` を呼ぶ。よって同バイナリのCLI処理や後続のSYCL処理より前に実行される（`engine/src/hy4flash/sycl/sy_main.cpp:79-84`）。

Inkling2はbackend初期化時に早期関数・guardから確認し、さらに実行時の `main`、`apply_gpu_index`、`enum_gpu_devices`、queue生成経路でも確認する。確認のたびに `getenv` を行い、static cacheは使わない。Strata自身がこの値を後から読み直して別の状態を計算する処理は見つからなかった（`engine/src/inkling2/sycl/ink_sycl_backend.cpp:18-28`、`engine/src/inkling2/sycl/ink_sy_main.cpp:101-103`、`engine/src/inkling2/sycl/ink_sy_common.h:65-99,119-127`）。

環境設定関数の戻り値は呼び出し側で確認されず、この処理に対応するログ、警告、エラー出力もない。設定に失敗した場合のStrata側の追加処理は確認できない（`engine/src/hy4flash/sycl/sy_common.h:33-39`、`engine/src/inkling2/sycl/ink_sy_common.h:46-52,65-68`）。

## 根拠

- Hy4の確認と既定値設定、CLIより前の位置: `engine/src/hy4flash/sycl/sy_main.cpp:79-84,105-123`
- Hy4のPOSIX/Windows環境設定helper: `engine/src/hy4flash/sycl/sy_common.h:33-39`
- Inkling2の値確認helper: `engine/src/inkling2/sycl/ink_sy_common.h:46-52,63-69`
- Inkling2の早期初期化とbackend初期化: `engine/src/inkling2/sycl/ink_sycl_backend.cpp:18-28,65-70,94`
- Inkling2のGPU選択、列挙、queue生成: `engine/src/inkling2/sycl/ink_sy_common.h:82-99,119-127`
- Inkling2のSYCL backend追加条件: `engine/src/inkling2/CMakeLists.txt:206-207`
- Hy4 SYCL runnerのビルドスクリプト: `engine/src/hy4flash/sycl/build_hy4_sycl.sh:1-6,62-68`
