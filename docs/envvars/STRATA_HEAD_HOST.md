# `STRATA_HEAD_HOST`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

ネイティブ出力 head (`output.weight`) の重みを GPU VRAM ではなく mapped pinned host memory に置くよう要求する。`NativeHead::load` はこの変数が設定されていると、最初の `cudaMalloc` を行わずに割当失敗扱いにし、その後の host-memory fallback を試す。head の計算自体は同じ `weights_` ポインターを `native_mmvq` / `native_q5_k_f32` に渡す経路であり、変数が変えるのはロード先とメモリ配置である（`engine/src/core/native_head.cpp:218-245`, `engine/src/core/native_head.cpp:320-352`）。

この機能が使われるのは `--native-head-gguf` が有効な `strata generate` 経路である。`--native-head-gguf` は `--stream-token` を必要とし、単一 GPU では `native_head.load`、layer split では最後の stage の `st.head.load` が呼ばれる（`engine/src/program/generate.cpp:1262`, `engine/src/program/generate.cpp:3927`, `engine/src/program/generate.cpp:5165`, `engine/src/program/generate.cpp:5379-5380`, `engine/src/program/generate.cpp:7775-7783`, `engine/src/program/generate.cpp:8391-8400`）。

## 値と判定

`NativeHead::load` 内で `std::getenv("STRATA_HEAD_HOST") != nullptr` を判定するだけで、値を parse しない（`engine/src/core/native_head.cpp:125-130`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `NativeHead::load` に到達した場合 | VRAM 割当を試す | 空文字、`0`、`1`、`false`、`0anything` など、環境に存在する任意の文字列 | なし（環境変数が存在すれば値の内容によらず要求扱い） |

大文字小文字、空白、数値としての妥当性、文字列全体は検査しない。数値変換や範囲・境界値もない。優先順位の形で CLI 値を読むことはなく、CLI は native head をロードするかどうかを決める。`--native-head-gguf` が未指定で解決後も空ならこの `NativeHead::load` 経路には入らず、本変数単独では作用しない（`engine/src/program/generate.cpp:8391-8396`）。

## 有効になる条件

- native output head が有効であること。`--native-head-gguf PATH` は `--stream-token` を要求する。ネイティブ preset が設定されている場合は空の `native_head_gguf` に preset が補われる（`engine/src/program/generate.cpp:5165`, `engine/src/program/generate.cpp:5379-5380`）。
- head の `output.weight` が native MMVQ 対応型で canonical head 寸法に一致し、データ payload が完全であること。寸法は正の int32 範囲で入力幅が 256 の倍数でなければならない。これらの検証は環境変数を読む前に行われる（`engine/src/core/native_head.cpp:98-123`）。
- `NativeHead::load` が呼ばれること。通常の単一 GPU 起動ではロード時、layer split では最後の stage のロード時に判定する。`--prefill-head-alias` で head を unload した後に復元する場合も同じ関数が再度呼ばれ、その時点で環境を読み直す（`engine/src/program/generate.cpp:7775-7783`, `engine/src/program/generate.cpp:8391-8396`, `engine/src/program/generate.cpp:19164-19180`）。
- host fallback が許可されること。ロード時に CUDA device 情報が得られ、GPU が discrete で、Metal build でない必要がある。`spill_allowed` は Metal build または integrated GPU では false になる（`engine/src/core/native_head.cpp:222-229`, `engine/include/strata/core/spill_gate.hpp:8-14`）。
- `STRATA_HEAD_HOST_OFF` が未設定で、`native_q6_k_packed_enabled()` が false であること。これらの条件により fallback が抑止されると、本変数によって VRAM 割当を飛ばした状態から続行できず、head load は失敗する（`engine/src/core/native_head.cpp:130`, `engine/src/core/native_head.cpp:222-252`）。Q6 packed 判定は `STRATA_Q6_PACKED` の文字列が厳密に `1` の場合に有効となり、関数内 `static` に初回評価結果を保存する（`engine/src/kernels/cuda/native_mmvq.cu:3145-3150`）。
- 設定時は `STRATA_PEER_HEAD_SPLIT` による peer split 条件も `!ask_host` により成立しない。未設定時の peer split には、別途その変数の数値が非ゼロ、異なる peer GPU、P2P 可用性などの条件がある（`engine/src/core/native_head.cpp:130-150`）。

