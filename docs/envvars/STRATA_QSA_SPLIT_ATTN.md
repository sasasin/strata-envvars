# `STRATA_QSA_SPLIT_ATTN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA の decode attention を、対応する CUDA GPU で int8 tensor-core の split attention に切り替える opt-in スイッチ。通常の `qsa_decode_attn_batch` に代えて、選択された KV cell を複数 block で処理し、partial を log-sum-exp merge する。通常経路と bitwise 一致する保証はなく、Strata の資料は差を rounding level としている。Verifier の通常 window 経路と MTP drafter の attention で参照される。実装は `engine/src/core/verify.cpp`、`engine/src/core/mtp.cpp`、split kernel の選択条件は `engine/src/kernels/cuda/qsa_prompt_attn.cu` にある（`verify.cpp:2575-2590`、`mtp.cpp:1342-1349,2481-2499`、`qsa_prompt_attn.cu:2379-2430`）。

この変数は prompt attention の切替ではない。prefill は `qsa_decode_attn_batch` を使うが、この候補名を読む箇所はなく、split 関数を呼ぶのは verifier と drafter の上記経路である（`engine/src/prefill/prefill.cpp:5567,9470`、`engine/src/core/verify.cpp:2582`、`engine/src/core/mtp.cpp:1348,2493`）。

## 値と判定

各読み取り箇所で `std::getenv` の戻り値を `std::atoi` に渡し、結果が 0 以外なら有効とする。文字列全体の妥当性検査、真偽文字列比較、範囲制限、無効値の警告はない。未設定は無効、空文字も `atoi("") == 0` で無効。`1`、`2`、`-1`、`1tail`、` 1` は有効、`0`、`0tail`、`true`、`false`、空白だけの文字列は無効となる。数字の後ろは検査されない（`verify.cpp:2581`、`mtp.cpp:1347,2485-2488`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| Verifier の通常 window attention | `false` | `1`, `-1`, `1tail` | 空文字, `0`, `true` |
| MTP の単一 row attention | `false` | `1`, `-1`, `1tail` | 空文字, `0`, `true` |
| MTP の複数 slot attention | `false` | `1`, `-1`, `1tail` | 空文字, `0`, `true` |

## 有効になる条件

- split kernel が実際に起動するのは CUDA build のみ。関数は HIP build (`__HIPCC__`) では直ちに `false` を返す（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2383-2388`）。
- CUDA では、QSA geometry が要求する head dimension、head 数、KV head 数、selection capacity、page table、int8 KV と scale buffer が揃い、Q4 KV ではない必要がある。device の compute capability が 8.0 以上（sm_80+）であることも必要（`qsa_prompt_attn.cu:2389-2404`）。
- scratch が split 数分の partial を保持できることが必要。不足時は `false` を返す。split 数は GPU SM 数・query 数・KV head 数・capacity から計算され、1〜20 block の範囲（capacity の chunk 数以下）になる（`qsa_prompt_attn.cu:2414-2419`）。
- Verifier では `record_window` の通常 attention 分岐に限られる。slot/run 別や batch-row 等、先行する特殊分岐を通るとこの読み取り位置に到達しない（`verify.cpp:2430-2564,2575-2590`）。
- MTP の単一 row 経路は `record_rest`、複数 slot 経路は `record_rest_slots` で読む。後者では値が有効だと `qsa_decode_attn_slots` の fused 経路を抑止し、row ごとの loop に入る。その後 split 関数が非対応として `false` を返せば、各 row は `qsa_decode_attn_batch` に戻る。このため HIP でも複数 slot 時に fused slot 呼び出しを迂回する効果はあり得るが、HIP で split kernel 自体が動くことはない（`mtp.cpp:2485-2499`、`qsa_prompt_attn.cu:2386-2388`）。
- 他の環境変数、CLI option、設定ファイルによる値の上書きは、これらの読み取り経路にはない。

## 実行時の詳細

Verifier、MTP 単一 row、MTP 複数 slot のそれぞれで関数内 `static const bool` として初回評価時に値を cache する。Verifier は `record_window` が通常 attention 分岐へ初めて到達したとき、MTP はそれぞれ `record_rest` / `record_rest_slots` が最初に実行されたときに読み取る。起動時一律の読み取りではなく、初回評価後にプロセス環境を変更しても、その関数の判定には反映されない（`verify.cpp:2581`、`mtp.cpp:1347,2485-2488`）。

Verifier は split が有効で、split 関数が `true` を返した場合にその出力を使う。無効または関数が対応条件を満たさない場合は `qsa_decode_attn_batch` を呼び、標準 attention を実行する（`verify.cpp:2582-2590`）。MTP の単一 row でも同様に失敗時は標準 batch kernel に戻る。MTP 複数 slot 経路は前節のとおり、split が有効なとき fused slot kernel を先に避け、各 row で split を試して失敗時に標準 kernel を使う（`mtp.cpp:1346-1349,2489-2499`）。

split kernel は query ごと・KV head ごと・split ごとの kernel と merge kernel を同じ stream に launch する。CUDA device 属性取得失敗、sm_80 未満、geometry / KV 条件不一致、scratch 不足、共有 memory 属性設定失敗は通常 kernel への fallback になる。launch 後の CUDA error は stderr に出力し `exit(1)` する（`qsa_prompt_attn.cu:2389-2429`）。

## ログと測定値

Verifier で split が実行されず通常 batch kernel に戻ると、`strata::dispatch::notef` に `qsa layer: decode attention batch kernels (split tensor-core attention off or declined) kv_rot=%ld` を渡す（`verify.cpp:2587-2589`）。MTP fallback に対応する専用ログはない。split kernel の CUDA launch error は `qsa_decode_attn_split: %s` を stderr に出して終了する（`qsa_prompt_attn.cu:2424-2427`）。

`docs/DETAILS.md:1288-1301` は sm_80+・int8 KV の decode split を rounding-level と記載する。同資料の測定表は 0.1.45、RTX 3060 / RTX A4000、IQ3_XXS、30K prompt 後の decode、5 pairs という条件で、この変数を含む CUDA opt-in 群をまとめ、split attention はそれぞれ +2.8% / +3.5%、KL 0.0016（floor 0.0012）と記録する（`docs/DETAILS.md:1710`）。これは資料に記された測定であり、他の構成への一般化はできない。

## 根拠

- 読み取りと fallback: `engine/src/core/verify.cpp:2575-2590`, `engine/src/core/mtp.cpp:1342-1349,2481-2499`
- split 対応条件、分割数、kernel launch と失敗処理: `engine/src/kernels/cuda/qsa_prompt_attn.cu:2379-2430`
- 関数の用途と CUDA 条件の概要: `engine/include/strata/kernels/qsa_prompt_attn.hpp:45-51`
- backend による実装ファイルの区分: `engine/cmake/strata_gpu_engine.cmake:90-92`, `engine/cmake/hip_backend.cmake:105-109`
- Strata の説明と測定値: `docs/DETAILS.md:1288-1301,1710`
