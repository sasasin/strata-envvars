# `STRATA_PF_FUSED_Q8D`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

MoE prefill の native fused expert 経路で、i-quant 形式の gate/up と `Q8_0` down の組み合わせを fused kernel に含める opt-in。CUDA では `sm_80` 以上、HIP では gfx12 の device で対象になり、対象層の down 計算が MMQ から Strata の fused `Q8_0` down kernel に切り替わる。ほかの層や対応外の形式を有効にするスイッチではない。CUDA は `src/prefill/moe_fused_iq.cu` の `q8d_cuda_requested`、HIP は同ファイルの `q8d_hip_requested` が値を読み、`dev_info` の setup と `native_supported` が適用を決める（同 `:2262-2266`, `:2477-2480`, `:2635-2641`, `:2891-2953`）。

## 値と判定

両 backend とも文字列を数値や真偽値として parse せず、`getenv` が返す文字列の先頭文字が `'1'` かだけを見る。したがって `1`, `10`, `1anything` は on、`0`, `true`, `false`, 空文字、` 1`, 未設定は off。大文字小文字、空白除去、文字列全体の妥当性確認はない（CUDA `:2264-2266`、HIP `:2639-2641`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| 通常の CUDA / HIP build | off | 先頭が `1`（例: `1`, `10`, `1anything`） | 空文字、`0`, `true`, ` 1` など先頭が `1` 以外 |
| `STRATA_PF_OWN_ONLY` 相当の build（fused prefill あり、MMQ なし） | 初期化時に `1` を設定 | 既存値があればその値を維持し、上記の先頭文字判定に従う | 既存値が空文字または先頭が `1` 以外なら off |

own-only の既定値設定は、環境に名前が存在するか（空文字も含む）を先に確認し、未設定の場合にだけ `1` を設定する。Unix では `setenv(..., 0)`、Windows では `_putenv_s` を使う（`src/prefill/prefill.cpp:204-237`, `include/strata/prefill/own_only_switches.hpp:18-24,48-56`）。

## 有効になる条件

- backend と device が合うこと。CUDA では `sm_80+` で native kernel の基礎 setup が成功した後に Q8D setup を試す。sm_80 未満は `dev_info` が先に戻るため対象外で、Turing の `sm_75` opt-in も Q8D setup より前に戻る。HIP では gfx12 の native WMMA kernel が利用可能な device に限る。HIP の gfx11 はこの変数による int8 Q8D 経路の対象外（`src/prefill/moe_fused_iq.cu:2390-2414,2428-2448,2477-2480,2635-2641`）。
- `STRATA_PF_FUSED=0` または `STRATA_PF_FUSED_NATIVE=0`、あるいは prompt path が設定する fused override `0` では `native_supported` が false となり、Q8D も使われない。`STRATA_PF_FUSED` が空または未設定のときは backend/device の既定ルールが加わる。HIP gfx12 で `STRATA_PF_FUSED` 未設定なら既定対象の gate/up 形式だけが通り、`STRATA_PF_FUSED=1` ならほかの対応済み native gate/up 形式にも opt-in が適用される（同 `:2891-2908,2976-3039`）。
- CUDA では `STRATA_PF_FUSED_NT=256` の native wide kernel が setup 済み、または `STRATA_PF_FUSED_WS=1` の warp-specialized kernel が setup 済みの場合、Q8_0-down pair は `native_supported` で除外される（同 `:2950-2953`）。HIP の Q8D gfx12 分岐にはこの CUDA 限定の除外判定はない。
- 実際の組み合わせは CUDA では対応する i-quant gate/up と `Q8_0` down。`Q2_0` gate/up は除外され、K-quant gate/up は `STRATA_PF_FUSED_KQ` 側の条件に従う。HIP gfx12 でも Q8D が扱うのは i-quant gate/up と `Q8_0` down。`Q2_0` gate/up + `Q8_0` down は Q8D だけでは通らず、`STRATA_PF_FUSED_KQ` が有効な場合の別経路となる（同 `:2915-2957,3025-3034`）。
- layer dispatch 側では、native expert layout (`lay.native`)、`stream_all`、`use_mmq || fused_only` が必要で、peer-device 用経路では fused native 層を選ばない。Hadamard-folded 層には追加の trellis pair 条件があり、Q8D だけではその条件を満たさない（`src/prefill/prefill.cpp:5426-5442`）。
- `dev_info` が該当 device 上で基礎 native kernel を利用可能と判定し、Q8_0 down kernel setup に成功する必要がある。setup 失敗時は `d.q8d` が立たず、対象層は fused Q8D 対象にならない（同 `:2390-2414,2477-2480`）。
- `STRATA_PF_FUSED_Q8D` を読む通常の CLI 引数やサーバー設定ファイル経路は見つからなかった。prompt path の fused override は別途 `native_supported` が参照し、`0` なら無効化する（`src/prefill/moe_fused_iq.cu:2905-2908`; override の設定箇所は `src/program/generate.cpp:11712-11725`）。

