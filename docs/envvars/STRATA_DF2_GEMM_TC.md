# `STRATA_DF2_GEMM_TC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA 版 DFlash2 の GEMM で、条件を満たした場合に tensor-core 用 `gemm_tc_kernel` を選ぶための opt-in フラグです。Q4_0 と Q8_0 の双方で使われ、通常の GEMM 経路を置き換えます。DFlash2 の他の処理や、条件外の GEMM を直接切り替える変数ではありません。実装は `df2_gemm` です（`engine/src/kernels/cuda/dflash2.cu:1836-1858`）。

## 値と判定

`std::getenv` で値を取得し、未設定、空文字、または先頭文字が `'0'` なら false、それ以外の非空文字列なら true とします。数値や真偽値として文字列全体を parse せず、空白除去・大文字小文字変換・妥当性検査もありません（`engine/src/kernels/cuda/dflash2.cu:1837-1840`）。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA（`__HIPCC__` 未定義） | OFF | `1`、`true`、`false`、` 0`、`00x` など、空でなく先頭が `0` 以外の値 | 空文字、`0`、`0anything` など先頭が `0` の値 |
| HIP（`__HIPCC__` 定義） | 判定コードがコンパイル対象外 | 該当なし | 該当なし |

この表の有効・無効はフラグ自体の判定です。CUDA で ON と判定されても、下記の capability と GEMM 条件が揃わなければ tensor-core 経路には入りません。HIP ビルドではこの変数を読みません（`engine/src/kernels/cuda/dflash2.cu:1836-1858`）。

## 有効になる条件

CUDA ビルドでこのフラグが ON であり、さらに次の条件をすべて満たす必要があります。

- デバイス取得と compute capability の取得に成功し、major が 8 以上であること。失敗時は CUDA エラー状態を `cudaGetLastError()` で取得・消去して false とし、通常 GEMM に進みます（`engine/src/kernels/cuda/dflash2.cu:1840-1847`）。
- GEMM が `ncols` 1〜8 の経路であること。`ncols > 8` では先に独立した batch tensor-core 経路を試し、条件に合わなければ 8 列以下に分割して再帰呼び出しします（`engine/src/kernels/cuda/dflash2.cu:1801-1835`）。分割後の呼び出しではこのフラグによる判定が適用されます。
- `g_gemm_variant == 0`、`ncols >= 2`、`rows >= 1024`、かつ `rows` が 16 の倍数であること（`engine/src/kernels/cuda/dflash2.cu:1848`）。`g_gemm_variant` はベンチ用 API から設定される値で、通常は 0 です（`engine/src/kernels/cuda/dflash2.cu:1762-1763`; `engine/include/strata/kernels/dflash2.hpp:53,61-68`）。

DFlash2 の GEMM 自体は CUDA/HIP GPU エンジンに含まれますが、この環境変数の判定部は HIP コンパイル時に除外され、Metal と SYCL は DFlash2 実装を含みません（`engine/cmake/strata_gpu_engine.cmake:8-13`; `engine/src/kernels/cuda/dflash2.cu:9-13,1836-1858`）。`docs/SETTINGS.md:57` は適用先を「NVIDIA and AMD」としていますが、当該コードでは HIP 側が除外されるため、その記載と実装の適用範囲は一致しません。

## 実行時の詳細

`df2_gemm` の関数内 `static const bool` を初めて初期化するときに値を読み、同時に現在の CUDA デバイスの compute capability を調べます。その結果はプロセス内で一度だけキャッシュされるため、その後の環境変数変更や別 GPU への切り替えでは再評価されません。判定が true で GEMM 条件も満たす場合、Q4_0 は `gemm_tc_kernel<true>`、Q8_0 は `gemm_tc_kernel<false>` を起動して戻ります。それ以外は既存の Q4_0 / Q8_0 GEMM 経路を続けます（`engine/src/kernels/cuda/dflash2.cu:1837-1860,1908-1941`）。

通常の DFlash2 推論では `Dflash2Drafter::gemm` が行列情報をまとめて `kernels::df2_gemm` に渡します。たとえば KV 更新時には K/V 投影の GEMM がこの経路を通ります（`engine/src/core/dflash2.cpp:480-503`）。この関数には同名の CLI 引数や別の設定値との優先順位を決める処理はなく、static 初期化時にプロセス環境にある値を読みます。GEMM の入力は別途 `n_in` が 512 の倍数、各行列の `n_out` が 16 の倍数、行列数が 1〜3、全行列の量子化形式が一致する必要があり、違反は `std::invalid_argument` になります（`engine/src/kernels/cuda/dflash2.cu:1787-1797`）。Terminal の `strata launch --set NAME=value` は設定をモデルの run configuration に置くと説明されていますが、その設定値とプロセス環境の競合時の優先順位は、この GEMM 実装からは確認できません（`docs/SETTINGS.md:10-11`; `engine/src/kernels/cuda/dflash2.cu:1837-1847`）。なお、`ncols > 8` で使われる batch tensor-core 判定は別の関数内 static 判定であり、この変数に依存しません（`engine/src/kernels/cuda/dflash2.cu:1801-1823`）。

## ログと測定値

このフラグの値や選択結果を示すログはありません。対象 GEMM の起動後に `cudaGetLastError()` が失敗を返した場合は、`stderr` に `dflash2 kernel gemm4_tc: <CUDA error string>` または `dflash2 kernel gemm8_tc: <CUDA error string>` を出し、例外を送出します。通常 GEMM でも対応する `gemm4` / `gemm8` 名で同じ形式のエラーを報告します（`engine/src/kernels/cuda/dflash2.cu:29-35,1848-1858,1900-1941`）。この環境変数による性能値は、参照したソース・設計資料では確認できません。

## 根拠

- `engine/src/kernels/cuda/dflash2.cu:1801-1858` — 列数分岐、環境変数判定、capability 条件、tensor-core kernel 選択。
- `engine/src/kernels/cuda/dflash2.cu:29-35,1900-1941` — 起動エラーのログ・例外と通常 GEMM 経路。
- `engine/src/core/dflash2.cpp:480-503` — DFlash2 drafter から GEMM への呼び出し。
- `engine/cmake/strata_gpu_engine.cmake:8-13,97` — DFlash2 実装を含むビルド範囲。
- `docs/SETTINGS.md:57` — 適用先についての既存説明（コード上の HIP 除外と不一致）。
