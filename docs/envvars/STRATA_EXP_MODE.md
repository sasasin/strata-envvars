# `STRATA_EXP_MODE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`native_expert_grouped` の grouped native expert 計算で、主に gate/up と down のカーネルレイアウトを選ぶ数値設定。CUDA/HIP 実装では grouped expert の起動ごとに `exp_mode()` の値を使い、SYCL 実装では mode 8 が条件を満たす gate/up の融合経路を選ぶ。通常の CUDA layout（mode 0）に対し、1、2、4、5〜8 などの値は別レイアウトを選択するが、対象 format や処理段階が対応しない場合は通常経路または別の fallback に戻る。生成処理全体や全 expert kernel を一律に切り替える設定ではない。`STRATA_EXPERT_NIBBLE` の変換済み slot に対しては、この値が 0/8 以外だと別の gate/up kernel との競合理由として拒否理由文字列を返す。`engine/src/kernels/cuda/iq_kernels.cu:6763-6803,7270-7316`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7748-7753,7797-7818`、`engine/include/strata/core/expert_nibble.hpp:277-298`。

## 値と判定

CUDA/HIP と SYCL の `exp_mode()` は `std::getenv("STRATA_EXP_MODE")` の結果を `std::atoi` に渡す。文字列全体の妥当性検証や範囲検査はなく、先頭の空白と符号の後から読める10進数字列を変換し、数字が始まらない文字列や空文字は 0 になる。したがって `8tail` は 8、`0anything`・`true`・空文字は 0、`-1` は -1 と判定される。大文字小文字は関係しない。CUDA/HIP の通常実装では 0 以上の値だけが自動選択値を上書きするため、負値は自動選択に戻る。SYCL 実装は負値を自動選択値へ置き換えず、そのまま返す。一方、`STRATA_EXP_MODE` が設定済みかどうかだけを見る箇所では空文字も「設定済み」である。`engine/src/kernels/cuda/iq_kernels.cu:6763-6769,6811`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7602-7606,7748-7752`。

| 条件 | unset | 有効になる値（例） | 無効値・結果（例） |
| --- | --- | --- | --- |
| CUDA/HIP grouped expert | 自動選択。gfx906 HIP は 7、それ以外は device 別規則を評価 | `0`、`2`、`4`、`8`。整数変換後 0 以上なら自動値より優先 | 空文字・`true`・`0anything` は 0。`8tail` は 8。負値は自動選択へ戻る。範囲検査はなく、カーネル側の対応条件に合わなければ fallback |
| SYCL grouped expert | gfx906 条件では 7、それ以外は 0 | 8 は後述の gate/up 融合条件をすべて満たす場合に有効。その他の値は実装された mode 分岐に従う | 空文字・数字なしは 0。負値は負値のまま返り、mode 8 や gfx906 の 5〜8 分岐を選ばない。8 でも条件不足なら融合 gate/up を使わない |

数値に列挙値としての検証はない。CUDA/HIP で例として `3` は mode 1/2/4 の AMD layout 条件にも mode 5 以上の LDS 条件にも当たらず、通常 layout に進む。`5`〜`8` は LDS 分岐の候補で、format 条件を満たさない場合の fallback は gfx906 で 2、それ以外で 0。9 以上も「mode 8 だけ」として拒否されず、`>= 7` / `>= 5` の条件に入り、対応状況に応じて kernel が選ばれる。`engine/src/kernels/cuda/iq_kernels.cu:5890-5897,7270-7309,7355-7409`。
| NVIDIA の起動時既定値 | `sm_86` / `sm_89` / `sm_120` の既定表が適用される条件では、値未設定なら Strata が `8` を設定 | 明示値があればその値を保持 | 空文字を含む設定済み値は自動 `8` の設定を抑止し、カーネル側の `atoi` 結果が使われる |

## 有効になる条件

- 対象は `native_expert_grouped` の grouped native experts 経路。別の expert 実装、CPU 経路、通常の Dense 計算を一括で切り替えるものではない。CUDA/HIP 側の mode 選択と起動は `engine/src/kernels/cuda/iq_kernels.cu:6763-6803,7270-7316,7355-7409`。
- CUDA/HIP では build に `STRATA_EXP_LAYOUTS` が含まれる必要がある。現行ファイルでは `#if 1` で有効。gfx906 HIP は既定 mode 7 / fallback mode 2、その他は既定 mode 0 / fallback mode 0。`engine/src/kernels/cuda/iq_kernels.cu:5883-5899`。
- 自動選択は device に依存する。CUDA の `sm_70` は `STRATA_SM70_TABLE` が設定され、`atoi` が非 0 のとき mode 8。それ以外では mode 0。`sm_60` は `STRATA_SM60_TABLE` が未設定または `atoi` が非 0、`sm_61` は同様に `STRATA_SM61_TABLE` が未設定または非 0 のとき mode 8。`sm_12.1` は `STRATA_SM121_PERF` が未設定または非 0 かつ `strata::qwen_defaults_026()` が false のとき mode 8。Turing (`sm_75`) は `STRATA_SM75_EXP` の規則に従い mode 4 を選ぶ。明示した非負の `STRATA_EXP_MODE` はこれらの自動選択より先に採用される。`engine/src/kernels/cuda/iq_kernels.cu:6771-6803`。
- HIP の gfx1151 自動 mode 8 は `hip_exp8_auto_enabled(dev)` が true の場合に選ばれるが、明示した非負値があればその値が優先される。`engine/src/kernels/cuda/iq_kernels.cu:6755-6769,6774-6778`。
- CUDA/HIP mode 8 の gate/up LDS kernel は対応 format のみで動作し、それ以外は AMD layout の fallback 値または CUDA layout に進む。mode 5 以上でも format が未対応なら同様に fallback する。mode 8 の down kernel にも `n_ff <= 4096` と down type の条件がある。`engine/src/kernels/cuda/iq_kernels.cu:7270-7309,7355-7409`。
- SYCL の mode 8 fused gate/up は `!v1`、`L.had_block == 0`、`n_ff % 32 == 0`、旧 kernel / split multi が無効、`g_kq_split` が有効、`gu_lanes() == 8`、phase が down-only / gate-up-only ではない、かつ `gu_fused_sycl_type_ok(L.gu_type)` が true の場合だけ選ばれる。型一覧は 12、13、（build macro `STRATA_Q6K_EXPERTS` がある場合の 14）、8、23、18、40、21、22、6。満たさない場合は通常の gate/up と後続処理へ進む。`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7740-7745,7797-7818`。
- `STRATA_EXPERT_NIBBLE` の変換 slot を使う構成では、`STRATA_EXP_MODE` が空でなく `atoi` 結果が 0 と 8 のどちらでもないと、`env_conflicts()` は別 layout の gate/up kernel を競合理由として返す。これは拒否理由の判定であり、ここ自体は mode を設定したりログを出したりしない。`engine/include/strata/core/expert_nibble.hpp:277-298`。

