# `STRATA_PRIVATE_MTP_Q8_SOA`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL エンジンの MTP draft layer が所有する Q8_0 重みについて、読み込み時に SoA 形式の device cache を作り、条件を満たす Q8 MMVQ 呼び出しを専用の MTP Q8 SoA カーネルへ切り替えるための内部フラグです。単独では有効にならず、`STRATA_PRIVATE_B60_NEXT_POOL` も `1` で始まる必要があります。通常の重み領域はそのまま保持され、cache がない呼び出しは既存の packed / wide32 / small MMVQ 経路へ進みます。`sycl/include/b60_mtp_q8_cache.hpp:5` `sycl/src/core/mtp.cpp:418` `sycl/src/kernels/cuda/native_mmvq.dp.cpp:4138`

この実装は独立した実験的 SYCL backend に含まれます。トップレベル CMake は `STRATA_ENABLE_SYCL` が有効な場合に `sycl/` を構成し、CUDA/HIP と同時には有効化できません。CUDA/HIP/CPU 側の同名読み取りはこの checkout では見つかりません。`CMakeLists.txt:23` `sycl/CMakeLists.txt:257`

## 値と判定

`b60_mtp_q8_cache_requested()` は呼び出すたびに `std::getenv` で対象変数と `STRATA_PRIVATE_B60_NEXT_POOL` を読み、それぞれの先頭文字が `'1'` かを調べて AND を返します。完全一致や数値変換はしません。どちらかが未設定または空文字なら false です。`sycl/include/b60_mtp_q8_cache.hpp:5`

| 条件 | unset | 有効になる値（対象変数） | 無効になる値（対象変数） |
|---|---|---|---|
| SYCL build、かつ `STRATA_PRIVATE_B60_NEXT_POOL` の先頭文字も `1` | false | `1`, `10`, `1anything` | 空文字、`0`, `true`, ` 1`, `01` |
| それ以外の build または `STRATA_PRIVATE_B60_NEXT_POOL` が unset / 空 / 先頭文字が `1` 以外 | cache 要求は成立しない | 該当なし | 対象変数が `1` で始まっても成立しない |

大文字小文字・後続文字・数値としての妥当性は検査しません。たとえば `1anything` は有効、`true` は無効です。CLI 引数や設定ファイルによる上書き経路はありません。関連する `STRATA_PRIVATE_B60_NEXT_POOL` も同じく先頭文字だけで判定されます。`sycl/include/b60_mtp_q8_cache.hpp:5`

## 有効になる条件

- SYCL backend で MTP draft layer の `MtpDrafter::load` が実行されること。CUDA/HIP/CPU build にはこの実装が含まれません。`CMakeLists.txt:23` `sycl/CMakeLists.txt:257`
- 読み込み時に `owns_weights_` が true で、`q4_` が false であること。共有重み (`shared != nullptr`) は `owns_weights_ = false` になり、`--mtp-q4` 相当の Q4 重みでは cache 作成分岐に入りません。`sycl/src/core/mtp.cpp:317` `sycl/src/core/mtp.cpp:382` `sycl/src/core/mtp.cpp:418`
- 読み込み時点で対象変数と `STRATA_PRIVATE_B60_NEXT_POOL` の両方が有効であること。条件を満たすと、固定名の 9 tensor を shape・kind・byte size 検査後に変換します。cache mask は tensor ごとに異なり、1/4/8-token 呼び出しのすべてが全 tensor で使えるわけではありません。`sycl/src/core/mtp.cpp:418`
- 実行時に `native_q8_0_mmvq` が呼ばれ、対象変数と `STRATA_PRIVATE_B60_NEXT_POOL` がまだ有効で、`b60_weights_packed()` または `STRATA_PRIVATE_BMG_SINGLE_ACTOR` が有効、かつ `ncols` が 1/4/8 であること。さらに raw pointer、行列 shape、device が cache と一致し、その token 数の mask が立っている場合だけ専用 probe を選びます。`b60_weights_packed()` は現在の packed 状態を返し、single-actor 判定は初回呼び出し時に static cache されます。`sycl/src/kernels/cuda/native_mmvq.dp.cpp:4141` `sycl/src/kernels/cuda/weight_permute.dp.cpp:101` `sycl/include/b60_layout_state.hpp:8`
- 上記の追加実行条件が満たされない、または cache lookup が mask 不一致で null を返す場合は、この最適化を使わず、続く既存の packed、wide32、small MMVQ の順に処理します。`sycl/src/kernels/cuda/native_mmvq.dp.cpp:4144`

## 実行時の詳細

cache の作成判定は MTP 重み読み込み中の一度です。次の 9 tensor について寸法・`q8_0` kind・byte size を検査してから変換します。mask は `1u << tokens` で照合されます。9 個でなければ、または記録した合計 `72,071,424` bytes と合わなければ例外にします（各 matrix の 256-byte guard を含む）。変換後 cache は raw weight pointer を key に登録され、終了時に owned weights の destructor が解放します。`sycl/src/core/mtp.cpp:418-439` `sycl/src/core/mtp.cpp:188-195` `sycl/src/kernels/cuda/weight_permute.dp.cpp:200-217`

