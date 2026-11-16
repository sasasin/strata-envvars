# `STRATA_PRIVATE_B60_DECODE_LAYOUT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（2026-11-17 時点）。作業ツリーは `## main...origin/main`（`git status --short --branch` に追加変更なし）。

## 役割

この非公開 SYCL 実験スイッチは、B60 decode layout 候補を使う起動時の分岐を有効にします。`b60_layout_requested()` が真の場合、生成処理は通常レイアウトのまま進まず、条件に合うモデル・実行設定で expert 重みを B60 用に準備して `packed(true)` を呼びます。`Layouts::packed(true)` は対象行列に `b60_weight_permute_many` を実行し、packed 状態を設定します（`sycl/include/b60_layout_state.hpp:7`、`sycl/src/program/generate.cpp:7876-7887`、`sycl/include/b60_layout_host.hpp:126-135`）。

この変数だけで全ての B60 専用経路が動くわけではありません。通常の二段パイプライン経路では固定の all-resident decode 条件と `STRATA_PRIVATE_PACKED_REGISTER=1` が必要です。別の single-actor 経路には追加の固定条件があります（`sycl/src/program/generate.cpp:4509-4515,7876-7887`）。

## 値と判定

SYCL の `b60_layout_requested()` が初めて呼ばれたとき、`std::getenv` の結果が非 null で、先頭文字が文字 `'1'` なら真です。文字列全体の比較・数値変換はしません。従って未設定、空文字、`0`、`true`、` 1` は偽、`1`、`1anything`、`10` は真です。大文字小文字や後続文字は判定に影響しません。関数内 `static const bool` に保存されるため、プロセス中の環境変更は初回評価後の結果に反映されません。既定値は偽です（`sycl/include/b60_layout_state.hpp:7`）。

| 条件 | unset / 空文字 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| SYCL 実行ファイルで同関数が呼ばれる場合 | 偽 | 先頭が `1`（例: `1`, `1anything`） | 先頭が `1` 以外（例: `0`, `true`, 空文字） |

この変数に対する CLI 引数や別設定値からの上書き・優先順位処理はありません。CLI やモデル構成は、後述の有効条件を満たすかどうかを決めます（`sycl/src/program/generate.cpp:4509-4515,7876-7887`）。

## 有効になる条件

- この読み取りは `sycl/include/b60_layout_state.hpp` にあり、CUDA/HIP の実装から同名変数を直接読む箇所は見つかりませんでした（同リポジトリ全体の候補名検索）。したがって、Strata の SYCL 実装でのみ確認できた挙動です。
- 通常の二段パイプライン経路では、native pack、`pipe` が真かつ `n_stages == 2`、`o.no_prefill_borrow`、`o.batch == 0`、`o.prompt_cache == 0`、`o.spec <= 6`、およびモデル形状 `n_layers=48, n_expert=512, n_embd=2560, n_ff=640, hc=4, hc_lr=320` が必要です。どれかを満たさない場合は `invalid_argument("B60 layout candidate requires the fixed all-resident two-stage decode scene")` になります（`sycl/src/program/generate.cpp:7879-7881`）。
- 同経路ではさらに `STRATA_PRIVATE_PACKED_REGISTER` の値が存在し、先頭文字が `'1'` である必要があります。満たさない場合は `invalid_argument("B60 packed weights require the packed register reader")` になります（`sycl/src/program/generate.cpp:7882-7883`）。
- `STRATA_PRIVATE_BMG_SINGLE_ACTOR` も先頭文字 `'1'` で有効な場合は別経路に入り、`o.serve`、native pack、単一 GPU、空の split device 指定、pipeline windows 無効、`o.no_prefill_borrow`、batch 無効、prompt cache 無効、spec が 6 以下、async adapt 無効、および同じモデル形状が必要です。さらに `STRATA_VERIFY_NO_HOST=1`、`STRATA_VERIFY_DEVICE_PLAN=1`、`STRATA_PRIVATE_PACKED_REGISTER=1` は文字列全体の一致が必要です。不一致時は `invalid_argument("B60 single layout requires the fixed single-device no-host decode scene")` になります（`sycl/src/program/generate.cpp:4509-4515`）。
- SYCL 確認処理の `B60MainActorScope` は、レイアウトが要求されているのに重みが packed 状態でなければ `logic_error("B60 main graph recorded while weights are raw")` を投げます（`sycl/include/b60_layout_state.hpp:14-20`）。
- QSA 用候補 kernel は別条件（`STRATA_PRIVATE_B60_NEXT_POOL` など）と形状・token 数・device 条件が揃う場合に限り選択されます。Hyper-connection の Q8 up32 経路も `STRATA_PRIVATE_GR_Q8_UP32` が別途先頭文字 `'1'` であることが必要です。対象変数だけではこれらの追加経路は有効になりません（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:2525-2545`、`sycl/include/b60_layout_state.hpp:9`、`sycl/src/kernels/cuda/fused_gr.dp.cpp:2386`）。

## 実行時の詳細

値は lazy な関数内 static として初回使用時に一度読み取られ、起動中の再評価はありません（`sycl/include/b60_layout_state.hpp:7`）。通常経路では B60 layout の初期化後、固定シーン条件を検査し、`Layouts::add_device` で重み・device pointer 群を登録してから `packed(true)` を呼びます。`packed(true)` は各行列群を変換し、キュー完了後に packed 状態を立てます。single-actor 経路では先に staging を準備し、verify 実行前に residency を bind して同じく packed 化します（`sycl/src/program/generate.cpp:4508-4515,7876-7887`、`sycl/include/b60_layout_host.hpp:69-107,111-135`）。

重みが packed の間、SYCL の native expert 読み取りや B60 対応 kernel はその状態を条件に処理を選びます。例として、verify の native expert 分岐は対象変数が偽なら別の host/device staging 条件を評価し、真の場合はその枝を避けます（`sycl/src/core/verify.cpp:1648-1672`）。single-actor と layout の両方が有効な場合は staged expert を使います（同 `:1654-1657`）。

## ログと測定値

packed 化の完了時に stderr へ `B60_LAYOUT phase=packed matrices=%llu payload_bytes=%llu metadata_bytes=%llu wall_ms=%.6f` を出します。single-actor 経路の bind 完了時は `B60_SINGLE_LAYOUT resident_slots=%lld total_experts=%lld staging_cap=80` を出します（`sycl/include/b60_layout_host.hpp:124-135`）。値による警告や、未設定時の専用ログは確認できません。ソース資料に一般化できる性能測定値はありません。

## 根拠

- `sycl/include/b60_layout_state.hpp:7` — 値の読み取り、先頭文字判定、static cache。
- `sycl/src/program/generate.cpp:4508-4515,7876-7887` — 有効条件、失敗条件、初期化と適用分岐。
- `sycl/include/b60_layout_host.hpp:69-107,111-137` — 対象重みの登録、packed 化、ログ、single staging。
- `sycl/src/core/verify.cpp:1648-1672` — verify 内でのレイアウト依存分岐。
- `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:2525-2545`、`sycl/src/kernels/cuda/fused_gr.dp.cpp:2386` — 別変数にも依存する追加の候補 kernel。
