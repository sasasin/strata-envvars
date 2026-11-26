# `STRATA_ATTN_PERCELL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL の QSA prompt attention で、選択済みセルの attention score を計算するカーネルを選ぶ。既定（未設定）は `qsa_prompt_attn_percell` で、`STRATA_ATTN_PERCELL` の値が文字 `'0'` から始まる場合は `qsa_decode_attn_batch` を使う。前者はセルごとに work-item を割り当てる 128-cell chunk の経路、後者は warp kernel であり、コードコメントは前者が FP32 で warp kernel と bitwise 一致しないと説明している。これは選択セルや Q/K/V の選択条件を変える設定ではなく、選択済みセルの attention 計算方法を切り替える。実装は SYCL prefill の QSA 分岐にある。(`engine/sycl/src/prefill/prefill.cpp:3560-3569,3873-3901`, `engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1416-1437`)

## 値と判定

`std::getenv` の戻り値を一度だけ `static const bool` に保存し、未設定なら `true`、設定済みなら先頭文字が `'0'` 以外のとき `true` とする。文字列全体の parse や数値変換はしない。空文字は設定済みだが先頭文字が `'0'` ではないため per-cell が有効。(`engine/sycl/src/prefill/prefill.cpp:3884-3895`)

| 条件（build / 経路） | unset | per-cell になる値の例 | warp kernel になる値の例 |
|---|---|---|---|
| SYCL の QSA batched prompt fallback が実行され、この分岐まで到達 | 有効 | `1`, `true`, `false`, 空文字, ` 0`, `-1` | `0`, `00`, `0anything`, `0.5` |

大文字小文字、空白、数値としての妥当性は検査しない。`0` で始まるかだけを比較するため、`false` は無効値として扱われず per-cell を選び、`0anything` は後続文字を無視して warp kernel を選ぶ。境界値や負値に対する数値範囲の判定はない。(`engine/sycl/src/prefill/prefill.cpp:3886-3895`)

## 有効になる条件

- `engine/CMakeLists.txt` の `STRATA_ENABLE_SYCL=ON` で選ぶ独立した実験的 SYCL backend の実行ファイルに限る。このファイルの分岐は `engine/sycl/src/prefill/prefill.cpp` にあり、CUDA、HIP、CPU、Metal のコードからこの変数を読む箇所は見つからなかった。(`engine/CMakeLists.txt:23-32`, `engine/sycl/CMakeLists.txt:303-311`)
- prompt の layer が `core::is_qsa_layer` に該当し、QSA の query/key/value・indexer 計算を通って attention の処理へ進む必要がある。GDN layer や decode attention、draft layer の `qsa_decode_attn_batch` 呼び出しでは、この環境変数は参照されない。(`engine/sycl/src/prefill/prefill.cpp:3512,3560-3575,3873-3895`, `engine/sycl/src/core/mtp.cpp:1060`)
- `STRATA_PROMPT_ATTN_OLD` が未設定で、`qsa_prompt_attn_batch` が成功すると、その関数内の batch kernel が使われ、この環境変数を読む fallback 分岐には入らない。設定有無だけを調べる `STRATA_PROMPT_ATTN_OLD` は空文字でも batch kernel を飛ばす。SYCL の batch 関数は ESIMD または XMX の実装が入力を扱えたとき成功し、それ以外は `false` を返す。(`engine/sycl/src/prefill/prefill.cpp:3853,3873-3875`, `engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1973-2017`)
- fallback の各 query batch で、ビルド macro `STRATA_SYCL_TLA_ATTN` が定義され、`STRATA_SYCL_TLA_ATTN` 環境変数が先頭 `'1'` で、かつ `nb == 32`、`m.cap == 2051`、TLA batch 呼び出しが成功する場合は `continue` で先へ進むため、この変数の判定を通らない。macro を有効にする CMake 設定は AOT `bmg-g31` を要求する。(`engine/sycl/src/prefill/prefill.cpp:3877-3886`, `engine/sycl/CMakeLists.txt:313-320`)
- ESIMD/XMX の batch attention が fallback を止める場合、それらの適用条件にも依存する。ESIMD は既定で試され、Battlemage の int8 K/V 等の対応条件を満たせば成功し、`STRATA_PROMPT_ATTN_ESIMD=0` で無効化できる。XMX は既定で無効で、`STRATA_PROMPT_ATTN_XMX` が非ゼロなら試される。いずれかが処理を引き受ければ `STRATA_ATTN_PERCELL` は読まれない。(`engine/sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:406-438`, `engine/sycl/src/kernels/cuda/qsa_prompt_attn_xmx.dp.cpp:369-388`)

