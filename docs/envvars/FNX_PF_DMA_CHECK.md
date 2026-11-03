# `FNX_PF_DMA_CHECK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。Strata の作業ツリーは `## main...origin/main` で、未コミット変更はありません。調査対象は Strata 所有ソースです。

## 役割

`strata-split` の prompt prefill にある multi-GPU host-memory ring で、host buffer から device buffer への DMA copy 後に、copy 先と元 host buffer の値を比較する診断 kernel を有効にします。計算経路や DMA の選択自体を切り替える変数ではありません。`strata-split` は通常のビルドでは無効で、Qwen3.8-Flash-Next の全層を Linux 上の 2〜4 枚の NVIDIA または AMD GPU に分割する別エンジンです（`CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:1-7,92-115`）。

## 値と判定

`src/split/src/prefill.cu:898` は `fnx::env_int("FNX_PF_DMA_CHECK", 0) != 0` を使います。`env_int` は未設定なら既定値を返し、設定済みなら符号付き 10 進整数全体を `strtoll` で読みます（`src/split/src/env.hpp:15-21,33-40`）。

| 状態 | 結果 |
|---|---|
| 未設定 | `0`。比較を無効にする |
| 空文字 | 整数として不正。例外 `FNX_PF_DMA_CHECK: '' is not a whole number` |
| 整数 `0`（例 `0`, `+0`, `-0`, `00`） | 無効 |
| 0 以外の整数（正負どちらも可） | 有効 |
| 整数でない文字列、前後の空白、数字の後ろに文字がある値 | 不正値として例外 |
| `long long` の範囲外 | `strtoll` の範囲エラーで不正値として例外 |

文字列全体が符号と数字だけであることを要求します。小数、基数接頭辞、空白、末尾文字は受け付けません。値域の追加制限や clamp はなく、0 との比較だけです。例外は `std::runtime_error` で、設定値を読む CLI 引数による上書きはありません。

## 有効になる条件

- `STRATA_BUILD_SPLIT=ON` でビルドした `strata-split` または同じ engine を使う `split_fnx_run` の経路が対象です。通常の Strata engine でこの変数を読む箇所は確認できません（`CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:92-115,153-164`）。
- `FNX_PF_DMA_CHECK` が非 0 でも、prompt の ring が host-memory copy-engine 経路を使い、該当する DMA copy が発行される必要があります。`FNX_PF_DMA=0` では receive/gather を host-memory kernel 読み取り経路にするため、比較 kernel は起動されません。`FNX_PF_DMA` の既定値は CUDA で 1、HIP で 0 です（`src/split/src/prefill.cu:891-898`; copy 条件は `src/split/src/pf_common.cuh:219-227,241-259,274-288`）。
- `FNX_PF_RING_SM` が非 0 なら GPU-thread ring の `ring_sum` が使われ、copy-engine ring を通らないため、この比較は使われません（`src/split/src/prefill.cu:738-740,1241-1246,1299-1306`）。
- HIP で RCCL による prompt sum が有効な場合、`pf_ring` は RCCL all-reduce の後に戻るため、ring checker を通しません（`src/split/src/prefill.cu:512-533`）。
- `FNX_PF_OVERLAP` は比較を無効にしません。overlap 経路も `pf_ring` を呼びます（`src/split/src/prefill.cu:821-830,1151-1159`）。CLI オプション、モデル設定ファイル、他の値による `FNX_PF_DMA_CHECK` 自体の優先上書きはありません。

## 実行時の詳細

`Engine` のコンストラクターは `prefill_alloc()` を呼び、その中でカードごとに ring の DMA 設定と `FNX_PF_DMA_CHECK` を読み取って `PfRing::dma_check` に保存します（`src/split/src/engine.cu:31,272-275`; `src/split/src/prefill.cu:625-634,883-905`）。エンジン生成時の読み取りであり、既存エンジンの実行中にプロセス環境を書き換えても保存済み設定は更新されません。別の Engine を作れば再び読み取ります。

ring の receive copy（`ring in`）と gather 出力 copy（`ring out`）では、DMA copy の後に同じ stream 上で `k_pfr_cmp` を起動します。kernel は device 側の `uint4` と、比較時点の host 側の 4 word を比較します。HIP は system scope atomic load、CUDA は uncached load を使います。不一致があれば、receive は error bit 64、gather は bit 128 を `err` に立てます（`src/split/src/pf_common.cuh:139-153,219-225,245-251,274-286`）。比較 kernel 自身は差分の内容を出力しません。

prefill は各カードの ring error を回収し、非 0 なら `prefill: ring error <値>` 例外を投げます（`src/split/src/prefill.cu:1319-1335`）。同じ error word には他の ring エラーも含まれ得るため、この数値だけでは DMA check 起因と断定できません。`sfnx` では最終的に `ERR ...` を標準出力、`sfnx: failed: ...` を標準エラーに出して終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1027-1035,1085-1092`）。`split_fnx_run` では `fnx_run: ...` を標準エラーに出し終了コード 1 です（`src/split/tools/fnx_run.cpp:1364-1373`）。不正値を読む段階で例外となった場合、`sfnx` の Engine 初期化 catch は上記の `fail` 経路を通ります（`src/split/tools/sfnx.cpp:1055-1062`）。

## 根拠

- 候補名の全参照を `rg` で確認したところ、Strata ソースでの実値読み取りは `src/split/src/prefill.cu:898` の一箇所でした。他の参照は `src/split/src/prefill.cu:307,892` と `src/split/src/pf_common.cuh:137-138` のコメントです。読み取り箇所があるため、候補一覧との食い違いではありません。
- 環境値の parse: `src/split/src/env.hpp:15-21,33-40`。
- split エンジンの対象・build 条件: `CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:1-7,92-115,153-164`。
- 設定値の保持、backend ごとの `FNX_PF_DMA` 既定値: `src/split/src/prefill.cu:883-905`。
- checker と各 copy 経路: `src/split/src/pf_common.cuh:139-153,219-227,241-259,274-288`。
- error 集約と失敗通知: `src/split/src/prefill.cu:1319-1335`, `src/split/tools/sfnx.cpp:1027-1035,1055-1062,1085-1092`, `src/split/tools/fnx_run.cpp:1364-1373`。
- Strata の実装コメントは、HIP gfx1201 の DMA 読み取りで flag 時点に host stores が見えない場合を調べる用途としてこの変数を挙げています。ただし、ここではそのコメントを独立に再現・測定した結果とは扱いません（`src/split/src/prefill.cu:891-892`）。