| tensor | rows × cols | mask | cache が許可する token 数 |
|---|---:|---:|---|
| `fc_embedding.weight` | 2560 × 2560 | 18 | 1, 4 |
| `fc_hidden.weight` | 2560 × 2560 | 272 | 4, 8 |
| `mlp.shared_expert.down_proj.weight` | 2560 × 640 | 2 | 1 |
| `mlp.shared_expert.gate_proj.weight` | 640 × 2560 | 2 | 1 |
| `mlp.shared_expert.up_proj.weight` | 640 × 2560 | 2 | 1 |
| `self_attn.k_proj.weight` | 512 × 2560 | 18 | 1, 4 |
| `self_attn.o_proj.weight` | 2560 × 6144 | 2 | 1 |
| `self_attn.q_proj.weight` | 12288 × 2560 | 2 | 1 |
| `self_attn.v_proj.weight` | 512 × 2560 | 18 | 1, 4 |

各 Q8 MMVQ 呼び出し時には cache helper が対象変数を再読します。対象変数を MTP 読み込み後に有効化しても cache は遡って作られないため通常経路へ進みます。読み込み時に作成済みでも、後から対象変数または `STRATA_PRIVATE_B60_NEXT_POOL` を無効化すると専用経路を通りません。cache lookup は shape/device 不一致を検出すると例外にし、token-mask 不一致なら cache を返さず通常経路に戻ります。`sycl/include/b60_mtp_q8_cache.hpp:5` `sycl/src/kernels/cuda/weight_permute.dp.cpp:200`

cache lookup に成功すると `b60_mtp_q8_multi_soa_probe` を呼び、その場で return するため、通常の Q8_0 MMVQ 経路を実行しません。probe は 1 token を単独 probe に委譲し、4/8 token は K が 2560/6144/640 の専用カーネルを選びます。単独 probe は N が正で 16 の倍数であることを要求します。`sycl/src/kernels/cuda/native_mmvq.dp.cpp:4141` `sycl/src/kernels/cuda/native_mmvq.dp.cpp:5923`

## ログと測定値

9 tensor の cache 作成成功後、stderr に `B60_MTP_Q8_CACHE device=%d matrices=%d allocation_bytes=%zu` を出します。対象変数が unset または条件不成立の場合、このログはこの分岐からは出ません。cache byte 数は MTP の `vram_` に加算され、後続の一般的な `strata mtp: draft layer loaded, ...` 表示にも反映されます。`sycl/src/core/mtp.cpp:435` `sycl/src/core/mtp.cpp:593`

shape/kind/byte size の不一致は `B60 MTP Q8 RT tensor mismatch` または `B60 MTP Q8 RT cache count/bytes` の `std::runtime_error`、cache helper の不正 shape/mask は `B60 MTP Q8 cache shape/mask`、queue/所有権不整合は `B60 MTP Q8 cache ownership/queue` の `std::invalid_argument`、allocation 失敗は `std::bad_alloc` になります。cache lookup の行列寸法/device の不一致は `B60 MTP Q8 cached pointer geometry/device` の `std::logic_error` です。load の関数内で示される catch は `sycl::exception` のみです。専用 probe の不正 shape は `MTP Q8 SoA rows` / `MTP Q8 SoA columns` / `MTP multi Q8 SoA shape` / `MTP multi Q8 SoA columns` の `std::invalid_argument` になります。`sycl/src/core/mtp.cpp:432` `sycl/src/kernels/cuda/weight_permute.dp.cpp:208-215` `sycl/src/kernels/cuda/weight_permute.dp.cpp:200-206` `sycl/src/kernels/cuda/native_mmvq.dp.cpp:5923-6020`

`docs/DETAILS.md` と `docs/INTEL.md` の MTP 説明には、この private cache flag の挙動や測定値は記載されていません。そのため性能・数値精度の差は本書では述べません。

## 根拠

- 対象変数と併用変数の読み取り: `sycl/include/b60_mtp_q8_cache.hpp:5-9`
- MTP の所有権・Q4 条件、tensor 検証、cache 作成とログ: `sycl/src/core/mtp.cpp:317-328`, `sycl/src/core/mtp.cpp:418-439`
- cache lookup、mask・shape/device 条件、cache の作成・解放: `sycl/src/kernels/cuda/weight_permute.dp.cpp:191-245`
- Q8 MMVQ の実行時分岐と fallback: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:4138-4150`
- SYCL 専用 probe の shape 分岐: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:5923-6020`
- backend が別 project であること: `CMakeLists.txt:23-32`, `sycl/CMakeLists.txt:257-265`
