# `STRATA_GR_UP_WIDE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。作業ツリーは `main...origin/main` で未コミット変更なし。

## 役割

ハイパーコネクション（HC）の up 射影を、1 warp = 1 行で読む `gr_up_wide_kernel` に切り替える。既定の `gr_up_multi_kernel` が 1 block = 16 列 × 4 stream（160 block、8 行/warp）なのに対し、wide は 1 block = 2 列 × 4 stream（`UPW_BLOCKS = N/2` = 1280 block、1 行/warp）で 8 warp が 8 行を担当する（`engine/src/kernels/cuda/fused_gr.cu:476-483, 514-564`）。行のロード、dot、xor 和、epilogue、stream 間の平均は既定カーネルと同じで、`mixed` と `R_out` も同じ値になる、とコメントは述べる（`fused_gr.cu:476-488`）。

読み取りは `gr_up_wide_on()` の 1 箇所（`fused_gr.cu:489-512`）、使用箇所は `launch_multi` 内（`fused_gr.cu:1871-1880`）だけ。単 token 用 `fused_gr_read` は影響しない（`fused_gr.cu:4526-4548`）。

## 値と判定

`std::getenv("STRATA_GR_UP_WIDE")` を関数内 `static` で 1 回だけ読み、`std::atoi(v) != 0` で判定する（`fused_gr.cu:495-499`）。文字列全体ではなく先頭の数値 prefix だけを見る。

| 設定値 | 結果 |
|---|---|
| 未設定 | 既定規則（下記） |
| `1` / `2` / `-1` / `1abc` / ` 1` | ON |
| `0` / `00` / `0abc` / `abc` / `false` / `off` / 空文字 | OFF |

空文字は「設定あり・値 0」として OFF になり、既定規則へは戻らない。HIP build は `__HIPCC__` の分岐で `getenv` より前に `false` を返すため、`=1` でも無視される（`fused_gr.cu:490-493`）。SYCL 版 `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp` にこの名前はない。

既定規則は `gr_up_wide_default(false, major, minor, qwen_defaults_026())`（`fused_gr.cu:507`）。CUDA かつ `STRATA_DEFAULTS=026` でなく、実効 compute capability が 12.0 で、`STRATA_SM120_PERF` が 0 でなければ ON（`engine/include/strata/core/sm120_series.hpp:60-61, 78-80, 172-174`）。GB10（12.1）用の定数 `kGb10GrUpWide` は `false` なので 12.1 では常に OFF（`sm120_series.hpp:89-97`）、他の arch も OFF。`STRATA_SM120_PERF` は未設定か `atoi != 0` で ON（`sm120_series.hpp:32-39`）。`STRATA_DEFAULTS` は `026` / `0.2.6` / `v0.2.6` の完全一致だけを 0.2.6 とみなす（`engine/include/strata/core/defaults_026.hpp:21-30`）。明示した `STRATA_GR_UP_WIDE` は `STRATA_SM120_PERF=0` と `STRATA_DEFAULTS=026` より優先する（`fused_gr.cu:499`）。

`is_sm120` は `STRATA_EMULATE_CC` を経由するが（`sm120_series.hpp:41-42`, `engine/include/strata/core/emulate.hpp:59-80`）、受け付けるのは 75 以上 120 未満だけなので（`emulate.hpp:63`）、`=120` で 12.0 を装うことはできない（`sm120_series.hpp:41` のコメントと不一致）。実 12.0 カードに `=86` を置くと既定は OFF。

## 有効になる条件

値が ON でも、次のすべてを満たす読みでだけ wide が起動する。

- CUDA build である。
- HC の multi read が既定経路 `launch_multi` に到達する。`fused_gr_read_multi_slice` は Q8_0 重み（`STRATA_HC_Q8`）、RDNA 経路、V3 split で先に return する（`fused_gr.cu:4284-4301, 4349-4396`）。`STRATA_HC_PERSIST=1` の persistent read も先に処理される（`verify.cpp:1816`）。
  - `STRATA_GR_V3` は discrete な 12.0 カードで 13 GiB 超なら既定 ON（`sm120_series.hpp:139-144`）。この場合 v3 の up カーネルが走り wide は呼ばれない。wide の既定 ON 対象（RTX PRO 5000 72 GB など）はこれに当たるため、実際に wide を使うには `STRATA_GR_V3=0` が要る。