## 実行時の詳細

`STRATA_HEAD_HOST` は `NativeHead::load` の呼び出しごとに直接読み取られ、変数自体の static cache はない（`engine/src/core/native_head.cpp:98-130`）。設定時は `status` を `cudaErrorMemoryAllocation` に初期化するため、head の VRAM `cudaMalloc` を試さない。続いて device 情報から discrete GPU と確認でき、`STRATA_HEAD_HOST_OFF` が unset、Q6 packed が off の場合、`cudaHostAlloc` で mapped / portable pinned memory を確保し、`cudaHostGetDevicePointer` で device alias を得て GGUF の重みをコピーする。その alias を `weights_` に保持し、通常と同じ head kernel 呼び出しに渡す（`engine/src/core/native_head.cpp:218-245`, `engine/src/core/native_head.cpp:254-265`, `engine/src/core/native_head.cpp:320-352`）。

未設定時は VRAM `cudaMalloc` を先に試す。割当が失敗した場合も、同じ discrete GPU・`STRATA_HEAD_HOST_OFF` unset・Q6 packed off の条件なら host fallback が行われる。従って本変数は fallback を要求する指定であり、unset は host fallback を禁止する指定ではない（`engine/src/core/native_head.cpp:222-245`）。

本変数の判定は load ごとであり、起動時の一度きりとは限らない。一方、`STRATA_Q6_PACKED` 判定は別関数内で static cache される。後段の cache 不足時に自動で head を host に移す経路は別条件で制御され、単一 GPU では `STRATA_HEAD_HOST_OFF` と `STRATA_SPILL_OFF` の unset などを確認するが、`STRATA_HEAD_HOST` はその分岐では読み直さない（`engine/src/program/generate.cpp:9346-9373`, `engine/src/program/generate.cpp:9903-9918`）。`STRATA_SPILL_OFF` はこの後段の自動移動条件にはあるが、`NativeHead::load` 内の明示要求による fallback 条件には含まれない（`engine/src/core/native_head.cpp:222-229`）。

## ログと測定値

host fallback に成功すると stderr に `strata generate: short of GPU memory: the output head (%llu MiB) stays in pinned host memory and is read over PCIe for every logits row: decode is slower` を出す。この文言は明示的な `STRATA_HEAD_HOST` 要求時にも同じである（`engine/src/core/native_head.cpp:228-239`）。native manifest が有効なら、head の配置理由に `held in mapped pinned host memory (short of VRAM or STRATA_HEAD_HOST)` が記録される（`engine/src/core/native_head.cpp:281-288`）。

host fallback が使えず VRAM への割当も成功扱いにならない場合は `native head upload: <CUDA error>` を返す。単一 GPU 呼び出し元はその内容と VRAM 情報を stderr に出して終了コード 1 で終了する。layer split の呼び出し元も head エラーを stderr に出し、終了コード 1 で終了する（`engine/src/core/native_head.cpp:241-252`, `engine/src/program/generate.cpp:7777-7783`, `engine/src/program/generate.cpp:8394-8396`）。

## 根拠

- `engine/src/core/native_head.cpp:98-150` — head load、環境変数の設定有無判定、peer split 抑止。
- `engine/src/core/native_head.cpp:218-265` — VRAM allocation の省略、host fallback、重みの配置。
- `engine/src/core/native_head.cpp:281-288` — manifest 上の配置理由。
- `engine/src/core/native_head.cpp:320-362` — 配置後の head 実行経路。
- `engine/src/program/generate.cpp:7775-7783`, `engine/src/program/generate.cpp:8391-8400`, `engine/src/program/generate.cpp:19164-19203` — 呼び出し条件と復元時の再 load。
- `engine/include/strata/core/spill_gate.hpp:8-14` — Metal / integrated GPU の spill gate。
- `engine/src/program/generate.cpp:9346-9373`, `engine/src/program/generate.cpp:9903-9918` — 後段の自動 host 移動と抑止条件。
- `engine/src/kernels/cuda/native_mmvq.cu:3145-3150` — fallback 条件に関係する Q6 packed 判定。
