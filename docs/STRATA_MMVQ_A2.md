# `STRATA_MMVQ_A2`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL backend の Q6_K wide MMVQ カーネルで、Q6_K の `ql` / `qh` を読み込む方法を選びます。有効時は、2-byte 境界のデータを含む領域から aligned な 16-byte 読み込みを2回行ってシフトする `load16_a2` 経路を使います。無効時は `sycl::int4` の直接ロード経路を使います。また、Q6_K wide カーネルの既定の shape 条件もこの値に連動します。

この変数の読み取りは SYCL ソース `sycl/src/kernels/cuda/native_mmvq.dp.cpp` にあります。CUDA backend や HIP backend で同名変数を読む実装は、HEAD 内で確認できませんでした。

## 値と判定

実装は `std::getenv()` の結果に `std::atoi()` を適用し、戻り値が 0 かどうかで判定します。文字列全体の妥当性は検査しません。

| 環境の値 | 判定 |
|---|---|
| unset | 有効（既定） |
| 空文字 | 無効（`atoi("")` は 0） |
| `0`、`00`、`0abc` | 無効（変換結果が 0） |
| `1`、`2`、`-1` | 有効（変換結果が 0 以外） |
| `abc` | 無効（数値変換できず 0） |
| ` 1x`、`+1x` | 有効（先頭の空白と符号を許容し、数値部分 `1` を変換） |

`atoi` は数値の後ろを検査しないため、たとえば `1abc` は有効、`0abc` は無効です。大小文字の概念はありません。判定値は関数内の `static const bool` に保存されるため、プロセス内で初回に判定した後の環境変更は反映されません。

根拠: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1534-1537`。

## 有効になる条件

環境変数が有効でも、aligned-load 経路を必ず通るわけではありません。

- `native_mmvq()` が GGML type 14（Q6_K）を受け取り、`native_q6_k_mmvq()` に進む必要があります。
- packed Q6_K weight が registry に登録され、その shape が一致する場合は `q6_packed_mmvq()` が先に処理を終えるため、この変数はその呼び出しに作用しません。
- rowwarp カーネル条件（1〜4 columns、`n_in % 256 == 0`、`rowwarp_rpw() > 0`）に合う場合は wide 経路より先に rowwarp が選ばれます。
- 通常の wide 経路には `STRATA_MMVQ_WIDE` が有効であること、`ncols` が `STRATA_MMVQ_WIDE_MAXC` 以下であること、`n_in % 256 == 0`、`n_out >= STRATA_MMVQ_WIDE_MIN` が必要です。`STRATA_MMVQ_WIDE` が未設定なら既定で有効です。
- wide 経路に入っても、aligned-load kernel の選択は wide kernel の rows-per-warp が 1 の場合に限られます。そうでない場合は別の wide kernel が選択されます。
- `STRATA_MMVQ_WIDE_MIN` または `STRATA_MMVQ_WIDE_MAXC` が設定されていれば、それぞれ `atoi` の値が `STRATA_MMVQ_A2` に基づく既定値を置き換えます。明示設定時は空文字や非数値文字列も `atoi` の結果 0 になります。

`STRATA_MMVQ_A2` が有効なときの既定値は `wide_min = 0`、`wide_maxc = 8`、無効なときは `wide_min = 4096`、`wide_maxc = 4` です。そのため、この変数は aligned load の選択に加え、wide 経路を使える出力行数・column 数の既定 gate にも影響します。各既定値も初回評価後に static 保存されます。

根拠: packed path と Q6_K dispatch は `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2699-2720,3426-3446,3685-3702`、rowwarp と wide gate は同 `3426-3455`、wide kernel の分岐は同 `1697-1741`。関連 knob の読み取りは同 `1989-2002,3433-3435`。

## 実行時の詳細

wide kernel が選択され、rows-per-warp が 1 で、この変数が有効な場合、Q6_K block 内の `ql` と `qh` に `load16_a2()` を使います。この関数は対象 address を含む aligned 16-byte chunks を読み、必要な byte 列を shift して `sycl::int4` に組み立てます。Q8_1 側の量子化値もこの A2 template 経路内では複数の 32-bit load で読みます。無効の場合、Q6_K の `ql` / `qh` は `sycl::int4` pointer から直接ロードし、Q8_1 値も `sycl::int4` 経由でロードします。計算後は同じ wide kernel 内で積和と出力を行います。

環境変数の判定自体はログを出さず、入力値を変更する処理でもありません。Strata の `docs/INTEL.md` は aligned-load 実装について、出力 token は同一であり、`STRATA_MMVQ_A2=0` で旧経路を戻せると記載しています。同資料は B70 上の kernel 測定と Coder decode 44.9→54 tok/s を報告していますが、これは資料記載の測定条件に限られた値です。この調査では測定を再実行していません。

根拠: load method と template 分岐は `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1515-1537,1539-1587`、wide launcher の分岐は同 `1697-1741`、資料記述は `docs/INTEL.md:448-455`。SYCL の kernel source set には `native_mmvq` が含まれます（`sycl/CMakeLists.txt:206`）。

## 根拠

- 読み取り、既定値、aligned load 実装: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1515-1537`
- Q6_K wide kernel の launch 選択: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1697-1741`
- Q6_K dispatch、wide shape gate、fallback 経路: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3426-3514`
- GGML type 14 から Q6_K への dispatch: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3685-3702`
- 関連資料と測定記載: `docs/INTEL.md:448-455`