- `launch_multi` 内で `s_down == nullptr`（`STRATA_HC_REQ8` 無効）かつ `q8_mixed == nullptr`（`fused_gr.cu:1871`）。verify の HC read は前半で `qcnt_` があるとき `q8_mixed` を設定し（`verify.cpp:1810-1813`）、`qcnt_` は `STRATA_QFUSE` か `STRATA_QFUSE_HC` が ON で確保される（`verify.cpp:320, 1431-1437`）。sm_120 では `STRATA_QFUSE=1` が既定なので（`nv_defaults.cpp:104-129`）、既定の window HC read は wide にならず、`STRATA_QFUSE=0` も要る。
- `STRATA_GR_V70` の token-split read が先に成立していない（`fused_gr.cu:1797-1803`）。token 数は 8 以下（`kFusedGrMaxT`, `engine/include/strata/kernels/fused_gr.hpp:70`）で、8 超の window は 8 token 以下の slice に分かれる（`fused_gr.cu:4468-4481`）。
- モデル形状が n_embd 2560 / hc 4 / hc_lr 320 と一致する（`fused_gr.cu:43-46, 4522-4524`）。

wide は `launch_multi` の最初の分岐なので、`STRATA_GR_UP75` や `STRATA_GR_FAST` の up カーネルより優先される（`fused_gr.cu:1871-1884, 1910-1928`）。

## 実行時の詳細

- 読み取りは最初に `gr_up_wide_on()` が呼ばれた時点の 1 回だけ。以後の環境変更は反映されない（`fused_gr.cu:495-499`）。未設定時の既定は device ごとに 1 回計算して `per_dev[64]` に保存し、`cudaGetDevice` か属性取得に失敗すると OFF（`fused_gr.cu:500-510`）。
- engine はこの変数を設定しない（sm_120 の既定表にも `setenv` の対象にもない, `nv_defaults.cpp:107-129`）。既定はカーネル側で決まる。
- 起動するのは `gr_up_wide_kernel<T, true>`（T=1..6）または `gr_up_wide_kernel<kFusedGrMaxT, false>`、グリッドは常に 1280 block、block は 256 スレッド（`fused_gr.cu:1872-1880`）。既定カーネルの q8_1 tail（`gr_q8_tail`）は wide にはないが、wide の条件で `q8_mixed` は null なので出力に差は出ない（`fused_gr.cu:473, 514-564`）。

## ログと測定値

wide の選択・非選択を告げるログはない。`gr_up_wide_on()` にも起動箇所にも `fprintf` はなく、v3 や persist のような「off にした理由」の行も出ない（`fused_gr.cu:489-512, 1871-1880`）。有効かは `STRATA_GR_UP_WIDE` / `STRATA_SM120_PERF` / `STRATA_GR_V3` / `STRATA_QFUSE` の組み合わせからしか判断できない。

- RTX PRO 5000、IQ3_S、全 expert resident、interleaved 5 pair: story 197.6 → 201.3 tok/s（+1.9%）、code 243.5 → 245.1（+0.7%）、生成 token id は 6/6 一致、単体 read は旧カーネルと bitwise（`fused_gr.cu:486-488`, `sm120_series.hpp:13-14`）。`STRATA_GR_V3` の設定に触れておらず、既定では v3 が先に走るため、この数値だけで既定構成の効果は言えない。
- GB10（12.1、IQ3_S、全 expert resident、DFlash2 Q4_0 drafter、`--spec 6`）: chat / code / json / agent で -0.4 / -0.3 / -0.1 / -0.2%。ばらつき程度なので OFF のまま（`sm120_series.hpp:83-90`）。`docs/DGX_SPARK_LINUX.md:124-126` も Spark では level か遅いとして OFF、明示設定は有効とする。

専用の wide テストはないが、`fused_gr_selftest` は `launch_multi` の出力を単 token read と比較するため、wide が有効な環境では wide もこの比較に入る（`fused_gr.cu:4684, 4701`）。`docs/DETAILS.md:1467` の sm_120 既定表は本変数を列挙せず、`sm120_series.hpp` の「12.0 で既定 ON」と一致しない。`docs/SETTINGS.md` にも項目がない（register では status `research`）。

## 根拠

- `engine/src/kernels/cuda/fused_gr.cu:476-512, 514-564, 1869-1880`（getenv / atoi / 既定、wide カーネル本体、起動条件）
- `engine/include/strata/core/sm120_series.hpp:60-61, 78-80, 139-144, 172-174`（wide と V3 の既定規則）
- `engine/include/strata/core/defaults_026.hpp:21-30`（`STRATA_DEFAULTS` の判定）
- `engine/src/core/nv_defaults.cpp:104-129` と `engine/src/core/verify.cpp:1431-1437, 1810-1813`（QFUSE と q8_mixed）
- `engine/src/kernels/cuda/fused_gr.cu:4284-4301, 4349-4396`（v3 / Q8 / RDNA が先に return）
