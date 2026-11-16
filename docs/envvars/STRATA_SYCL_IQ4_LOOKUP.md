# `STRATA_SYCL_IQ4_LOOKUP`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（2026-11-17 時点）。

## 役割

SYCL エンジンの IQ4_XS native MMVQ で、Intel Battlemage の一部形状に対して `WideIQ4Lookup` 経路を試すかを制御する。`WideIQ4Lookup` は IQ4_XS の 4-bit 値を `iq4_decode::bit_select_impl` で復号し、親の `WideIQ4XS` と同じ `apply` の浮動小数点演算を使う（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:1831-1850`）。変数を有効にしても、ここより前の専用カーネル経路や後続条件が成立すれば、この経路は選ばれない（同 `:3701-3776`）。

IQ4_XS (`ggml_type == 23`) の native MMVQ から呼ばれる。通常の CUDA/HIP/Metal 経路ではなく、Strata の SYCL ソース内の実装である（同 `:3692-3700`, `:4203-4217`）。

## 値と判定

`native_iq4_xs_mmvq` 内の関数ローカル `static const bool` 初期化で `std::getenv` を 1 回呼び、未設定なら `true`、設定済みなら `std::atoi(v) != 0` とする（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3744-3747`）。文字列全体の検証はせず、`atoi` が先頭の空白と符号・10進数字を変換し、数字以降は無視する。したがって、数字で始まらない値（`true`、`false`、空文字など）は 0 として無効になり、先頭の数値部分が非ゼロなら有効になる。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| `atoi` による判定 | 有効 | `1`, `-1`, `+1`, ` 1tail`, `1.5` | 空文字, `0`, `00`, `0tail`, `true`, `false`, `x1` |

値の優先順位を変える CLI 引数・設定ファイルはこの関数にありません。別環境変数 `STRATA_MMVQ_WIDE_K` はこの後の `try_wide` 共通条件を制御し、未設定では wide 経路を許可、`atoi` が 0 のときは失敗扱いにして次の実装へ進ませる（同 `:2066-2069`, `:2071-2083`）。

## 有効になる条件

- SYCL バックエンドで IQ4_XS の native MMVQ (`ggml_type == 23`) が呼ばれること（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3692-3700`, `:4203-4217`）。
- `STRATA_SYCL_IQ4_LOOKUP` のキャッシュ値が有効で、実行デバイス世代が Battlemage、かつ `n_in` が 2560 または 6144 であること（同 `:3744-3749`, `:3772-3775`）。
- `try_wide` の追加条件として `STRATA_MMVQ_WIDE_K` が有効、`1 <= ncols <= 8`、`n_in` が IQ4_XS のブロック長 `QK` の倍数であること（同 `:2071-2083`）。この関数の前段では `ncols` は 1〜8 に検証される（同 `:2298-2302`）。
- より前の優先経路が return していないこと。B60 キャッシュ経路（同 `:3701-3716`）、`STRATA_PRIVATE_IQ4_INT4_DPAS` 経路（同 `:3717-3730`）、B60 packed dense 主 actor 経路（同 `:3731-3735`）が先に判定される。
- 既定有効の `STRATA_SYCL_IQ4_PAIR_REUSE` 分岐に入らないこと。この分岐は Battlemage、`ncols <= 4`、`n_in` 2560/6144、除外 shape でなく、weight と activation が 64-byte 整列なら選択 shape かどうかにかかわらず return する。明示的に `STRATA_SYCL_IQ4_PAIR_REUSE=0` とすれば `atoi` 判定が偽になり、この経路を通らない（同 `:3736-3756`）。
- さらに `STRATA_SYCL_IQ4_T4_ESIMD` の条件を満たして先行 return しないこと（同 `:3758-3763`）、および `STRATA_SYCL_IQ4_T4_XMX` の有効 shape で先行 return しないこと（同 `:3764-3770`）。

条件を満たさない場合、`WideIQ4Lookup` は呼ばれず、続いて `WideIQ4XS`、wave MMVQ、multi または通常 IQ4_XS カーネルへ進む（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3772-3843`）。

## 実行時の詳細

環境変数は `native_iq4_xs_mmvq` の `use_bit_select` static 初期化時に読み取られる。関数に到達しても前段の early return があれば初期化位置まで実行が進まず、最初にその位置へ到達した呼び出しで値が固定される。その後プロセス内で環境を変更しても反映されない（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3747`）。

有効な場合は `try_wide<WideIQ4Lookup>` が列数に応じた wide kernel を投入し、成功扱いで `launch_check()` の後に return する。`STRATA_MMVQ_WIDE_K=0` などで `try_wide` が false を返すと `WideIQ4XS` を試す（同 `:2066-2083`, `:3772-3777`）。変数による CLI 優先順位、子プロセスへの転送、リクエスト単位の再評価はこのコードにはない。

## ログと測定値

この変数の値や選択結果を表示する専用ログは該当箇所にない（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3744-3777`）。この分岐の後にある `launch_check()` はエラーコードを 0 に固定する移植時の残存コードで、SYCL の例外機構への置き換えを促すコメントがある（同 `:2311-2325`）。対象変数が有効・無効のどちらで失敗するか、またその失敗時の表示や終了結果は、この分岐だけからは確認できない。対象変数に関する条件付き測定値も確認できなかった。

## 根拠

- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3692-3700` — 対象関数と前提チェック。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3777` — 先行経路、環境変数の読み取り、Battlemage 判定、優先順位。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1831-1850` — `WideIQ4Lookup` の復号処理と共通演算。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2066-2083` — `STRATA_MMVQ_WIDE_K` と wide-dispatch の追加条件。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:4203-4217` — GGML type 23 から IQ4_XS native MMVQ への dispatch。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2311-2325` — `launch_check()` の実装。
