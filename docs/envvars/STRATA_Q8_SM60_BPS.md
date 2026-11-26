# `STRATA_Q8_SM60_BPS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Q8 SM60 decode kernel の CUDA launch grid を決める「SM あたりの block 数」を上書きする。各 launch の grid は `min(出力行グループ数, SM 数 × この値)` となる。対象は Q8_0 の native decode MMVQ のうち、SM60 用 kernel に到達した行列だけであり、モデルの量子化形式、Q8_0 の値、出力の選択そのものを切り替える設定ではない（`engine/src/kernels/cuda/q8_sm60.cuh:108-115,184-191`、呼び出しは `engine/src/kernels/cuda/native_mmvq.cu:2767-2787,3699-3704`）。

この変数単独では kernel を有効にしない。通常は別変数 `STRATA_Q8_SM60=1` が必要で、CUDA の native Q8_0 decode 経路に対象行列の packed plane が登録されているときに参照される（`engine/src/kernels/cuda/native_mmvq.cu:2623-2636,2770-2787`）。

## 値と判定

`std::getenv` の戻り値を `std::atoi` に渡し、結果が正 (`> 0`) のときだけ採用する。数値文字列全体の妥当性検査、上限 clamp、警告はない。`atoi` の変換なので、たとえば `3tail` は `3` として、`0tail` は `0` として扱われる。先頭空白や符号も `atoi` の変換規則に従う。数値に変換できない文字列と空文字は `0` となる。`atoi` で `int` の範囲に収まらない値の結果は C/C++ ライブラリの保証外であり、Strata 側の追加処理はない（`engine/src/kernels/cuda/q8_sm60.cuh:110-115`）。

| ビルド・実行経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA（非 HIP）で SM60 kernel が呼ばれる経路 | GPU の compute capability が 7.0 なら 6、それ以外なら 4。GPU 属性取得失敗・device index が 0〜63 の範囲外なら 4 | `atoi` の結果が正の整数となる値。例: `1`, `6`, `3tail` | `0`, `-1`, 空文字, `true`, `no`, `0tail` など、`atoi` の結果が 0 以下になる値。既定値へ戻る |
| HIP (`__HIPCC__`) | 4 | なし。この分岐では値を採用しない | すべて。常に 4 |

CUDA の既定値はデバイスごとの static cache に保存される。環境変数が正の値ならその値がデバイスに関係なく優先される。上限は `sm_count()` との積を通じて launch grid の出力行グループ数により抑えられるが、変数自体の clamp はない（`engine/src/kernels/cuda/q8_sm60.cuh:116-136,139-155,184-191`）。

## 有効になる条件

- Strata の CUDA engine 経路であること。HIP 互換ビルドでは `q8_sm60.cuh` の include と関連処理が除外される (`engine/src/kernels/cuda/native_mmvq.cu:2659-2661`)。
- Pascal / Volta 向けにビルドする場合は CUDA 12.x と `STRATA_EXPERIMENTAL_SM60=ON` が必要。CMake は compute capability 7.5 未満をこの build option なしでは拒否する (`engine/cmake/backends/cuda.cmake:28-57,76-80`)。
- `STRATA_Q8_SM60` が文字列全体として `"1"` であること。この値は初回参照時に static cache され、それ以外（未設定、空文字、`"01"`、`"1x"` など）は SM60 経路を有効にしない (`engine/src/kernels/cuda/native_mmvq.cu:2625-2636`)。
- Q8_0 行列が packed registry に登録され、`q8_packed_mmvq` が対応する pointer と shape を見つけること。SM60 mode では packed eligibility は `n_in >= 128`, `n_in % 32 == 0`, `n_out > 0` (`engine/src/kernels/cuda/native_mmvq.cu:2770-2783,2991-2995`)。dense 側は Q8_0 かつ PLE key tensor 以外などの条件を通って pack され、出力 head は Q8_0 の場合に別途 pack を試みる (`engine/src/core/native_dense.cpp:498-515`, `engine/src/core/native_head.cpp:261-265`)。
- `q8sm60::launch` が入力幅・列数・共有メモリ条件を満たすこと。`n_in` は 32 の倍数かつ 128 以上、`ncols` は 1〜8、必要共有メモリがデバイス上限以下である必要がある。条件を満たさない通常の packed copy は、SM60 launch を断念し、測定済み shape なら exact packed kernel、それ以外は caller の通常 kernel に戻る (`engine/src/kernels/cuda/q8_sm60.cuh:203-215`, `engine/src/kernels/cuda/native_mmvq.cu:2785-2796,2799-2832,3701-3704`)。in-place packed tensor が kernel に断られた場合は fallback せず `strata q8 inplace: q8sm60 declined in-place tensor ...` を出して abort する (`engine/src/kernels/cuda/native_mmvq.cu:2789-2793`)。
- MTP drafter の行列でこの設定を使うには、さらに `STRATA_MTP_Q8_SM60` が必要。`STRATA_Q8_SM60_BPS` は MTP 専用行列の pack を開始しない (`engine/src/core/mtp.cpp:106-115,490-508,996-1004`)。

