# `STRATA_PRIVATE_B60_NEXT_POOL`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（2026-11-17 時点）。

## 役割

この変数は、Strata の SYCL カーネルにある Battlemage 向けの実験的な「next pool」経路を選ぶ補助フラグである。単独で機能全体を有効化するものではなく、MTP Q8 weight cache、IQ4 dense/head/expert の専用カーネル、GDN verify、fused GR down、QSA decode のそれぞれで異なる条件と組み合わせて使われる。条件に合わない呼び出しでは既存の経路へ進む。CUDA/HIP や一般の CLI / サーバー設定から値を読む参照は確認できず、対象は SYCL 実装である。

## 値と判定

各直接読み取り箇所は `std::getenv` の戻り値が null でないことに加えて、先頭文字 `p[0]` が `'1'` かだけを見る。文字列全体の比較や数値変換はしない。従って未設定、空文字、`0`、`true`、` 1` は無効であり、`1`、`1anything` は有効になる。大文字小文字や後続文字は判定に関係しない。無効値を理由に警告・エラーは出さない。

| 読み取り経路 | unset / 空文字 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| MTP Q8 cache 準備 (`b60_mtp_q8_cache_requested`) | 無効 | 先頭が `1` で、かつ `STRATA_PRIVATE_MTP_Q8_SOA` も同じ条件を満たす | 先頭が `1` 以外。後者の変数が未設定・空・先頭 `1` 以外でも無効 |
| IQ4 MMVQ、GDN verify、fused GR、QSA、IQ expert の各経路 | 無効 | 先頭文字が `1` | 空文字、`0`、`true`、空白始まりなど |

他の環境変数や CLI 引数がこの値を上書きする共通の優先順位はない。各機能に固有の追加フラグ・状態条件は次節のとおり。MTP cache 判定以外は、各関数内 `static` の初回呼び出しで値を保存するため、その翻訳単位の該当関数が一度評価された後にプロセス環境を変更しても反映されない。一方 MTP cache 準備判定は初期化時に評価し、`native_q8_0_mmvq` 側の helper は呼び出しごとに再評価する（`sycl/include/b60_mtp_q8_cache.hpp:5-9`、`sycl/src/core/mtp.cpp:418-420`、`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3683`）。

## 有効になる条件

- **MTP Q8 cache:** `MtpDrafter` が自身で weights を所有し、Q4 形式ではなく、`STRATA_PRIVATE_MTP_Q8_SOA` も有効であることが必要。選ばれるのはコードに列挙された 9 個の Q8 tensor で、形状・byte 数が一致しなければ `B60 MTP Q8 RT tensor mismatch`、cache の件数・総 byte 数が想定と異なれば `B60 MTP Q8 RT cache count/bytes` を送出して例外となる。モデル形式などが合わない場合はこの準備ブロックに入らない（`sycl/src/core/mtp.cpp:418-440`）。cache が作られていても、native Q8 MMVQ の `ncols` が 1, 4, 8 のいずれかで、重みポインタ・形状・デバイスに一致する cache がある場合に限って専用 probe を使う。それ以外は packed Q8、wide32、通常 small MMVQ の順で試す（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:4138-4150`、cache lookup は `sycl/src/kernels/cuda/weight_permute.dp.cpp:200-206`）。
- **IQ4 MMVQ:** `STRATA_PRIVATE_IQ4_INT4_DPAS` 側の Battlemage / packed weights / dense-head-draft 形状条件を満たす場合、dense の `ncols==4` かつ device / actor 条件に応じて leaf-pair kernel を選ぶ。IQ4 head cache 経路が別途有効で形状一致した場合は、`n_out==106299 && ncols==1` または `n_out==248320 && ncols==4` の head leaf kernel を選び、条件外では head SOA probe に戻る。cache 経路で必要な cache がないときは `B60 missing exact head decode cache` で失敗する（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3715,3717-3729`）。
- **IQ expert grouped:** `gu_type` が 16 または 22、`n_embd==2560`、`n_ff==640`、旧 kernel / split multi でなく、lanes が 8、`grid_groups==0`、`cap_groups==cap_entries`、対象 device で `p16_enabled` または `ps_enabled` が成立し、actor/device と `cap_entries` の組が分岐条件に合う必要がある。満たさない場合は後続の既存 switch に進む（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7388-7417`）。
- **GDN verify:** `n_keep==nullptr`、`t_out_begin==0`、`xq==nullptr`、`conv_channels==10240`、`h_k==16`、`h_v==48`、`eps==1e-6f`、`n_tok` が 2 または 4 のときに read-only split-local kernel を選ぶ。ほかは既存の GDN 経路へ進む（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:2200-2222`）。
- **Fused GR down:** `gc_enabled()` はこの変数に加えて `b60_main_actor()` を要求する。さらに GR down が SOA 経路を選び、token 数 `E` が 1、2、4 の場合に compact down kernel を使う。条件外は通常 SOA down kernel を使う（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2895,3095-3100,3110-3116`）。
- **QSA decode:** `STRATA_PRIVATE_B60_DECODE_LAYOUT` も有効であること、さらに query 数・KV capacity と device / single-actor 条件が一致することが必要。該当時は `B60QsaHead6` または `B60QsaLocalFence` を起動する。それ以外も layout flag だけで選ばれる float4 経路、または通常 vector-codes 経路へフォールバックし得る（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:2508-2509,2515-2549`）。

