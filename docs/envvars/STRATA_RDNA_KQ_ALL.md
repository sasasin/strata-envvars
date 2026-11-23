# `STRATA_RDNA_KQ_ALL`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

AMD RDNA 向け K-quant MMVQ のうち、Q4_K（type 12）と Q5_K（type 13）について、列数 `ncols` が 1〜3 の呼び出しでも専用 `rdna_kq_kernel` を試すための設定です。未設定ならこの小列数の専用経路は `false` を返し、呼び出し元が通常の `native_mmvq` カーネルへ進みます。4 列以上では変数の有無にかかわらず専用経路を試します。IQ4_XS（type 23）と IQ3_S（type 21）はこの変数による列数制限を受けません（`engine/src/kernels/cuda/rdna_mmvq.cu:391-429`; 呼び出し元 `engine/src/kernels/cuda/native_mmvq.cu:3311-3324,3518-3531,3559-3572,3801-3815`）。

## 値と判定

Q4_K/Q5_K で `ncols < 4` のときだけ `std::getenv("STRATA_RDNA_KQ_ALL") == nullptr` を判定します。未設定なら専用経路を拒否し、何らかの値が設定されていれば許可します。値の文字列・数値・真偽値としての parse はなく、空文字も設定済みです。したがって `1`、`0`、`false`、`true`、`0anything`、空文字はいずれも同じ扱いです。前後空白や大文字小文字も調べません。`ncols >= 4` の場合、この変数は判定に使われません（`engine/src/kernels/cuda/rdna_mmvq.cu:405-418`）。

| 条件 | unset | 設定ありの例 | 無効値の例 |
|---|---|---|---|
| Q4_K / Q5_K、`ncols` が 1〜3 | 専用 RDNA KQ 経路を拒否し `false` を返す | 空文字、`0`、`false` を含む任意の値で専用経路を試す | 値の無効判定はない |
| Q4_K / Q5_K、`ncols` が 4〜16 | この変数を参照せず専用経路を試す | 同左 | 同左 |
| IQ4_XS / IQ3_S | この変数を参照せず専用経路を試す | 同左 | 同左 |

## 有効になる条件

- AMD の wave32 HIP ビルドであること。ソースは `__HIP_PLATFORM_AMD__` が定義され、`STRATA_HIP_GFX906` が未定義の場合だけ RDNA カーネル本体をコンパイルし、それ以外のビルドでは同関数が常に `false` を返す stub です。したがって NVIDIA CUDA、gfx906 wave64、SYCL、Metal、CPU の実行経路ではこの変数は機能しません（`engine/src/kernels/cuda/rdna_mmvq.cu:20-23,36,484-493`; HIP backend の定義と gfx906 分離 `engine/CMakeLists.txt:91-104,233-241`）。
- `rdna_kq_mmvq2()` が使える状態、すなわち `rdna_q6k_enabled()` が true であることが必要です。同関数は `STRATA_RDNA_Q6K` が設定されていれば先頭文字が `'1'` の場合のみ有効値 1 とし、それ以外では 0 を返します。この変数が未設定の場合に限り `STRATA_HIP_FAST_DEC` を調べ、先頭文字が `'1'` なら値 2 とします。値 1 はアーキテクチャ確認を迂回し、値 2 は GPU が gfx11 WMMA または gfx12 と確認できた場合だけ有効です。この判定結果は関数内 `static` に初回評価時キャッシュされます（`engine/src/kernels/cuda/rdna_mmvq.cu:352-362,377-385`）。
- KQ dispatcher が受け付ける `n_in` は `QK`（256）で割り切れ、`ncols` は 1〜16 である必要があります。条件外なら、この環境変数の判定前に `false` を返します。第 2 重みがある場合は `n_out` が 8 の倍数であることも必要です（`engine/src/kernels/cuda/rdna_mmvq.cu:391-394`）。
- この設定が列数条件を変えるのは type 12（Q4_K）と type 13（Q5_K）だけです。type 23（IQ4_XS）と type 21（IQ3_S）は同じ dispatcher から専用カーネルを試しますが、この変数を読みません（同 `:405-418`; 呼び出し元 `engine/src/kernels/cuda/native_mmvq.cu:3518-3527,3813-3815`）。

なお、Strata の `docs/SETTINGS.md` はこの変数の対象を「NVIDIA and AMD」としていますが、現行コードの有効実装は上記 HIP AMD guard 内に限られます（`docs/SETTINGS.md:435`; `engine/src/kernels/cuda/rdna_mmvq.cu:20,36,484-493`）。`docs/DETAILS.md` にこの変数の説明は見つかりませんでした。

## 実行時の詳細

`native_q4_k_mmvq()` / `native_q5_k_mmvq()` が最初に `rdna_kq_mmvq()` を呼びます。専用 dispatcher は `rdna_q6k_enabled()`、形状条件、GGML type を順に確認します。type 12/13 の小列数で環境変数が未設定なら `false` を返すため、呼び出し元は汎用 Wave MMVQ または通常の単列カーネルへ進みます。設定済み、または 4 列以上なら KQ 専用カーネルを launch し、dispatcher は `true` を返して呼び出し元の fallback を抑止します（`engine/src/kernels/cuda/rdna_mmvq.cu:391-431`; `engine/src/kernels/cuda/native_mmvq.cu:3311-3336,3559-3584`）。

この変数は関数内 `static` に保存されず、小列数の type 12/13 呼び出しごとに `getenv` で確認されます。そのためプロセス環境が呼び出し間で変更されれば、次の対象呼び出しに反映されます。一方、RDNA dispatcher 自体の有効・無効は別の `rdna_q6k_enabled()` の static cache に従います（`engine/src/kernels/cuda/rdna_mmvq.cu:377-385,405-412`）。

## ログと測定値

この変数を読む箇所に、値や経路選択を出力する専用ログ・警告はありません。専用 KQ カーネルが選ばれた呼び出し元は `launch_check()` を実行し、CUDA/HIP runtime の launch error があれば `native MMVQ launch: ` に runtime のエラー文字列を続けた `std::runtime_error` を送出します。変数が未設定で専用 dispatcher が `false` を返すこと自体はエラーではなく、通常経路へ fallback します（`engine/src/kernels/cuda/native_mmvq.cu:2491-2495,3319-3324,3567-3572`）。Strata の `docs/DETAILS.md` に本変数に結び付いた測定値はありません。

## 根拠

- 値の有無判定、対象 type、列数と dispatcher の条件: `engine/src/kernels/cuda/rdna_mmvq.cu:391-431`
- 共通 RDNA 有効条件、環境変数の先頭文字判定と cache、GPU 世代判定: `engine/src/kernels/cuda/rdna_mmvq.cu:352-385`
- HIP AMD のコンパイル guard と非対応 build の stub: `engine/src/kernels/cuda/rdna_mmvq.cu:20-23,36-37,484-493`
- Q4_K / Q5_K の fallback 呼び出し: `engine/src/kernels/cuda/native_mmvq.cu:3311-3336,3559-3584`
- 設定一覧の説明: `docs/SETTINGS.md:435`
