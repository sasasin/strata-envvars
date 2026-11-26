# `STRATA_PF_XMX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL backend の prompt MoE expert 計算で、グループ化した XMX 経路を選ぶ整数モードです。`0` はこの XMX 経路を使わず、`1` は expert 重みを FP16 に dequantize してから grouped XMX GEMM を使い、`2` は条件を満たす native pack で dequantize を grouped launch 内に含める fused XMX 経路を選びます。対象コードは SYCL prefill とその XMX kernel にあり、CUDA/HIP 側の読み取りは見つかりませんでした（`engine/sycl/src/prefill/xmx_moe.dp.cpp:149-175`, `engine/sycl/src/prefill/prefill.cpp:5133-5143,5161-5222`）。

## 値と判定

`xmx::mode()` は `std::getenv("STRATA_PF_XMX")` の結果を `std::atoi` に渡します。未設定なら GPU 世代が Alchemist のとき `2`、それ以外は `0` です。設定ありなら空文字を含めて `atoi` の結果を使います。文字列全体の検証や警告はありません。したがって `"2tail"`, `" 2"`, `"+2"` は `2`、`"0anything"`, `"true"`, 空文字, 数字に変換できない文字列は `0` になります。負数や `3` なども整数として返されますが、実装が定義するモードは `0/1/2` だけです（`engine/sycl/src/prefill/xmx_moe.dp.cpp:152-170`）。

| 条件 | unset | 有効になる値（例） | 無効・未対応になる値（例） |
|---|---|---|---|
| Alchemist の SYCL 実行 | `2` | `2`, `2tail` → mode 2; `1` → mode 1 | `0`, 空文字, `true` → mode 0 |
| Alchemist 以外の SYCL 実行 | `0` | `1` または `2` を要求 | `0`, 空文字, `true` → mode 0 |
| `STRATA_NO_DG2_XMX` build、または `STRATA_XMX_SG16` がなく実行 GPU が Battlemage | その build/device による既定判定 | なし（非ゼロ要求は下記の警告後に mode 0） | 非ゼロ値は無視され mode 0 |

`atoi` の値が `1` または `2` でない非ゼロ整数は parser に拒否されず返りますが、どちらの grouped XMX 分岐にも一致しません。`mode()!=0` だけで判定する補助条件（`f16_pairs` や Battlemage の `fp16_group` 条件）には影響し得るため、`0/1/2` 以外はサポートされた選択肢として扱えません（`engine/sycl/src/prefill/prefill.cpp:4627-4628,4841-4848,5161`）。

## 有効になる条件

- この読み取りと利用は `engine/sycl` の SYCL prefill 実装にあります。変数名の参照検索では、CUDA/HIP 実装や CLI 引数としての別定義は見つかりませんでした。
- mode 1/2 の要求は XMX kernel が build に含まれる必要があります。`STRATA_NO_DG2_XMX` が定義された build では非ゼロ要求を無視して mode 0 にし、stderr に警告します。CMake は `STRATA_SYCL_AOT` が `pvc` で始まる場合にこの macro を定義し、`bmg` / `lnl` では `STRATA_XMX_SG16` を定義します（`engine/sycl/CMakeLists.txt:72-77`; `engine/sycl/src/prefill/xmx_moe.dp.cpp:160-170`）。
- `STRATA_XMX_SG16` がない build で実 GPU が Battlemage の場合も、非ゼロ要求は警告後に mode 0 へ戻ります。SG16 AOT build ではこの Battlemage 拒否分岐を通りません（`engine/sycl/src/prefill/xmx_moe.dp.cpp:164-170`）。
- mode 2 の fused 経路にはさらに `!use_mmq` と `xmx2_fmt()` が必要です。`xmx2_fmt()` は native expert layout、tail scale なし、`N % 128 == 0`, `kFF2 % 128 == 0`, `kFF % 32 == 0` を要求し、形式が trellis の `(gu,down)=(144|145,144|146)`、または両方がコード内の IQ type allowlist（2, 3, 6, 7, 8, 12, 13, 16, 17, 18, 20, 21, 22, 23, 29, 42。`STRATA_Q6K_EXPERTS` build では 14 も含む）に入る必要があります（`engine/sycl/src/prefill/prefill.cpp:4754-4772`）。条件外では mode 2 の XMX fused 経路を使わず、独立して有効な int8 経路などがなければ通常の FP16 expert 経路へ進みます（同 `:4775-4781,4789-4797,5133-5144`）。
- mode 1 は MMQ を使う expert layer では `compute` 内の grouped XMX 分岐まで到達しません（`use_mmq` 分岐が先に処理を返すため）。mode 1 の gate/up grouped GEMM は group の平均 routed rows が `STRATA_PF_XMX_GU_MAX` 未満の場合に限り、未設定時の閾値は `250` です。閾値以上では gate/up を expert ごとの oneMKL GEMM に fallback しますが、down は grouped XMX GEMM です（`engine/sycl/src/prefill/prefill.cpp:5083-5132,5161-5222`; `engine/sycl/src/prefill/xmx_moe.dp.cpp:177-180`）。
- mode 2 が fused 経路に入っても、group 平均 rows が `STRATA_PF_XMX_ROWS` 未満のときだけ grouped fused IQ XMX を使います。同変数の未設定値は `200` で、閾値以上では group を dequantize して expert ごとの GEMM に fallback します（`engine/sycl/src/prefill/prefill.cpp:5035-5066`）。
- `STRATA_PREFILL_MMQ` / その alias `STRATA_PF_I8` は `use_mmq` と別の int8 選択に関与します。mode 2 の形式条件が不成立でも、これらで選ばれた int8 経路は独立して利用される場合があります（`engine/sycl/src/prefill/prefill.cpp:333-345,4775-4781`）。