## 実行時の詳細

この変数は Strata の共通設定レジストリや CLI parser ではなく、SYCL kernel / MTP code 内で直接読み取られる。MTP Q8 cache 判定は drafter weights 初期化中に一度実行され、該当時に cache を生成する。native Q8 MMVQ はモデル計算中に helper を都度呼び、cache が存在して形状・デバイス・token mask に一致する場合だけ probe に早期 return する。cache lookup は mutex で保護された pointer-keyed registry を参照し、token mask は 1 / 4 / 8 token を区別する（`sycl/src/core/mtp.cpp:418-440`、`sycl/src/kernels/cuda/native_mmvq.dp.cpp:4138-4150`、`sycl/src/kernels/cuda/weight_permute.dp.cpp:191-206`）。

残る5箇所の読み取りは、MMVQ・verify・fused GR・QSA・IQ expert の各 `static` bool initializer 内で初回評価される。それぞれの評価結果をプロセス実行中に再読み込みしない。OS、サーバーモード、CLI 引数による別の有効条件は該当コードにはなく、device / model shape / tensor layout / actor 状態による制限が適用される。

## ログと測定値

値そのものが無効なときに出るログはない。専用経路が実際に呼ばれた場合、GDN verify は device / token count の組み合わせごとに一度 `[B60_GDN_SPLIT_LOCAL] capture device=%u T=%d` を stderr に出し、fused GR compact down は device ごとに一度 `[B60_GR_COMPACT_DOWN] capture device=%u T=%d` を出す（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:2211-2219`、`sycl/src/kernels/cuda/fused_gr.dp.cpp:2957-2964`）。MTP cache 作成時は `B60_MTP_Q8_CACHE device=%d matrices=%d allocation_bytes=%zu` を出す（`sycl/src/core/mtp.cpp:437-440`）。この commit の資料に本変数の測定値は確認できなかった。

## 根拠

- `sycl/include/b60_mtp_q8_cache.hpp:5-9` — MTP の直接読み取りと追加フラグ。
- `sycl/src/core/mtp.cpp:418-440` — MTP 初期化条件、tensor 対象、失敗条件、ログ。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3680-3686,3701-3734,4138-4150` — MMVQ の値判定、IQ4 条件、Q8 cache の利用と fallback。
- `sycl/src/kernels/cuda/verify_kernels.dp.cpp:2200-2222` — verify 経路、条件、ログ。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2890-2896,2957-2964,3095-3116` — actor 条件、compact down kernel とログ。
- `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:2508-2509,2515-2549` — QSA の追加条件と fallback。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5191-5192,7388-7417` — IQ expert 経路条件。
- `sycl/src/kernels/cuda/weight_permute.dp.cpp:191-206` — MTP cache registry と lookup 条件。
