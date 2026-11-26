# `STRATA_GR_Q8_PFS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Q8_0 の fused hyper-connection read において、down projection の活性値 staging を複数 token 分まとめてロードする `gr_down_q8_fast_kernel<T, 4, true>` を選ぶ。無効時は同じ kernel の `PFS=false` 版となり、token ごとに staging を計算して shared memory に書く。PFS 版もソースコメント上は同じ値・同じ演算順であり、変えるのはロードの発行順である（`engine/src/kernels/cuda/fused_gr.cu:2545-2547,2577-2581,2582-2608,2610-2628`）。

この設定は `fused_gr_read_multi` が Q8 down/up weight を持つ入力を `launch_q8` に渡し、さらに `launch_q8_t` の Q8_0 通常経路まで到達したときだけ参照される（`engine/src/kernels/cuda/fused_gr.cu:4285-4293,4055-4068,3991-4012`）。CLI 引数からこの値を上書きする処理は確認できない。Strata の既定値注入と環境変数の明示設定が優先関係にある。

## 値と判定

`launch_q8_t<T>` 内の関数ローカル `static` 初期化で `std::getenv` を呼び、設定値があれば `std::atoi`、未設定なら `-1` にする。文字列全体の検証、エラー報告、clamp はない。`pfs_env >= 0` のときは 0 以外を有効、0 を無効とし、負値または未設定は実行環境ごとの既定判定に委ねる（`engine/src/kernels/cuda/fused_gr.cu:3994,4009-4012`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| すべての build / backend（通常経路が選ばれた場合） | `pfs_env=-1` として下記の既定判定 | `1`、`2`、`1tail` は `atoi` 結果が正なので有効 | 空文字、`0`、`0anything`、`true`、`-1` はそれぞれ `0` または負値になり、0 は無効、負値は既定判定へ戻る |
| CUDA の既定判定 | `hc_q8_sm80_fast()` の結果 | CUDA device の compute capability major が 8 以上なら既定で有効 | SM80 未満、または capability 問い合わせに失敗した場合は既定で無効 |
| HIP の既定判定 | `hc_q8_sm80_fast()` は常に false | 既定では有効値なし。明示値が非負ならその値で判定 | 未設定または負値なら無効 |

`atoi` は整数の先頭部分を読むため、たとえば `1tail` は 1、数字で始まらない `true` や空文字は 0 になる。先頭空白や符号を受け付け、後続文字列の妥当性は確認しない。整数として表せない入力についてコード上の安全な範囲検査はない。負数は「負なら fallback」という条件のため `-1` と同様にアーキテクチャ既定判定へ戻る（`engine/src/kernels/cuda/fused_gr.cu:3994,4010`）。

Strata は起動時の `apply_arch_defaults` で、対象名が未設定の場合にだけ `"1"` をプロセス環境へ追加する。既に設定済みなら空文字や `"0"` も保持される（`engine/src/core/arch_defaults.cpp:302-310,218-224`）。注入条件は次のとおり。

| AMD GPU の条件 | 既定値 `1` の注入条件 | 注入を止める条件 |
|---|---|---|
| gfx1200 / gfx1201 | `STRATA_DEFAULTS=026` ではなく、`STRATA_GFX12_DEFAULTS` が `0` で始まらない | `STRATA_DEFAULTS=026`、または `STRATA_GFX12_DEFAULTS` の先頭が `0` |
| gfx1151 on Windows | `STRATA_DEFAULTS=026` ではなく、`STRATA_GFX1151_DEFAULTS` が `0` で始まらない | `STRATA_DEFAULTS=026`、または `STRATA_GFX1151_DEFAULTS` の先頭が `0` |
| discrete RDNA3 gfx1100 / gfx1101 / gfx1102 | 全 GPU が integrated ではない扱いで、`STRATA_DEFAULTS=026` ではなく、`STRATA_GFX11_DEFAULTS` が `0` で始まらない | `STRATA_DEFAULTS=026`、または `STRATA_GFX11_DEFAULTS` の先頭が `0` |
| その他の AMD GPU / gfx1151 on non-Windows | このアーキテクチャ表からは注入しない | 該当なし |

既定表における `STRATA_DEFAULTS=026` は完全一致（`026`、`0.2.6`、`v0.2.6`）で判定され、結果は `qwen_defaults_026()` が初回に cache する。上表の `STRATA_GFX*_DEFAULTS` は値全体でなく先頭文字が `0` かを判定する（`engine/include/strata/core/defaults_026.hpp:21-29`, `engine/src/core/arch_defaults.cpp:41-66`, `engine/include/strata/core/gfx11_extra.hpp:27-30,41-46`）。アーキテクチャ表が `"1"` を注入しても、その後の kernel 側ではユーザー値と同じ `atoi` 判定を受ける。

## 有効になる条件

