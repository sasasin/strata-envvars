# `STRATA_INK_SWA_RING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling-2 の HIP backend が使う sliding-window attention (SWA) の K/V ring 容量を token 数で上書きする。設定値は既定容量より優先して候補値になるが、モデルの SWA window 未満は採用されず、最後に context 上限で制限される。リングは 64-token page 単位で管理される。ring が window より大きい場合、batch 内の後続 token が先行 query に必要な K/V を上書きしないよう、必要に応じて `forward_batch` が batch を分割する。window と同じ容量にするとこの余裕がなくなり、実装コメントは以前の上書き状態に戻ると説明している。(`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:716-736`)

この変数を読むのは `INKLING_ENABLE_HIP` で組み込まれる Inkling-2 HIP backend だけで、CUDA、CPU、Metal、SYCL backend にはこの名前の読み取りがない。HIP backend の `init()` 中に読み取る。(`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:555-565`, `engine/src/inkling2/hip/CMakeLists.txt:30-32,74-82`)

## 値と判定

`std::getenv` で取得し、未設定または空文字なら上書きを試みない。空でない値は `std::atoi` で変換するため、文字列全体の厳密な検証はしない。数値として読める先頭部分を使い、先頭の空白や符号を受け付け、数値の後ろの文字列は無視する。たとえば `1024junk` は 1024、`true` と `0anything` は 0 になる。変換結果 `v` が `win` 以上の場合だけ候補 ring に採用し、それ未満なら既定候補のままにする。(`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:724-730`)

| 条件 | unset | 採用される例 | 採用されない例 |
|---|---|---|---|
| HIP backend の初期化、モデル window を `win` とする | `win + max(opts.chunk, 64)` が候補 | `win`、`win` 以上の整数、`win` 以上の数値で始まる文字列 | 空文字、`win` 未満、`0`、`-1`、`true`、`0anything` |

候補値はまず `kKvPageTokens`（この backend では 64）単位で切り上げられ、その後 `ctx_cap = ceil(max(max_ctx, win)/64)*64` に上限設定される。最終値は `max(win, min(candidate, ctx_cap))`。したがって十分大きな値も context 上限を越えず、window 未満にもならない。`win` はモデル設定の `c_.swa_win` を最低 1 にした値、既定候補の `opts.chunk` は `BackendOpts` の prompt chunk（既定 512、CLI の `--chunk` で設定）である。`max_ctx` は `BackendOpts` の context 上限（既定 32768、CLI では `--ctx` / `--max-context`）に由来する。(`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:725-734`, `engine/src/inkling2/ink_backend.h:17-21`, `engine/src/inkling2/ink_main.cpp:875-881`)

## 有効になる条件

- `strata-inkling` に HIP backend が組み込まれ、実行時にその backend が選ばれて `init()` が呼ばれること。CMake は `STRATA_ENABLE_HIP` が有効な場合に HIP サブディレクトリを追加し、HIP backend object を `INKLING_ENABLE_HIP=1` でコンパイルする。(`engine/src/inkling2/CMakeLists.txt:237-247`, `engine/src/inkling2/hip/CMakeLists.txt:74-82,115`)
- 実際に S(W)A visit があるモデルで ring 容量が使われる。ring page 数は `swa_ring_` から計算し、SWA pool の確保と各 batch token の page 対応に使う。SWA visit がないモデルでは、この ring による SWA K/V pool の追加はない。(`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1471-1472,1516-1522,3459-3469`)
- 値が `win` 未満、または `atoi` が 0 を返す文字列なら上書きされず、計算済みの既定候補が使われる。採用値も context cap で制限される。別の環境変数による上書きはない。
- 大きな ring は SWA pool の最大 page 数と VRAM 見積りを増やす。pool の初期化に失敗すると `init()` は `false` を返し、呼び出し側が初期化失敗を扱う。(`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1023-1028,1471-1472,1516-1519`)

## 実行時の詳細

変数は backend `init()` ごとに評価され、値を保存して以後再読込する仕組みはこの箇所にはない。決定した値は `swa_ring_` として保持され、初期化中の page pool サイズ計算、VRAM 見積り、batch 処理で使われる。プロセス実行中に環境を変更した場合に再評価するコードはない。(`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:555,724-736,1023-1028,1471-1472`)

`swa_span_cap_` は、最終 ring が `win` より大きく、かつ `ctx_cap` より小さい場合に `swa_ring_ - win`、それ以外は 0 となる。batch に含まれるある slot が ring wrap 後の位置に達し、同 slot の batch 内 span がこの上限を超える場合、`batch_token_cap()` が一度の処理 token 数を上限以下にし、`forward_batch()` が順に部分 batch を実行する。TDR/VRAM guard による既存 chunk cap も引き続き適用される。(`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:731-735,1817-1835,1851-1885`)

ring は K/V page の循環位置計算と HIP attention kernel に渡される一方、attention の参照 window は `swa_win` で決まる。よって変数が変えるのは ring の保持容量と、それに伴う batch 分割・資源量であり、attention window 自体ではない。(`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:3463-3469,3978-3979,5393-5394`, `engine/src/inkling2/hip/ink_hip_ops.hip.h:1745-1760`)

## ログと測定値

初期化時に毎回 stderr へ `[ink-hip] SWA KV ring %d positions (window %d, forward_batch span cap %d)` を出す。環境変数の値が無効でもこの設定結果ログは出る。変数専用の警告・エラーはない。大きな値で page pool 確保に失敗した場合は pool 初期化エラーが `err` に渡され、`init()` が失敗する。(`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:735-736,1516-1519`)

`docs/DETAILS.md` にこの変数の記載はないため、性能値や一般的な速度効果は記載しない。Strata の `--ring-check` の説明は、SWA window 後の batch logits と一 token ごとの logits を比較し、ring 上書きでは KL が大きくなり得ることを述べるが、これは検査方法の説明であり、この環境変数の測定結果ではない。(`engine/src/inkling2/ink_main.cpp:369-374,425-440`)

## 根拠

- 読み取り、変換、容量計算、ログ: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:716-736`
- build 条件: `engine/src/inkling2/CMakeLists.txt:237-247`; `engine/src/inkling2/hip/CMakeLists.txt:30-32,74-82,115`
- batch cap と分割: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1817-1885`
- page pool、VRAM 見積り、ring 使用: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1023-1028,1471-1472,1516-1519,3459-3469`
- attention の window と ring index: `engine/src/inkling2/hip/ink_hip_ops.hip.h:1745-1760`
- `docs/DETAILS.md` との照合: この commit の同文書に `STRATA_INK_SWA_RING` の記載なし。
