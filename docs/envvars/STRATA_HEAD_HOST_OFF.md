# `STRATA_HEAD_HOST_OFF`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

native output head が GPU メモリに収まらないとき、または cache 用の GPU メモリが足りないときに、head を mapped pinned host memory に置く fallback を抑止します。単独 GPU と layer split の最終 GPU stage で `NativeHead::load()` が使われる native head 経路、および単独 GPU の cache sizing 経路が対象です。環境変数を設定するだけで native head を有効にするものではありません。

## 値と判定

実装は値を parse せず `std::getenv(...) == nullptr` かどうかだけを見ます。unset の場合に fallback が許可され、何らかの値が設定されていれば fallback は抑止されます。

| 環境の状態 | 判定 |
|---|---|
| 未設定 | fallback を許可（ほかの条件も満たす場合） |
| 空文字を設定 | fallback を抑止 |
| `0`、`1`、`false` など任意の非空値 | fallback を抑止 |

大文字小文字、空白、数値としての妥当性、文字列全体は検査されません。CLI 引数によるこの判定の上書きもありません。

## 有効になる条件

環境変数が unset でも、次の条件がそろわなければ fallback は実行されません。

- `NativeHead::load()` の初回配置では、head の `cudaMalloc` が失敗するか、`STRATA_HEAD_HOST` が設定されて host 配置を要求していること。
- GPU 情報の取得に成功し、GPU が discrete であること（Metal build と integrated GPU は対象外）。
- `native_q6_k_packed_enabled()` が false であること。同 helper は `STRATA_Q6_PACKED=1`（文字列全体が厳密に `1`）なら true になり、この fallback を止めます。head の tensor type による条件ではありません。
- cache が0 slotsになった後の移動では、native head がロード済みでまだ host 上にないこと、`--vram-reserve-mib` が明示されていないこと、単一 GPU であること、layer split でないこと、`STRATA_SPILL_OFF` も unset であること。

`STRATA_HEAD_HOST_OFF` は初回配置では `STRATA_SPILL_OFF` を参照しないため、後者を設定しても `NativeHead::load()` の pinned host fallback は止まりません。一方、cache sizing 後の移動は両方が unset の場合に限られます。`--native-head-gguf` を使うか、`--native` が native head を補う経路で native head がロードされる場合にだけ関係します。layer split では最終 stage の head 読み込み時に初回配置判定が通りますが、cache sizing 後の移動条件は `!multi_gpu` のため対象外です。

## 実行時の詳細

`NativeHead::load()` は head の `cudaMalloc` 後に GPU の種別を確認します。割り当て失敗時に、discrete GPU、`STRATA_HEAD_HOST_OFF` unset、Q6_K packed mode 無効のすべてを満たすと、pinned host allocation と device pointer 取得を試み、成功すれば head のデータを host memory にコピーしてその device pointer を使います。成功時は stderr に `strata generate: short of GPU memory: the output head (...) stays in pinned host memory ...` と出ます。ここで fallback が抑止され、GPU allocation も失敗していれば load は失敗し、呼び出し元は `strata generate: <native head upload error>` を stderr に出して終了コード 1 を返します。`STRATA_HEAD_HOST` が設定されていると `cudaMalloc` を試さず allocation failure 扱いにするため、`STRATA_HEAD_HOST_OFF` も設定している場合は host 要求が失敗します。

別の経路では、cache sizing の結果が0 slotsのとき、条件を満たせばロード済み head を `NativeHead::to_host()` で host に移し、空いた GPU memory で cache を再計算します。成功時は stderr に `the cache had no room, so the output head ... moves to pinned host memory` と出ます。`STRATA_HEAD_HOST_OFF` が設定されているとこの移動条件を満たさず、続く不足診断 `no VRAM is left for the expert cache` が出ます。`STRATA_SPILL_OFF` が設定されていても同じ移動は抑止されます。

値は static cache されず、各 `NativeHead::load()` 呼び出しと cache sizing 判定の時点で読み直されます。serve の `--prefill-head-alias` 経路では request phase の間 head を unload した後、restore 時に `NativeHead::load()` が再度呼ばれるため、その load ごとに判定されます。通常のプロセスでは環境を起動後に変更するだけでは OS の process environment 自体が変わらないため、コード上の再読込だけで後から値が変化するわけではありません。

## 根拠

- `src/core/native_head.cpp:32-36,61-84,90-96`: native head load の入力条件、`STRATA_HEAD_HOST` による VRAM allocation の回避、`STRATA_HEAD_HOST_OFF` を含む初回 host fallback 条件、pinned host allocation、成功ログと load error。
- `src/core/native_head.cpp:117-136`: cache sizing 後に head を host memory へ移す処理と失敗時の `err`。
- `include/strata/core/spill_gate.hpp:8-14`, `src/program/generate.cpp:271-284`: Metal build と integrated GPU を spill 対象外にする条件。
- `src/program/generate.cpp:3377-3378,4220-4225,4351-4358,4420-4423`: `--native` / `--native-head-gguf` の入力、native preset による head 補完、`--stream-token` 要件と shard 選択。
- `src/program/generate.cpp:6417-6424,6880-6892`: layer split 最終 stage と単一 GPU の native head load、および load 失敗時の stderr と終了コード。
- `src/program/generate.cpp:7676-7704`: cache が0 slotsのときの late host move 条件、成功・失敗ログ。
- `src/program/generate.cpp:7705-7725`: host move が行われない場合の no-VRAM diagnostic。
- `src/program/generate.cpp:15387-15404`: serve の `--prefill-head-alias` で unload 後に `NativeHead::load()` を再度呼ぶ restore 経路。
- `src/kernels/cuda/native_mmvq.cu:2949-2955`: `STRATA_Q6_PACKED` が厳密に文字列 `1` のとき true を返す helper。これは `STRATA_HEAD_HOST_OFF` 自体の値判定ではなく、初回 fallback 条件にある除外条件。