- 入力に `q8_down` と `q8_up` があり、fused read が Q8 経路を選ぶこと。Q8 weight がない入力ではこの変数を読む `launch_q8_t` へ進まない（`engine/src/kernels/cuda/fused_gr.cu:4285-4293`）。
- PFS 分岐の前にある CUDA Tensor Core 経路が選ばれないこと。SM80+ CUDA では `STRATA_HC_Q8_TC` の経路が先に試され、続いて `STRATA_HC_Q8_BF16TC` 経路が試される。両経路が shape 条件を満たして起動すると、その `return` により `STRATA_GR_Q8_PFS` の判定箇所まで来ない。HIP ではこれらの mode helper が 0 を返す（`engine/src/kernels/cuda/fused_gr.cu:3904-3943,3945-3957,3960-3989`）。
- down projection で `STRATA_TSUM` が有効であること。`ts && pfs` の場合だけ PFS テンプレート版を起動する。`STRATA_TSUM` が 0 相当なら、`STRATA_GR_Q8_PFS=1` でも通常の `gr_down_q8_fast_kernel<T, 4>` または標準 down kernel が選ばれ、PFS は使われない（`engine/src/kernels/cuda/fused_gr.cu:4009-4022`）。
- `STRATA_TSUM` 未設定時の既定は CUDA SM80+ で有効、HIP では無効。AMD の上表の既定セットには `STRATA_TSUM=1` も含まれる（gfx12: `engine/src/core/arch_defaults.cpp:52-61`、gfx1151: `engine/src/core/arch_defaults.cpp:67-89`、Windows gfx1151: `engine/src/core/arch_defaults.cpp:95-105`、discrete RDNA3: `engine/include/strata/core/gfx11_extra.hpp:46-72`）。明示的に `STRATA_TSUM=0` を設定すれば既定セットでも無効となる。
- モデル形式、serve/server モード、CLI による PFS 固有の分岐は確認できない。観測上の適用条件は kernel 呼び出し時に渡される Q8 weight と上記 backend / switch 条件である。

## 実行時の詳細

engine 起動時に `generate.cpp` が GPU architecture を問い合わせ、`apply_arch_defaults` を呼ぶ。その関数は各既定値を未設定時だけ環境へ入れ、設定済みの値を優先する（`engine/src/program/generate.cpp:4290-4320`, `engine/src/core/arch_defaults.cpp:302-310`）。gfx12 では `arch_default_env` が、Windows gfx1151 では同じ表の Windows 分岐が、discrete RDNA3 では `gfx11_discrete_exact_env` が PFS 既定値を返す（`engine/src/core/arch_defaults.cpp:28-62,64-105`, `engine/include/strata/core/gfx11_extra.hpp:41-73`）。

`STRATA_GR_Q8_PFS` 自体はプロセス起動直後ではなく `launch_q8_t<T>` の初回呼び出し時に読み取られ、その template specialization 内で cache される。T=1..8 は別々の specialization なので、それぞれ初回に値を読む。該当 specialization の初回以降に環境を変更しても、その cache の値は更新されない。設定を値として見るだけでなく、`pfs` が真なら PFS 版 kernel、偽なら非 PFS 版 kernel を dispatch する（`engine/src/kernels/cuda/fused_gr.cu:3991-4012,4055-4068`）。

PFS 版は thread ごとに T 個の token の `R`、`w_norm`、必要な `bo_prev` を先にロードし、その後 token 順に同じ fma・二乗和・shared memory store を実行する。非 PFS 版は token ごとにロードから store までを行う（`engine/src/kernels/cuda/fused_gr.cu:2577-2628`）。PFS のための個別ログや timeout はない。Q8 kernel の launch error は `fused_gr_read_multi q8: %s` を stderr に出して `exit(1)` する（`engine/src/kernels/cuda/fused_gr.cu:4286-4293`）。

## ログと測定値

PFS の値そのものを報告するログはない。アーキテクチャ既定値が何か一つ以上追加されたとき、gfx12 / gfx1151 では `strata: gfx12 (RDNA4): %zu exact speed switches on by default ...` または `strata: gfx1151 (Strix Halo): %zu exact speed switches on by default ...` の集約行に、追加された名前の一覧として表示される（`engine/src/core/arch_defaults.cpp:397-404`）。discrete RDNA3 では `strata: gfx11 (RDNA3): ...` 行の名前一覧に含まれる（`engine/src/core/arch_defaults.cpp:318-332`）。その既定グループで何も追加されない場合、該当行は出ない。

kernel コメントは PFS 版と非 PFS 版が同じ値・演算順であると説明するが、対象 commit の文書に PFS 単独の比較条件付き測定値は見つからなかったため、性能値は記載しない（`engine/src/kernels/cuda/fused_gr.cu:2577-2581`）。

## 根拠

- `engine/src/kernels/cuda/fused_gr.cu:2545-2547,2577-2628` — PFS テンプレート分岐、読み込み順、演算。
- `engine/src/kernels/cuda/fused_gr.cu:3904-3957,3960-4012` — CUDA/HIP 既定、先行経路、値の parse と dispatch。
- `engine/src/kernels/cuda/fused_gr.cu:4055-4068,4285-4293` — Q8 経路の呼び出し、launch error。
- `engine/src/core/arch_defaults.cpp:16-66,67-105,302-310,318-332,360-404` — AMD architecture defaults、注入・集約ログ。
- `engine/include/strata/core/gfx11_extra.hpp:27-30,41-73` — discrete RDNA3 の既定値条件。
- `engine/include/strata/core/defaults_026.hpp:21-29` — `STRATA_DEFAULTS=026` の値判定と cache。
- `engine/src/program/generate.cpp:4290-4320` — GPU 状態確認と起動時の既定値適用。

