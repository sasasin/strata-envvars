# `STRATA_INK_CHUNK_AUTO`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling CUDA backend で、CLI の `--chunk` が指定されていないときに、GPU 上の expert 配置後に残る VRAM と slot 数に応じて prefill chunk を 512 より大きくする自動選択を有効にする。環境変数の値が `atoi` で 0 になる場合、この自動選択を止め、初期 chunk 512 を使う。対象は Inkling CUDA backend であり、HIP・SYCL・Metal backend にこの名前を読む箇所はない。候補一覧の `docs/SETTINGS.md` は NVIDIA and AMD と記すが、調査対象 commit での直接の読み取りは CUDA backend に限られる（`engine/src/inkling2/cuda/ink_cuda_backend.cu:292-300`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp`; `engine/src/inkling2/sycl/ink_sycl_backend.cpp`; `engine/src/inkling2/metal/ink_metal_backend.mm`; `docs/SETTINGS.md:395`）。

## 値と判定

CUDA backend の `init` 中に `std::getenv` で取得し、値が存在し、かつ `std::atoi(value) == 0` の場合だけ自動選択を抑止する。文字列全体の妥当性や数値範囲は検証しない。`atoi` が先頭の空白と符号を許容し、数字列の後ろを無視するため、空文字・非数値文字列・`0anything`・` 0` は 0 となり、自動選択を止める。一方 `1`、`-1`、`2`、`1anything` は 0 以外となり、自動選択を許す。未設定も自動選択を許す。`atoi` の表現範囲を超える値の結果は C/C++ の変換仕様上保証されないため、設定値として扱わない（`engine/src/inkling2/cuda/ink_cuda_backend.cu:292-300`）。

| 条件 | 未設定 | 自動選択を止める値 | 自動選択を許す値 |
|---|---|---|---|
| Inkling CUDA、`--chunk` なし、layer-split なし | 自動選択を試みる | `atoi` 結果が 0（例: `0`, `00`, `0anything`, 空文字, `false`, ` 0`） | `atoi` 結果が非 0（例: `1`, `-1`, `2`, `true`, `1anything`） |
| `--chunk N` 指定、または layer-split 有効 | この環境変数の判定箇所を通らない | 適用されない | 適用されない |

## 有効になる条件

- Inkling の CUDA backend が選ばれて初期化されること。この名前を読む環境変数判定は `engine/src/inkling2/cuda/ink_cuda_backend.cu` にのみある。
- CLI で `--chunk` を指定しないこと。引数解析は `chunk_auto` を false にするため、環境変数の判定を通らない（`engine/src/inkling2/ink_main.cpp:879-881`; 初期値は `engine/src/inkling2/ink_backend.h:17-21`）。
- モデルで layer-split が有効でないこと。`model_.ls_active` の場合は環境変数を読まず、自動選択も行わない（`engine/src/inkling2/cuda/ink_cuda_backend.cu:292-300`）。
- 自動選択が許可される場合でも、選ばれるのは 512 / 1024 / 2048 のいずれか。残 VRAM、slot 数、context までにまだ必要な K/V の量で 1024 または 2048 が選ばれる条件が決まり、どちらも足りなければ 512 のまま。slot 上限は 1–3 slot で 2048、4–15 で 1024、16 以上で 512（`engine/include/strata/core/ink_chunk.hpp:18-49`）。
- CUDA の空きメモリ取得に失敗して `led_loaded < 0` となる場合、auto 算出関数は 512 を返す（`engine/src/inkling2/cuda/ink_cuda_backend.cu:271-282`; `engine/include/strata/core/ink_chunk.hpp:42-49`）。

## 実行時の詳細

環境変数は CUDA backend の `init` 内で expert 配置後の空き VRAM を記録した後、runner 初期化より前に一度読み取られる。関数内 static cache はなく、この backend 初期化呼び出しで都度 `getenv` する。従って初期化後にプロセス環境を変更しても、実行中の chunk には反映されず、backend の再初期化時には再読込される。初期値 `opts.chunk` は 512、`chunk_auto` は true。自動選択が有効なら `ink_auto_chunk` の結果と初期値の大きい方を `chunk_try` として runner に渡すため、この処理は 512 を下回らせない（`engine/src/inkling2/ink_backend.h:17-21`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:282-300,322`）。

自動選択では expert 配置後の空き MiB、slot 数、GPU にまだ確保する K/V の推定量を使う。`kv_offload_mode == 1`（KV offload 明示 ON）なら追加 K/V 量を 0 とし、それ以外では `max_ctx`・初期確保 context・1 position あたりの K/V byte 数などから見積もる。必要空き量は基準 1460 MiB、512 超過分 1 token あたり 0.87 MiB、余裕 1500 MiB、および K/V 成長見積もりの合計。まず slot 上限内の 2048、次に 1024 を判定し、該当しなければ 512 を返す（`engine/src/inkling2/cuda/ink_cuda_backend.cu:203-214,292-300`; `engine/include/strata/core/ink_chunk.hpp:18-49`）。

runner の初期化が `InkAllocFailure` になると、`STRATA_INK_OOM_RETRY=0` で retry が無効の場合を除き、chunk を半分にし、最小 64 まで再試行する。この別環境変数も `atoi(...) == 0` で判定される。64 でも失敗すれば backend 初期化は false で戻り、通常 CLI は `init: ...` を stderr に出して終了コード 1、serve mode は `ERR init: ...` を protocol に返して終了コード 1 となる（`engine/src/inkling2/cuda/ink_cuda_backend.cu:284-289,321-337`; `engine/src/inkling2/ink_main.cpp:1086-1095`）。

## ログと測定値

自動選択が実行された場合、stderr に `[InkCUDA] prefill chunk %d (auto: %.0f MiB free after the experts, %.0f MiB of K/V still to grow, %d slot(s); --chunk N sets it)` が出る。環境変数で自動選択を止めた場合、または `--chunk` / layer-split で分岐を通らない場合、この auto chunk ログは出ない。初期化時の割り当て失敗による縮小再試行では `[InkCUDA] not enough free GPU memory for the working buffers at chunk ...; retrying with chunk ...` が出る（`engine/src/inkling2/cuda/ink_cuda_backend.cu:292-300,324-335`）。

`engine/include/strata/core/ink_chunk.hpp:3-7,19-21,33-36` には RTX 5090・RTX 4090・RTX 3060 Ti に関する chunk ごとの速度・メモリ測定記述がある。ただし、これらはこの環境変数を設定した比較測定ではないため、本書では変数の効果として速度値を主張しない。`docs/DETAILS.md` にこの変数や Inkling prefill chunk の追加説明は見つからなかった。

## 根拠

- `engine/src/inkling2/cuda/ink_cuda_backend.cu:271-300` — expert 配置後の空き VRAM、環境変数の読み取り、K/V 成長量、自動 chunk ログ。
- `engine/include/strata/core/ink_chunk.hpp:18-49` — chunk 候補の必要メモリ計算、slot cap、auto 選択。
- `engine/src/inkling2/ink_backend.h:17-21` — chunk の既定値と `chunk_auto`。
- `engine/src/inkling2/ink_main.cpp:879-881,1086-1095` — `--chunk` による優先と backend 初期化の失敗出力。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:321-340` — runner 初期化、OOM 縮小 retry、最終的な有効 chunk。
