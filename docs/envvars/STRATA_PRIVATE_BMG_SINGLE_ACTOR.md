# `STRATA_PRIVATE_BMG_SINGLE_ACTOR`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL 実装の private Battlemage/B60 デコードレイアウト経路で、通常は別デバイス用として扱われる verifier／draft 側の処理を単一アクターとして扱うためのスイッチ。値だけではレイアウトを有効にせず、`STRATA_PRIVATE_B60_DECODE_LAYOUT` と組み合わせて固定の単一デバイス no-host decode 条件を満たす必要がある。`b60_single_actor_requested()` が判定し、verifier staging、decode kernel の分岐、限定された B60 キャッシュ経路に使われる（`sycl/include/b60_layout_state.hpp:7-20`, `sycl/src/program/generate.cpp:4508-4515`）。

## 値と判定

`std::getenv` の戻り値が null でなく、先頭文字が `'1'` のときだけ true。文字列全体の比較・数値変換はしない。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL の `b60_single_actor_requested()` を含むビルド | false | `1`, `10`, `1anything` | 空文字、`0`, `0anything`, `true`, `TRUE`, ` 1`, `-1` |

大文字小文字、後続文字、数値としての妥当性は検査しない。先頭 1 文字だけが判定対象である。関数内の `static const bool` に初回呼び出し結果を保存するため、その後のプロセス環境の変更は反映されない（`sycl/include/b60_layout_state.hpp:8`）。

## 有効になる条件

- Strata の SYCL 実装を使うこと。この名前の直接の読み取りは `sycl/include/b60_layout_state.hpp:8` のみで、CUDA/HIP 実装や Python サーバー側での読み取りはない。
- 実行時に `STRATA_PRIVATE_B60_DECODE_LAYOUT` も先頭文字 `1` で有効であること。どちらかが無効なら single layout の初期化・bind 経路には入らない（`sycl/include/b60_layout_state.hpp:7-8`, `sycl/src/program/generate.cpp:4509`, `sycl/src/program/generate.cpp:7876-7880`）。
- `generate` の起動条件がすべて成立すること: serve モード、`native_pack`、単一 GPU（`multi_gpu` でなく split device もなし）、pipeline windows 無効、`no_prefill_borrow` 有効、batch 0、prompt cache 0、spec が 6 以下、adapt async 無効、`STRATA_VERIFY_NO_HOST` と `STRATA_VERIFY_DEVICE_PLAN` は unset でなく先頭文字が `0` 以外、`STRATA_PRIVATE_PACKED_REGISTER` は unset でなく先頭文字が `1`、モデル形状 `n_layers=48, n_expert=512, n_embd=2560, n_ff=640, hc=4, hc_lr=320` が必要。いずれかを満たさないと `std::invalid_argument("B60 single layout requires the fixed single-device no-host decode scene")` が投げられる（`sycl/src/program/generate.cpp:4509-4515`; `env_on` の判定は `sycl/src/core/verify.cpp:149-152`）。
- 検証側の native expert 経路では device plan が lean で `gy == 0` であることも必要。不成立なら `std::logic_error("B60 single staging needs the complete device plan")`（`sycl/src/core/verify.cpp:1648-1657`）。
- キャッシュ・次世代 pool の最適化は別の環境変数や重み形状等にも依存する。たとえば head cache は `STRATA_PRIVATE_IQ4_HEAD_SOA` が有効で Battlemage 世代かつ指定された行列寸法の場合に限られ、MTP Q8 cache は `STRATA_PRIVATE_B60_NEXT_POOL` と `STRATA_PRIVATE_MTP_Q8_SOA` の両方が有効な場合に限られる（`sycl/include/b60_weight_cache.hpp:5-8`, `sycl/include/b60_mtp_q8_cache.hpp:5-8`, `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3708-3715`, `sycl/src/kernels/cuda/native_mmvq.dp.cpp:4141-4146`）。この対象変数だけで各 cache や kernel は有効にならない。

## 実行時の詳細

`generate` は B60 layout と single actor の両方が有効な場合、重み・native head 用の layout を準備し、decode 準備時に `bind_single(...)` と `packed(true)` を呼ぶ。bind は resident expert を single staging に結び付け、`B60_SINGLE_LAYOUT` の状態行を stderr に出す。verifier の native expert 処理は通常の grouped 呼び出しに加えて `b60_stage_single_experts(...)` を実行する（`sycl/src/program/generate.cpp:4508-4515`, `sycl/src/program/generate.cpp:7876-7888`, `sycl/include/b60_layout_host.hpp:110-124`, `sycl/src/core/verify.cpp:1648-1671`）。

`B60MainActorScope` は verify 処理の開始時に現在の actor 状態を保存し、single actor または layout が要求されていれば main actor 状態を立て、スコープ終了時に元へ戻す（`sycl/src/core/verify.cpp:941`, `sycl/include/b60_layout_state.hpp:14-20`）。この状態や要求値を参照する kernel 分岐は、Battlemage 判定、layout/cache/pool 設定、テンソル寸法や token 数などの条件がさらに合う場合だけ選択される（例: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3715`, `sycl/src/kernels/cuda/iq_kernels.dp.cpp:7388-7411`, `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:2525-2538`）。

環境値は helper の初回呼び出し時に static cache される。CLI 引数からこの値を上書きする Strata 側の読み取りや転送は見つからず、適用は当該プロセス内である。

## ログと測定値

この変数の有効・無効だけを知らせるログは見つからない。single layout の bind が通ると stderr に `B60_SINGLE_LAYOUT resident_slots=%lld total_experts=%lld staging_cap=80` が出る（`sycl/include/b60_layout_host.hpp:117-124`）。起動条件不一致時は上記の `std::invalid_argument`、完全な device plan でない場合は `std::logic_error` 経路になる（`sycl/src/program/generate.cpp:4513-4515`, `sycl/src/core/verify.cpp:1654-1656`）。本変数に対応する条件付き性能測定値は確認できなかった。

## 根拠

- 読み取り、値判定、初回値の cache、actor 状態: `sycl/include/b60_layout_state.hpp:7-20`
- 起動時の有効条件と single layout 準備: `sycl/src/program/generate.cpp:4508-4515`
- decode 準備時の single bind: `sycl/src/program/generate.cpp:7876-7888`
- verifier の staging 分岐と失敗条件: `sycl/src/core/verify.cpp:1648-1671`
- single staging の準備・ログ・終了処理: `sycl/include/b60_layout_host.hpp:110-137`
- actor/cache 条件の例: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3715`, `sycl/src/kernels/cuda/native_mmvq.dp.cpp:4141-4146`, `sycl/src/kernels/cuda/iq_kernels.dp.cpp:7388-7411`, `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:2525-2538`
