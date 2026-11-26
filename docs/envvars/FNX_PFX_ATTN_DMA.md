# `FNX_PFX_ATTN_DMA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`strata-split`（sFNX）の複数 GPU prompt prefill において、他カードから host receive buffer に届いた attention partials を merge 前に device memory へコピーする経路を切り替える。CUDA build では unset 時に有効、HIP build では unset 時に無効で、値が有効なら各 partial piece の到着 flag を待つ専用 stream `st3` 上で host-to-device copy を行い、merge kernel は device buffer を読む。無効なら merge stream が全 piece の flag を待ち、mapped host receive buffer を直接 merge に渡す（`engine/src/split/src/prefill.cu:377-382, 785-816, 1043-1059`）。

これは Strata の通常エンジン共通の設定ではなく、任意ビルドの `strata-split` 用である。split は `STRATA_BUILD_SPLIT` で opt-in となる別 executable で、2〜4 カード構成のターゲットとして定義される（`engine/src/split/CMakeLists.txt:1-7, 116-145`）。

## 値と判定

`fnx::env_int` が `std::getenv` で値を読み、符号付き 10 進整数として文字列全体を `std::strtoll` で変換する。受理されるのは `long long` の範囲内で、任意の `+` / `-` と数字だけからなる文字列。空文字、数字以外、数字の後ろに文字がある値、前後の空白、範囲外の値は整数として無効で、`<名前>: '<値>' is not a whole number` の例外になる。判定は変換値が 0 かどうかだけで、0 以外は有効。したがって `1`、`-1`、`+2` は有効、`0` と `-0` は無効、`true`、空文字、`0anything` は無効。追加の clamp や許容値チェックはない（`engine/src/split/src/env.hpp:15-21, 33-40`）。

| build | unset | 有効になる値の例 | 無効になる値の例 |
|---|---:|---|---|
| HIP (`FNX_HIP`) | 0 | `1`, `-1`, `+2` | `0`, `-0` |
| CUDA (`FNX_HIP` なし) | 1 | `1`, `-1`, `+2` | `0`, `-0` |

どちらの build でも、値の文字列判定規則は同一。設定時の空文字は unset 扱いではなく、parse error になる。build ごとの既定値は `engine/src/split/src/prefill.cu:1043-1049` にある。

## 有効になる条件

- `strata-split` がビルドされ、その engine の prompt prefill buffer が初期化されること。CMake では CUDA または HIP の split build に限ってターゲットが追加され、カード数は 2、3、4（`engine/src/split/CMakeLists.txt:20-26, 116-145`）。
- CUDA では `FNX_HIP` を定義しない build、HIP では `FNX_HIP=1` の build でそれぞれ異なる unset 既定値が使われる（`engine/src/split/CMakeLists.txt:121-142`）。
- 実際に他カードの attention partials を merge する prompt attention 経路で使われる。`FNX_PF_ATTN_DEC` が有効な場合は decode attention を使い、prompt attention の `pf_attention` 呼び出しを迂回する（`engine/src/split/src/prefill.cu:1022-1026, 1672-1689`）。
- この変数自体の条件は `FNX_PF_DMA` による分岐と連動していない。HIP の説明コメントでは両方が opt-in とされるが、`attn_dma` の判定は独立しており、`FNX_PF_DMA` は別の prompt ring receive の設定である（`engine/src/split/src/prefill.cu:1043-1048, 1209-1216`）。
- CLI 引数や設定ファイルによる上書きは、この値の読み取り箇所にはない。

## 実行時の詳細

`Engine` の構築中に `prefill_alloc()` が呼ばれ、カードごとの `Pf` buffer を用意する際に環境値を読み取る（`engine/src/split/src/engine.cu:317-318`; `engine/src/split/src/prefill.cu:854-865, 1043-1049`）。関数内 static cache はなく、`prefill_alloc()` 内のカードごとの初期化で判定される。各 `Pf` に設定された値は、その `Engine` の buffer allocation 後には環境を変更しても反映されない。

有効時は `arecv_dev` と二組の copy / merge event、および非同期 stream `st3` を作る。各 attention piece について、その slot の flag が現在の sequence に達するのを `st3` で待ち、該当範囲を host receive buffer から device buffer に非同期コピーする。copy 完了 event と各カードの send 完了を merge stream が待ってから `attn_prompt_merge` を実行し、次回その buffer set を再利用する時は前回の merge 完了を待つ（`engine/src/split/src/prefill.cu:785-816, 1050-1059`）。無効時は専用 copy stream / device receive buffer を作らず、merge stream 自身が全 slot・piece の flag と send 完了を待ってから、host receive buffer を `attn_prompt_merge` に渡す（同 `prefill.cu:809-816`）。

## ログと測定値

この変数の有効・無効を知らせる専用ログは確認できない。値が整数でない場合、`env_int` の例外メッセージは `FNX_PFX_ATTN_DMA: '<値>' is not a whole number`。engine 構築中の例外は sFNX の失敗経路で stdout に `ERR <例外文>`、stderr に `sfnx: failed: <例外文>` を出し、終了コード 1 で終了する（`engine/src/split/src/env.hpp:33-40`; `engine/src/split/tools/sfnx.cpp:1094-1103, 1123-1135`）。

ソースコメントには CUDA での性能・logit 同一性の測定主張があるが、機種・OS/backend・測定回数などの条件が示されていないため、一般化できる測定値としては記載しない（`engine/src/split/src/prefill.cu:1048`）。

## 根拠

- 全参照検索では、変数名は `engine/src/split/src/prefill.cu:377, 1045-1048` にだけ現れる。実際の読み取りは同ファイル `1046, 1048` の2か所。
- helper の厳密な整数変換と unset 時 fallback: `engine/src/split/src/env.hpp:15-21, 33-40`。
- DMA / 非 DMA の attention partials 処理: `engine/src/split/src/prefill.cu:758-820, 1043-1059`。
- build 条件と対象 executable: `engine/src/split/CMakeLists.txt:1-7, 20-26, 116-145`。