## 実行時の詳細

値は `mode()` 内の関数ローカル `static const int` lambda で初回呼び出し時に評価・cache され、以降の呼び出しでは同じ値を返します。プロセス起動後に環境を変更しても再評価されません。初回評価では unset の既定値を決めるため `q_of(nullptr)` から得た device の Intel GPU 世代も参照します（`engine/sycl/src/prefill/xmx_moe.dp.cpp:149-175`）。

mode は prefill の workspace/ring sizing と expert execution の双方で参照されます。mode 2 は staged expert group 用 ring slot を追加し、mode 1 は dequantized expert の scratch slot 数を group 上限まで増やします（`engine/sycl/src/prefill/prefill.cpp:347-354,1769-1787`）。expert 実行では mode 1 が group dequantize 後に grouped GEMM を選び（gate/up は前節の平均 rows 条件付き）、mode 2 は eligible native format を quantized group のまま fused grouped kernel に渡します（同 `:5133-5143,5161-5222`; `engine/sycl/src/prefill/xmx_moe.dp.cpp:182-197`）。

CLI 引数による上書きはこの変数名の実装経路では確認できませんでした。設定が engine に渡る場合は環境変数として読み取られます。別の XMX 関連環境変数 `STRATA_PF_XMX_GU_MAX` と `STRATA_PF_XMX_ROWS` は mode 1/2 の各実行経路内の crossover を変えますが、`STRATA_PF_XMX` 自体の値判定や cache を上書きしません（`engine/sycl/src/prefill/xmx_moe.dp.cpp:177-180`; `engine/sycl/src/prefill/prefill.cpp:5037-5041,5207-5222`）。

## ログと測定値

build/device 条件で非ゼロ値が無視されたときは、stderr にそれぞれ `STRATA_PF_XMX ignored: this build is AOT for a device without the sub-group 8 XMX kernels` または `STRATA_PF_XMX ignored: this build has the sub-group 8 / 8x8x16 kernels (Arc A-series); Battlemage needs the AOT bmg build` が出ます（`engine/sycl/src/prefill/xmx_moe.dp.cpp:160-167`）。mode 2 で `xmx2` が false（mode 2 用 XMX 条件を満たさず、独立した int8 経路も選択されない）なら、prefill 中に一度 `strata: STRATA_PF_XMX=2 not taken at layer ... (stream_all ..., mmq ..., native ..., formats .../...)` を出します。実際に選択した mode 2 / mode 1 の経路では各々 `strata: prompt experts on the fused grouped XMX (STRATA_PF_XMX=2)` / `strata: prompt experts on the grouped XMX GEMM (STRATA_PF_XMX=1)` を一度出します（`engine/sycl/src/prefill/prefill.cpp:4789-4797,5031-5034,5186-5190`）。mode 0 や `atoi` が 0 になる無効文字列に対する専用ログはありません。

`docs/INTEL.md:287-295` は engine 0.1.45.3、Arc A750 8 GB 等の条件で grouped XMX 時の prompt 1K/2K/4K/6K を 46.4/83.1/110.4/114.8 tok/s、変更前を 35.1/61.7/79.3/66.3 tok/s と記録しています。`docs/release-notes-0.2.0.md:57` は同じ 4K の変更後値を 113.0 tok/s と記載しており資料間に差があります。いずれも過去版の資料上の値であり、この調査で再測定していません。`docs/DETAILS.md` に対象変数の記載は見つかりませんでした。

## 根拠

- Parser、device default、cache、build/device fallback: `engine/sycl/src/prefill/xmx_moe.dp.cpp:149-180`
- AOT macro 設定: `engine/sycl/CMakeLists.txt:50-77`
- mode ごとの scratch/ring sizing: `engine/sycl/src/prefill/prefill.cpp:347-354,1769-1787`
- mode 2 の format 条件・fallback・ログ: `engine/sycl/src/prefill/prefill.cpp:4748-4797,5031-5066`
- mode 1 の grouped execution・閾値・ログ: `engine/sycl/src/prefill/prefill.cpp:5161-5222`
- grouped kernel 実装: `engine/sycl/src/prefill/xmx_moe.dp.cpp:41-125,182-197`