## 実行時の詳細

`blocks_per_sm()` の最初の呼び出し時に環境を読み、その関数内 static `env` に保存する。したがってプロセス実行中に環境値を変更しても再読込されない。正の値ならただちに返し、未設定または無効値なら現在デバイスの compute capability を調べ、SM70 は 6、それ以外は 4 をデバイスごとに cache する。デバイス属性取得に失敗した場合も 4 を返す（`engine/src/kernels/cuda/q8_sm60.cuh:110-136`）。

その値は `launch_one` が出力行を `RPB = 256 / TPR` 行単位で処理する grid size を計算するときにだけ使われる。`TPR` は入力幅により 8 / 16 / 32 と変わり、grid は `min(ceil(n_out / RPB), sm_count × blocks_per_sm)`。kernel は grid stride で残りの group を処理する。つまり値を増やしても grid が必要 group 数を超えず、直接変えるのは並列 workgroup 数である（`engine/src/kernels/cuda/q8_sm60.cuh:71-76,184-199`）。

この変数を読むコードに CLI 引数・設定ファイルによる上書きや子プロセスへの転送はない。環境値は当該プロセス内で評価される。

## ログと測定値

`STRATA_Q8_SM60_BPS` の値を表示するログや、無効値への警告はない。SM60 経路を初回有効化すると `strata q8 sm60: Q8_0 decode GEMVs on the Pascal kernel (STRATA_Q8_SM60=1)` が stderr に出る。pack 成功時は `strata q8 sm60: packed ...`、VRAM 確保失敗や pack 同期失敗時は GGUF layout を保つ旨の stderr が出る（`engine/src/kernels/cuda/native_mmvq.cu:2629-2634,3050-3075`）。

`engine/src/kernels/cuda/q8_sm60.cuh:108-109` のコメントは Pascal で 4、80 SM の Volta で 6 blocks/SM が測定上よかったと述べる。これはソースコメントの記録であり、当該 commit の資料には `STRATA_Q8_SM60_BPS` 値ごとの測定条件・比較結果は見当たらない。`docs/OLDER_GPUS.md:155-163` は親機能 `STRATA_Q8_SM60=1` の Pascal 向け挙動を説明しているが、BPS の値規則は扱っていない。

## 根拠

- 直接の唯一の環境読み取りと判定・既定値・grid への反映: `engine/src/kernels/cuda/q8_sm60.cuh:108-136,184-215`。
- 親機能の有効条件、registry dispatch、fallback: `engine/src/kernels/cuda/native_mmvq.cu:2623-2636,2767-2802,2983-2995,3699-3704`。
- dense と output head の packed 登録経路: `engine/src/core/native_dense.cpp:498-515`, `engine/src/core/native_head.cpp:261-265`。
- MTP 専用経路の追加条件: `engine/src/core/mtp.cpp:106-115,490-508,996-1004`。
- CUDA の Pascal / Volta build 条件: `engine/cmake/backends/cuda.cmake:28-57,76-80`。