## 実行時の詳細

- NVIDIA CUDA build の通常起動では、同一 compute capability のカード構成の場合に `generate.cpp` が `apply_nv_defaults()` を呼ぶ。既定表は `sm_86`、`sm_89`、`sm_120` で mode 8 を含む。`apply_nv_defaults()` は環境変数が存在するかを確認し、未設定の場合だけ `setenv(..., 0)`（Windows は `_putenv_s`）で設定する。従って利用者が空文字を含む値を事前に設定していれば保持される。`engine/src/program/generate.cpp:4437-4449`、`engine/src/core/nv_defaults.cpp:37-42,67-73,75-103,104-118,222-238`。
- 自動 `8` は `nv_default_env()` がそのカード用の表を返す場合に限る。`sm_86` は `STRATA_SM86_PERF` の先頭文字が `0` なら表を返さない。`sm_89` と `sm_120` はそれぞれ `STRATA_SM89_PERF` / `STRATA_SM120_PERF` の先頭文字が `0` の場合、または `defaults026` が true の場合に表を返さない。明示 `STRATA_EXP_MODE` が存在すると `apply_nv_defaults()` はその項目を飛ばす。`engine/src/core/nv_defaults.cpp:15-18,41-43,75-83,104-107,222-238`。
- CUDA/HIP と SYCL の mode は `exp_mode()` 内の関数ローカル `static const int` に初回呼び出し時にキャッシュされる。プロセス内で後から環境を書き換えてもこの parse 結果は更新されない。CUDA/HIP は mode キャッシュに加えて device ごとの自動選択を `per_dev[64]` に保存する。bench API の `native_expert_set_mode()` が非負 mode を設定した場合は、環境 parse 値よりもその値を優先する。`engine/src/kernels/cuda/iq_kernels.cu:6763-6803,6822-6829`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7602-7606,7748-7758`。
- mode は gate/up と down で同じ使われ方をするとは限らない。CUDA/HIP の gate/up は mode 5〜8 を LDS 経路候補にし、format が対象外なら gfx906 では mode 2、それ以外では mode 0 に fallback する。down も mode 5 以上を gfx906 では mode 2、それ以外では mode 0 に丸めるが、gfx906 では mode 7/8 用 LDS down 経路が特定 type にあり、他の条件では AMD layout または CUDA layout を選ぶ。`engine/src/kernels/cuda/iq_kernels.cu:5890-5897,7270-7309,7355-7409`。
- Turing の自動 mode 4 は、down 経路で `cap_groups > 30` かつ mode が明示されていない場合に mode 0 へ戻る。`STRATA_EXP_MODE` が空文字でも `getenv` は非 null となるため、この fallback は抑止される。`engine/src/kernels/cuda/iq_kernels.cu:6807-6819`。
- `engine/src/kernels/expdec_bench.cpp` はこの変数を kernel choice を bypass する診断条件として読み、値が空でなく先頭文字が `0` でなければ警告を出す。通常の生成経路の mode 判定とは別の bench 専用警告。`engine/src/kernels/expdec_bench.cpp:443-447`。

## ログと測定値

- NVIDIA 既定表が未設定項目を一つ以上設定した場合、stderr に `strata: <GPU>: <N> [exact ]speed switches on by default (...)` の行が出て、設定した変数名一覧に `STRATA_EXP_MODE` が含まれる。ユーザー指定値が保持されただけの場合は `set` に追加されない。`engine/src/core/nv_defaults.cpp:222-255`。
- 通常の mode 選択自体について、ここで確認した実装には mode を表示するログはない。`expdec_bench` は条件に該当すると `# warning: STRATA_EXP_MODE is set, the kernel choice is bypassed` を stdout に出す。`engine/src/kernels/expdec_bench.cpp:443-446`。
- `native_grouped_parity` は gfx1151 で環境変数が未設定なら両比較実行を mode 0 に固定し、stdout に `gfx1151: STRATA_EXP_MODE=0 pinned for both runs (mode 8 and the CUDA layout differ in summation order)` を出す。これは parity 実行ファイルの挙動で、通常 engine 起動の既定値ではない。`engine/src/kernels/native_grouped_parity.cpp:380-395`。

## 根拠

- `engine/src/kernels/cuda/iq_kernels.cu:5883-5899,6750-6803,6807-6819,7270-7316,7355-7409`
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7602-7606,7740-7818,7884-7982`
- `engine/src/core/nv_defaults.cpp:15-18,37-43,67-73,75-103,104-118,222-255`
- `engine/src/program/generate.cpp:4437-4449`
- `engine/include/strata/core/expert_nibble.hpp:277-298`
- `engine/src/kernels/expdec_bench.cpp:443-447`
- `engine/src/kernels/native_grouped_parity.cpp:380-395`