## 実行時の詳細

QSA prompt はまず `qsa_prompt_attn_batch` を試し、旧 attention の指定または batch 関数の失敗時に `m.attn_batch` ごとの fallback loop に入る。該当 query batch で任意の TLA 経路が使われなければ、関数内 static の `percell` が初回評価され、真なら `qsa_prompt_attn_percell` を呼んで `continue`、偽なら `qsa_decode_attn_batch` を呼ぶ。したがって環境はプロセス起動時に必ず読むのではなく、この fallback 分岐が初めて実行される時点で読み取り、その値をプロセス内で cache する。初回評価後にプロセス環境を変更しても、この分岐の選択には反映されない。(`engine/sycl/src/prefill/prefill.cpp:3873-3895`)

per-cell 関数は K/V pool の形式から内部 mode を選び、128-cell chunk の score/attention 計算と merge kernel を queue に投入する。warp 側は `qsa_decode_attn_batch` に同じ query、選択 ID、step、pool、scratch、出力領域を渡す。どちらの出力も、その後の `fwht256_inplace_cuda`（KV state が rotated または hybrid のとき）、`gate_attn`、attention output projection に進む。(`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1419-1437`, `engine/sycl/src/prefill/prefill.cpp:3887-3901`)

## ログと測定値

この変数の読み取りや選択だけを知らせるログはない。コードコメントが per-cell と warp kernel の浮動小数点演算順序は bitwise 一致しないと述べるが、`STRATA_ATTN_PERCELL` に関する測定値や生成 token への影響は `docs/DETAILS.md` に見つからなかったため、性能・出力同一性は記載しない。(`engine/sycl/src/prefill/prefill.cpp:3884-3886`)

warp 経路の `qsa_decode_attn_batch` は、対応外 geometry または必要 buffer の欠落を検出すると stderr に `qsa_decode_attn_batch: unsupported geometry or missing buffers` を出し、`exit(1)` する。これは環境変数の値自体の検証ではなく、呼び出された kernel の入力検査である。per-cell 経路ではこの検査を通らない。(`engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1001-1008`)

## 根拠

- `engine/sycl/src/prefill/prefill.cpp:3512,3560-3575` — prompt の QSA/GDN 分岐と QSA 入力計算。
- `engine/sycl/src/prefill/prefill.cpp:3853,3873-3901` — 旧 attention 条件、batch/TLA fallback、対象環境変数の読み取りと出力後の処理。
- `engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1416-1437` — per-cell 関数の適用範囲、pool mode、chunk と merge。
- `engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1001-1008` — warp kernel の入力検査と終了経路。
- `engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1973-2017` — batch kernel が ESIMD/XMX を試し、未対応時 fallback を返す箇所。
- `engine/sycl/src/kernels/cuda/qsa_prompt_attn_esimd.dp.cpp:406-438`, `engine/sycl/src/kernels/cuda/qsa_prompt_attn_xmx.dp.cpp:369-388` — batch 経路の選択条件。
- `engine/CMakeLists.txt:23-32`, `engine/sycl/CMakeLists.txt:303-320` — SYCL backend と任意 TLA kernel の build 条件。
- `docs/DETAILS.md:1290-1319` — attention 関連設定の説明を照合。`STRATA_ATTN_PERCELL` の説明・測定値は掲載されていない。
