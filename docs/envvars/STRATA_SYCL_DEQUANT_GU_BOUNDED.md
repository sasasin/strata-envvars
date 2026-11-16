# `STRATA_SYCL_DEQUANT_GU_BOUNDED`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の gate/up 行列を FP16 に展開する `iq_dequant_gu_f16` で、対応する IQ 形式と形状なら bounded-offset 版の dequant kernel を先に試すフラグ。bounded 版が処理を受け付けるとその kernel を投入して関数から戻り、従来の subgroup kernel は使わない。bounded 版が対象外または形状を受け付けない場合は従来経路へ進む（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6537-6558, 6638-6649`）。

この読み取りは SYCL のソースにだけあり、通常の CUDA/HIP ビルドからは使われない。トップレベル CMake では SYCL は別 backend として `STRATA_ENABLE_SYCL` が有効な場合だけ追加され、CUDA/HIP と同時には構成できない（`CMakeLists.txt:23-32`）。対象ファイルは SYCL kernel library のソースに含まれる（`sycl/CMakeLists.txt:35-42`）。

## 値と判定

`env_on` は `std::getenv` が null でなく、値の先頭文字が NUL でも `'0'` でもない場合に true を返す。文字列を数値・真偽値として parse せず、空白除去や大文字小文字変換もしない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3689-3692`）。

| ビルド／読み取り箇所 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL `iq_dequant_gu_f16` | off | 先頭が `1`、`true`、空白など、`0` 以外の非 NUL 文字である値。文字列全体の妥当性は問わない | 空文字、`0`、`0anything` など先頭が `0` の値 |

したがって `false` や `anything` も有効、` 0` も有効、空文字は無効。CUDA/HIP にはこの変数を読む箇所がなく、そこでの値の扱いは該当しない。

## 有効になる条件

- `iq_dequant_gu_f16` が呼ばれる SYCL 実行経路であること。通常の prefill 経路では native expert の gate/up を個別に展開する箇所などから呼ばれる（`sycl/src/prefill/prefill.cpp:4686-4717`）。SYCL prefill が fused grouped XMX の枝を選ぶ場合、その枝は `iq_xmx_grouped` を呼ぶため、この dequant 関数と環境変数の判定には入らない（`sycl/src/prefill/prefill.cpp:4583-4605`）。
- 呼び出し引数が外側の検査を通ること。`n_embd` は 256 の倍数、type は `is_iq` が受け付ける形式、`tail` は null である必要があり、満たさなければ環境変数の分岐より前に stderr へ `iq_dequant_gu_f16: type %d / %lld\n` を出して `exit(1)` する（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6638-6643`）。
- bounded kernel が受け付ける type は 16（IQ2_XXS）、22（IQ2_S）、29（IQ1_M）のみ。さらに `n_ff` と `n_embd` が正、`n_embd` が 256 の倍数、uint32 byte-offset の上限内である必要がある。これら以外では bounded 関数が false を返し、フラグが有効でも従来経路へ進む（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6537-6558`; type 名は `sycl/src/kernels/iq_multi_parity.cpp:57-64`）。
- `n_embd == 2560` なら bounded kernel の `PerRow` を 10 に固定する。その他の対応形状では `n_embd / 256` を使う（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6467-6474, 6542-6546`）。
- `STRATA_SYCL_GU16_METADATA_QUARTET` が別途有効で type 16、`n_ff == 640`、`n_embd == 2560` の場合、bounded kernel の通常版より先に metadata 版を選ぶ。この別変数は先頭文字が `'1'` の場合だけ true になる（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6547-6550`）。

## 実行時の詳細

設定値は `iq_dequant_gu_f16` の関数ローカル `static const bool` として、同関数の最初の呼び出し時に一度だけ読み取られる。以後の呼び出しはキャッシュ値を使うため、プロセス実行中に環境を変更しても反映されない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6638-6645`）。

有効かつ適格な呼び出しでは bounded kernel が gate/up の block を処理し、gate/up を交互に並べた FP16 出力へ書き込む。bounded 関数が true を返すと、通常 kernel の subgroup 選択・投入へ進まず終了する（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6467-6497, 6643-6649`）。対象外 type や bounded 側の寸法上限を超えた場合は false が返り、`STRATA_SYCL_DEQUANT_GU_SG` による subgroup 数の選択へ進む。subgroup 数の未設定時は 1、受け付ける設定値は `atoi` 結果が 2、4、8 の場合で、それ以外は 1 に戻る。1 の場合は既存 kernel、2/4/8 の場合は tiled kernel が選ばれる（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6611-6617, 6645-6675`）。

bounded kernel の実装は常に 8 subgroup を起動する。対象変数は出力値や型選択を直接変更するのではなく、この代替 kernel を試すかどうかを切り替える。ソースから出力値の同一性や性能差は確認できない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6467-6497`）。

## ログと測定値

この環境変数の読み取り、有効化、bounded 関数の false による fallback に専用のログはない。外側の引数検査に失敗した場合の stderr 文言と終了処理は「有効になる条件」に記載したとおり。従来経路の末尾では `check("iq_dequant_gu_f16")` が呼ばれるが、この環境変数を理由とするログ文言はない（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6638-6644, 6675`）。

`docs/DETAILS.md` と関連する `docs/INTEL_ARC.md` にこの環境変数名の記載は見つからなかったため、ここでは性能値を記載しない。

## 根拠

- 候補名の唯一の実コード読み取りと値判定: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3689-3692, 6643-6649`。
- bounded kernel の type・寸法条件と投入: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6467-6497, 6537-6558`。
- SYCL 専用 build と runtime の呼び出し元: `CMakeLists.txt:23-32`, `sycl/CMakeLists.txt:35-42`, `sycl/src/prefill/prefill.cpp:4583-4605, 4686-4717`。
