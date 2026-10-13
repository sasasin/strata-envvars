# `STRATA_FUSE_WAIT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

HIP ビルドの verifier が、ホスト側の完了フラグを待つ処理と、その後の mapped host memory のコピーを一つの GPU kernel launch にまとめるかを制御する。verifier の計算値を変える設定ではなく、別々の待機・コピー launch を一つにする実行経路の選択である。CUDA ビルドでは常に無効で、この環境変数は参照されない。

## 値と判定

HIP ビルドで `fuse_wait_on()` が最初に呼ばれたときに `std::atoi` で一度だけ読み取り、結果を static に保持する（`src/core/verify.cpp:229-235`）。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 自動判定。現在の GPU が gfx1200 または gfx1201 なら有効、それ以外は無効（`src/core/verify.cpp:236-243`; `include/strata/kernels/gfx_arch.hpp:36`）。 |
| `0`、空文字、整数として 0 になる文字列 | 無効。 |
| 整数として 0 以外になる文字列（負数を含む） | 有効。 |

数値以外で始まる文字列や空文字は `atoi` が 0 と判定する。範囲検査やエラー報告はない。明示値がある場合は GPU 世代による自動判定を上書きする。起動後に値を変更しても、static 初期化済みの判定には反映されない。未設定時の GPU 判定は device ごとの static 配列に保持される。device 番号が取得できない、範囲外、またはプロパティ取得に失敗した場合は無効となる。

## 有効になる条件

- `src/core/verify.cpp` が `STRATA_USE_HIP` でコンパイルされた HIP ビルドでのみ、環境変数を読み自動判定を行う。HIP build の定義は `cmake/hip_backend.cmake:85-89` にある。
- CUDA など `STRATA_USE_HIP` が未定義のビルドでは `fuse_wait_on()` は常に `false` を返す（`src/core/verify.cpp:244-246`）。
- verifier の通常の CPU-planned 経路では、ホスト側が公開した GPU plan を待って plan 配列をコピーする処理を統合できる（`src/core/verify.cpp:1595-1605`）。ただし `device_plan_` 経路は別の wait/copy 関数を使うため対象外。
- verifier の CPU 行を mapped memory から取り込む経路では、`dec_batch` が真、profiling が無効、`remote_opt_` が null の場合に待機と行コピーを統合する（`src/core/verify.cpp:1622-1639`）。`device_plan_` 経路は対象外。
- profiling (`prof_on_`) 中は両方の統合経路を使わず、従来の独立した wait と copy に戻る（`src/core/verify.cpp:711-712,1599-1604,1627-1639`）。

## 実行時の詳細

plan のコピーでは、`wait_copy_i32_from_mapped` が一つの block の thread 0 で mapped flag が指定値以上になるまで待ち、system fence の後に plan 配列をコピーする。従来の `wait_flag_ge` と `copy_i32_from_mapped` の二つの launch を置き換える（`src/core/verify.cpp:1595-1605`; `src/kernels/cuda/verify_kernels.cu:1277-1292`; 宣言 `include/strata/kernels/verify_kernels.hpp:46-53`）。

CPU 行のコピーでは、各 row block が mapped flag を待ってから hit row の一覧を参照する。GPU が既に計算した hit row は +0.0 にし、それ以外は mapped host memory からコピーする。従来の独立した `wait_flag_ge` launch をコピー kernel にまとめる（`src/core/verify.cpp:1627-1639`; `src/kernels/cuda/elementwise.cu:236-260,289-298`; 宣言 `include/strata/kernels/elementwise.hpp:105-114`）。

実装コメントは gfx1201 の graph で依存 kernel node 一つのコストを約 2.4 μs と記し、この統合により各箇所で launch/node を一つ減らす設計を説明している（`src/core/verify.cpp:225-228`; `include/strata/kernels/verify_kernels.hpp:49-52`; `include/strata/kernels/elementwise.hpp:111-114`）。これはコメントに記された条件の測定値であり、一般的な性能向上を示すものではない。環境変数自体についての追加説明は `docs/DETAILS.md` では確認できなかった。ログ出力や、値が不正な場合の警告・エラー処理はこの実装箇所にはない。

## 根拠

- 値の読み取り、HIP 限定、未設定時の per-device 判定: `src/core/verify.cpp:225-246`。
- gfx12 判定対象（gfx1200 / gfx1201）: `include/strata/kernels/gfx_arch.hpp:30-36`。
- HIP compile definition: `cmake/hip_backend.cmake:85-89`。
- verifier の plan wait/copy と CPU 行 wait/copy の分岐: `src/core/verify.cpp:1595-1605,1622-1639`。
- 統合 kernel の処理: `src/kernels/cuda/verify_kernels.cu:1277-1292`, `src/kernels/cuda/elementwise.cu:236-260,289-298`。
