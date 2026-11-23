# `STRATA_RDNA_Q80_WMMA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

この変数は Q8_0 重みと Q8_1 入力の MMVQ に使う RDNA Wave32 WMMA 経路を止めるロールバック用スイッチです。`rdna_q80_wmma_mmvq` は値が `0` で始まる場合に `false` を返し、呼び出し元 `native_q8_0_mmvq` は通常の `small_mmvq<Q80Block, 8>` に進みます。それ以外の値は WMMA 経路を明示的に有効化する値として parse されるのではなく、このスイッチでは停止させません。経路は `ncols >= 8` の Q8_0 MMVQ 呼び出しから試されます（`engine/src/kernels/cuda/rdna_mmvq.cu:467-481`, `engine/src/kernels/cuda/native_mmvq.cu:3699-3703`）。

## 値と判定

`std::getenv` の返す文字列について、未設定かどうかと先頭 1 文字だけを見ます。設定値が空文字なら `v != nullptr` かつ `v[0] == '\0'` なので停止しません。文字列全体の比較、数値変換、大文字小文字変換、空白除去はありません（`engine/src/kernels/cuda/rdna_mmvq.cu:469-473`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| HIP AMD build（`STRATA_HIP_GFX906` を除く）で、RDNA Q6K 経路のゲートを通過 | この変数は WMMA 経路を止めない | 先頭が `0` 以外（例: `1`, `true`, `false`, 空文字, ` 0`） | `0`, `00`, `0anything`（先頭文字が `0`） |
| NVIDIA CUDA build、`STRATA_HIP_GFX906` build | 対象関数は常に `false` stub で、この変数は読まれない | 該当なし | 該当なし |

表の「有効」はこの変数が経路を止めないという意味であり、カーネル実行には下記条件も必要です。関連する外側のゲート `rdna_q6k_enabled()` は `STRATA_RDNA_Q6K` が設定済みならその先頭文字が `1` の場合だけ有効となり、そうでない場合に限り `STRATA_HIP_FAST_DEC` の先頭文字が `1` なら GPU 世代判定へ進みます。`STRATA_RDNA_Q6K` が設定されていて先頭が `1` 以外なら、`STRATA_HIP_FAST_DEC` が `1` でもゲートは無効です（`engine/src/kernels/cuda/rdna_mmvq.cu:377-385`）。

## 有効になる条件

- ソースは `engine/cmake/strata_gpu_engine.cmake:97-111` で共有 GPU kernel 群に含まれ、HIP build では HIP 用 WMMA 実装も追加されます。ただしこのファイルの本体は `__HIP_PLATFORM_AMD__` かつ `!STRATA_HIP_GFX906` の条件内にあり、それ以外の build は `false` stub です（`engine/src/kernels/cuda/rdna_mmvq.cu:20-23, 36-37, 484-492`）。
- `rdna_q6k_enabled()` が true であることが必要です。`STRATA_RDNA_Q6K` / `STRATA_HIP_FAST_DEC` の判定は上記のとおりです（`engine/src/kernels/cuda/rdna_mmvq.cu:377-385, 467-468`）。
- `ncols` は 8〜16、`n_in` は 32 の倍数、`n_out` は 64 以上である必要があります。満たさない場合はこの関数が `false` を返し、呼び出し元が通常の small MMVQ に進みます（`engine/src/kernels/cuda/rdna_mmvq.cu:474`, `engine/src/kernels/cuda/native_mmvq.cu:3702-3703`）。
- `arch_is_gfx11_wmma()` が true ならこのファイル内の直接 WMMA kernel を起動します。false のときは `hip_unsloth_wmma_q80_mmvq` に委譲します。同 helper はポインタ、正の `n_in` / `n_out`、`n_in % 32 == 0`、`1 <= ncols <= 16`、WMMA 対応 device を確認し、条件不成立または起動エラーなら false を返します（`engine/src/kernels/cuda/rdna_mmvq.cu:364-373, 475-480`; `engine/src/kernels/hip/hip_unsloth_wmma.cu:763-773`）。
- 呼び出し元では `q8_packed_mmvq` が先に成功するとこの判定自体に到達しません（`engine/src/kernels/cuda/native_mmvq.cu:3699-3703`）。

## 実行時の詳細

`native_q8_0_mmvq` はまず packed Q8 経路を試し、次に `ncols >= 8` のときだけ `rdna_q80_wmma_mmvq` を呼びます。RDNA Q6K ゲートが無効、対象変数の先頭が `0`、形状条件不成立、または HIP helper が利用不可なら、`rdna_q80_wmma_mmvq` は false となり、呼び出し元は `small_mmvq<Q80Block, 8>` を実行します。対象変数による分岐はこの経路の選択であり、別の Q8_0 計算経路を変更しません（`engine/src/kernels/cuda/native_mmvq.cu:3699-3703`, `engine/src/kernels/cuda/rdna_mmvq.cu:467-481`）。

変数は `rdna_q80_wmma_mmvq` 内の関数ローカル `static const bool` で、RDNA Q6K ゲートを通った後の初回呼び出し時に一度だけ読み取られます。その結果はプロセス内で cache され、後続の呼び出しでは環境の変更を再読しません。ゲートが通らない呼び出しでは static 初期化・読み取りに到達しません（`engine/src/kernels/cuda/rdna_mmvq.cu:467-474`）。

直接 kernel を起動した後、呼び出し元の `launch_check()` が CUDA/HIP runtime の最終エラーを検査し、失敗時は `native MMVQ launch: ` に runtime のエラー文字列を続けた `std::runtime_error` を送出します。変数の値を理由とする専用ログや警告はありません（`engine/src/kernels/cuda/native_mmvq.cu:2491-2495, 3702`）。

## ログと測定値

この変数の読み取りや WMMA 経路の選択を記録するログはありません。kernel 起動のエラーは上記 `launch_check()` の例外として観測できます。確認した Strata 資料には、この変数による性能差を条件付きで示す測定値がないため、性能値は記載しません。

## 根拠

- `engine/src/kernels/cuda/rdna_mmvq.cu:20-23, 36-37, 267-273, 364-385, 467-492`
- `engine/src/kernels/cuda/native_mmvq.cu:2491-2495, 3699-3703`
- `engine/src/kernels/hip/hip_unsloth_wmma.cu:763-773`
- `engine/cmake/strata_gpu_engine.cmake:97-111`

参考: Strata の `docs/SETTINGS.md:292` は本変数の対象欄を “NVIDIA and AMD” としていますが、対象変数の読み取りを含む実装は上記の AMD HIP 条件内にあり、NVIDIA/CUDA 側は stub です。この文書の適用範囲は実装に従っています。
