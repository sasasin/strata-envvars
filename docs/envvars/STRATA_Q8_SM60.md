# `STRATA_Q8_SM60`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA native MMVQ の Q8_0 decode で、通常 kernel の代わりに Pascal compute capability 6.0 向けの `q8sm60::kernel` を選ぶ opt-in です。主な対象は native dense の Q8_0 行列と native output head です。変数が有効でも、存在する Q8_0 tensor がない場合は演算に使われません。読み取りと有効判定は `engine/src/kernels/cuda/native_mmvq.cu` の `q8_sm60_on()`、kernel 起動は同ファイルの `q8_packed_mmvq()` と `engine/src/kernels/cuda/q8_sm60.cuh` にあります（`native_mmvq.cu:2625-2636, 2767-2805, 2983-2995`、`q8_sm60.cuh:53-105`）。

この経路は通常の exact kernel と積算順序が異なるため、結果は bitwise 一致しません。整数 dot は正確ですが、float の加算順序が異なるとソースに記載されています（`q8_sm60.cuh:17-18, 81-104`）。Q8_0 以外の型や prompt GEMM をこの変数が切り替える処理はありません。通常の out-of-place packed 経路では native dense の GGUF 重みを prompt path 用に残し、decode 用コピーを追加します。`STRATA_Q8_INPLACE=1` の別経路では重みを packed layout で格納します（`native_dense.cpp:469-483, 498-516`）。

## 値と判定

kernel を有効化する判定は `getenv` の値全体が厳密に文字列 `1` と一致する場合だけ true です。数値変換や大文字小文字変換はせず、`static const bool` に初回評価結果を保存します（`native_mmvq.cu:2625-2635`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA kernel の有効判定 | false | `1` | 空文字、`0`、`true`、`01`、`10`、`1 `、` 1` など、文字列 `1` 以外すべて |
| head の一部補助判定 | head load 時に設定なし扱い | 値の内容を問わず、環境変数が存在すれば設定あり | unset のみ。空文字も設定あり |

head の補助判定は kernel の有効判定とは別です。値が空または不正でも、Q8_0 head の peer split を抑止し（`native_head.cpp:131-136`）、manifest に `repacked (STRATA_Q8_SM60)` と付記し（同 `:281-288`）、`to_host()` による pinned host memory への移動を抑止します（同 `:297-300`）。このため無効値でも head 配置に副作用があります。

## 有効になる条件

- CUDA native MMVQ 経路であること。`__HIPCC__` build では `q8_sm60_on()` が常に false を返し、pack 関数も false を返します。Metal の stub も pack を行わず false を返します（`native_mmvq.cu:2625-2628, 3045-3050`、`engine/metal/src/engine/stubs_0145.cpp:149-154`）。
- 値が厳密に `1` で、該当する重みが Q8_0 であること。dense の通常の packed eligibility は `n_in >= 128`、`n_in % 32 == 0`、`n_out > 0` です（`native_mmvq.cu:2991-2995`）。native head は Q8_0 の場合に pack を試みます（`native_head.cpp:261-265`）。
- shape が kernel の shared-memory / launch 条件を満たすこと。CUDA kernel が起動できない場合は、packed exact kernel または通常の GGUF-layout kernel へ戻る経路があります（`native_mmvq.cu:2767-2800, 2991-2995`）。
- `STRATA_Q8_PACKED=1` も native Q8 packed layout を有効にしますが、この変数単独でも `q8_sm60_on()` が true なら packed copy が登録され、Pascal kernel を優先します（`native_mmvq.cu:2983-2995, 2770-2796`）。
- `STRATA_Q8_INPLACE=1` と併用すると dense load が eligible tensor を in-place packed にする経路があります。`STRATA_Q8_SM60` が有効な場合、in-place eligibility も Q8 shape 条件を使います（`native_dense.cpp:469-483, 498-516`、`native_mmvq.cu:2991-3012, 3111-3142`）。
- `STRATA_Q8_SM60_BPS` は同 kernel の blocks-per-SM を上書きする別変数です。`atoi` の結果が正ならその値、そうでなければ GPU に応じた既定値を使います（`q8_sm60.cuh:108-136`）。