## 実行時の詳細

CUDA の `q8d_cuda_requested()` と HIP の `q8d_hip_requested()` は関数内 `static const bool` に初回評価結果を保存する。CUDA では `dev_info()` の per-device cache が初めて構築されるとき、base setup が通った場合に限りこの値を参照し、Q8_0 down kernel setup に成功すると `d.q8d=true`、occupancy を `d.occ_kq8` に保存する。HIP では gfx12 の対象判定で static 値を参照する。したがって初回読み取り後の環境変更は反映されない。own-only build は初期化コードで未設定値を `1` にしてから main 前に進む（`src/prefill/moe_fused_iq.cu:2264-2266,2379-2385,2477-2480,2639-2641`; `src/prefill/prefill.cpp:204-237`）。

`prefill.cpp` は各 native layer の `fused::native_supported(gu_type, d_type)` を確認し、dispatch 条件を満たす層なら `fused::experts_native` に渡す。対象の down が `Q8_0` の場合、CUDA は Q8D 用 setup の occupancy を使って `launch<T_Q8_0, false>`、HIP gfx12 は `native_w11_kernel<T_Q8_0, false>` を起動する（`src/prefill/prefill.cpp:5430-5442,5540-5556`; `src/prefill/moe_fused_iq.cu:2950-2953,3125-3129,3220-3239,3320-3339`）。対象外・無効・setup 不成立なら fused Q8D は選ばれず、通常の prefill 経路が MMQ または build の構成に応じた FP16 経路を使う（`src/prefill/prefill.cpp:5572-5584`; own-only build で fused 未対応の layer は FP16 経路となる旨は同 `:373-385`）。変数固有の子プロセスへの転送は確認できなかった。

## ログと測定値

Q8D の値判定や Q8_0 kernel setup 成功・失敗だけを示すログは見つからなかった。fused expert 層に入った際の一般ログ `strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)` は `src/prefill/prefill.cpp:5477-5482` にあるが、Q8D 専用の確認ログではない。起動時に setup が成立しない場合も本変数専用の警告はなく、層の選択条件から外れる。kernel 起動後の共通エラーチェックは `src/prefill/moe_fused_iq.cu:3238-3243,3338-3339`。

`docs/DETAILS.md` にこの変数の記載はなく、測定値は記載しない。

## 根拠

- `src/prefill/moe_fused_iq.cu:2225-2231,2262-2266,2477-2480` — CUDA の値判定、kernel setup、device state。
- `src/prefill/moe_fused_iq.cu:2390-2414,2635-2641,2689-2704` — HIP の device 条件、値判定、Q8_0 down coverage。
- `src/prefill/moe_fused_iq.cu:2891-2957,3025-3039` — global fused gates、format pair と例外条件。
- `src/prefill/moe_fused_iq.cu:3114-3129,3219-3239,3320-3339` — dispatch 後の HIP / CUDA down kernel 起動。
- `src/prefill/prefill.cpp:204-237,373-385,5426-5442,5477-5482,5540-5556,5572-5584` — own-only 既定値、layer eligibility、dispatch と一般ログ、fallback。
- `include/strata/prefill/own_only_switches.hpp:18-24,48-56` — own-only 対象スイッチと未設定値の扱い。
- `include/strata/prefill/pf_fused_override.hpp:1-8,21-24` — process-wide fused override の意味。