## 実行時の詳細

`q8_sm60_on()` は最初に呼ばれた時点で値を一度読み、以後は cache した bool を返します。process 中に環境を書き換えてもこの判定は更新されません。成功時は stderr に一度 `strata q8 sm60: Q8_0 decode GEMVs on the Pascal kernel (STRATA_Q8_SM60=1)` と出します（`native_mmvq.cu:2629-2635`）。

native dense の load は、Q8_0 tensor（`blk.1.ple_key.weight` を除く）について enabled と eligibility を確認し、通常は元の GGUF weight を保持したまま同サイズの packed plane copy を作ります。head load も Q8_0 の output head を pack します（`native_dense.cpp:498-516`、`native_head.cpp:261-265`）。pack copy の割当または変換に失敗した場合は `strata q8 sm60: no VRAM for the packed ...; it keeps the GGUF layout` または `strata q8 sm60: packing the ... failed; it keeps the GGUF layout` を出し、その tensor は GGUF layout に残ります（`native_mmvq.cu:3050-3075`）。成功時のログは `strata q8 sm60: packed <what> (<n_out> x <n_in>, <MiB> MiB more VRAM)` です。native dense 側の追加 packed upload 失敗は `native dense packed upload <tensor>: <CUDA error>` として load を失敗させます（`native_dense.cpp:507-515`）。

decode の `native_q8_0_mmvq()` は登録済み重みを `q8_packed_mmvq()` に渡します。sm60 kernel が適用できない shape では packed exact layout または通常 kernel に fallback します。in-place packed tensor が sm60 kernel により拒否された場合は stderr に `strata q8 inplace: q8sm60 declined in-place tensor (...)` を出して abort します（`native_mmvq.cu:2767-2800, 3699-3704`）。

Q36 engine も `native_q8_0_packed_enabled()` と eligibility を使って packed Q8_0 planes を登録するため、同じ CUDA build ではこの opt-in の影響を受けます（`engine/src/qwen35/q36_engine.cu:1438-1450`）。別途 `STRATA_MTP_Q8_SM60` が有効な MTP drafter の行列を sm60 kernel に載せる経路もありますが、これは別設定による opt-in です（`engine/src/core/mtp.cpp:106-115, 490-508, 996-1004`）。

## ログと測定値

有効判定時と pack の成功・失敗時に上記 stderr ログが出ます。成功ログは `quiet` pack では抑止されます（`native_mmvq.cu:2629-2635, 3045-3075`）。Strata の `docs/OLDER_GPUS.md` は PH402（4 GP100 dies）、Windows 11、driver 581.80、CUDA 12.9、engine 0.1.40.2、Flash-Next IQ3_XXS、32K、greedy 256 tokens、2–3 回の interleaved starts で、Q8_0 dense shard の decode 平均を 28.3 から 38.9 tok/s と報告しています。これは同資料に記載された条件下の測定値です（`docs/OLDER_GPUS.md:341-352`）。

## 根拠

- `engine/src/kernels/cuda/native_mmvq.cu:2625-2635` — exact 値判定、cache、有効ログ。
- `engine/src/kernels/cuda/native_mmvq.cu:2767-2800, 2983-3012, 3045-3075, 3111-3142, 3699-3704` — eligibility、pack、decode 分岐、fallback と失敗経路。
- `engine/src/core/native_dense.cpp:469-483, 498-516` — dense tensor の in-place / packed copy。
- `engine/src/core/native_head.cpp:131-136, 261-288, 297-300` — head load、presence 判定の副作用と配置。
- `engine/src/kernels/cuda/q8_sm60.cuh:17-18, 53-105, 108-136` — 演算の差と起動 kernel の処理。
- `engine/src/qwen35/q36_engine.cu:1438-1450` — Q36 の packed registration。
- `engine/metal/src/engine/stubs_0145.cpp:149-154` — Metal pack stub。
- `engine/src/core/mtp.cpp:106-115, 490-508, 996-1004` — MTP の別 opt-in。
- `docs/OLDER_GPUS.md:341-352` — 条件付き測定値。
