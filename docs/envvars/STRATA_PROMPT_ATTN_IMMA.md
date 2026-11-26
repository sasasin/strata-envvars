# `STRATA_PROMPT_ATTN_IMMA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の QSA prompt attention で、int8 K/V を使うときに v3 の INT8 tensor-core kernel `prompt_attn_i8v3_kernel` を選ぶかを制御する。v3 を選ぶと K と V の積を INT8 tensor core で計算する。環境変数が無効なら同じ分岐から従来の `launch_i8`（v2）を選ぶ。値は prompt attention の kernel 選択に使われ、decode attention を切り替えるものではない。実装は `engine/src/kernels/cuda/qsa_prompt_attn.cu` の `qsa_prompt_attn_batch` にある（同ファイル 1154-1200, 1401-1431, 2471-2477, 2558-2568）。

## 値と判定

`std::getenv` の戻り値を一度読み、未設定なら内部値 `2`（既定動作）、設定されていれば先頭文字だけを調べる。先頭が `'1'` なら強制 ON、その他はすべて強制 OFF。数値変換や文字列全体の比較はしない（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2563-2568`）。

| 条件（build / 経路） | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA の QSA prompt attention、INT8 K/V 経路 | 内部値 `2`。Ampere（CC 8.0）以降で v3 を選ぶ | 先頭が `1` の文字列。例: `1`, `10`, `1anything` | 空文字、`0`, `2`, `true`, ` 1` など先頭が `1` でない文字列 |

空文字は「設定済み」だが空文字の先頭 `v[0]` は `'1'` ではないため OFF になる。大文字小文字、空白、残りの文字列、数値としての妥当性を検査しない。負値も先頭が `1` でないため OFF（同 `qsa_prompt_attn.cu:2564-2565`）。

## 有効になる条件

- CUDA の `qsa_prompt_attn_batch` が呼ばれること。HIP ビルドでは先に WMMA 経路を試し、使えなければ `false` を返すため、この環境変数の判定箇所へ進まない。Metal もこの CUDA kernel 選択経路ではない（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2471-2481, 2509-2518`）。
- 現在の device が Turing（CC 7.5）ではなく、CC 8.0 以上であること。device 能力は device ごとにキャッシュされ、Turing は v1 経路へ分岐する。これより古い GPU や不適合条件では prompt tensor-core 関数が `false` を返し、呼び出し側が別経路へ進む（同 `qsa_prompt_attn.cu:2474-2507, 2567-2568`）。
- QSA prompt attention の K が int8（`pools.k_q != nullptr`）で、V が int8、両方の scale があり、Q4 K/V 経路や K8V4 hybrid 経路ではないこと。形状・selection data・page table などの検査に失敗すれば同関数は `false` を返す（同 `qsa_prompt_attn.cu:2519-2543`）。
- 呼び出し側が `STRATA_PROMPT_ATTN_OLD` によって旧 attention 経路を強制していないこと。この別変数は値の内容ではなく設定有無で判定され、設定されると `qsa_prompt_attn_batch` を呼ばない。通常の prefill 呼び出し箇所は `engine/src/prefill/prefill.cpp:5537-5557` と `9462-9468`。
- unset の既定 ON は `strata::prompt_attn_imma_default(false, 80, strata::qwen_defaults_026())` が真の場合に限る。同 helper は CUDA、CC 8.0 以上、`v026` 既定値でないことを条件とする。`STRATA_DEFAULTS` が `026` / `0.2.6` / `v0.2.6` なら `v026` となり、unset 時は OFF。明示して先頭 `1` を設定した場合はこの default 判定を迂回するため、`STRATA_DEFAULTS=026` より本変数の明示値が優先する。`STRATA_DEFAULTS` は helper 内で一度 cache される（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2567`; `engine/include/strata/core/sm120_series.hpp:146-149`; `engine/include/strata/core/defaults_026.hpp:21-29`）。
- `STRATA_PROMPT_ATTN_OLD` やテスト用 `qsa_prompt_attn_set_imma` 以外に、CLI 引数による同値の上書きはこの読み取り経路にはない。テスト用 setter は `g_pa_imma` を直接変更する（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2432`）。

## 実行時の詳細

`qsa_prompt_attn_batch` は QSA attention のバッチ単位で呼ばれ、形状・device・KV pool の検査後、INT8 K/V 分岐に到達した時点で環境変数を読む。結果はプロセス内の `g_pa_imma` に保存され、以後は再読み込みしない。したがって起動後に環境を書き換えても通常は反映されず、最初の該当呼び出しより前に設定する必要がある。`qsa_prompt_attn_set_imma` が sentinel `-1` を設定した場合は再読込可能だが、これはテスト用 API である（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2376, 2432, 2563-2567`）。

値が強制 ON、または unset かつ default 条件を満たす場合、`launch_i8v3` は kernel ごとに dynamic shared-memory 属性を設定してから `prompt_attn_i8v3_kernel` を投入する。それ以外は `launch_i8` の v2 kernel を投入する（同 `qsa_prompt_attn.cu:1401-1431, 2567-2568`）。v3 kernel の投入が false を返す場合、prompt 関数も false となり、prefill 側では利用可能な別の QSA attention 経路または decode attention のループへフォールバックする（`engine/src/prefill/prefill.cpp:5556-5569, 9466-9472`）。

## ログと測定値

環境変数の読み取りや ON/OFF 自体を示すログは見つからない。v3 の shared-memory 属性設定に失敗した場合は `launch_i8v3` が CUDA エラーを消去して `false` を返し、上位の fallback に進む。kernel launch error の場合は stderr に `qsa_prompt_attn_batch (v3): <CUDA error text>` を出して `exit(1)` する（`engine/src/kernels/cuda/qsa_prompt_attn.cu:1408-1429`）。

`docs/DETAILS.md:1302` は Ampere 以降での既定 ON と `=0` による旧 kernel 選択を要約している。実装上は `=0` 固定ではなく、先頭文字が `1` でない設定値が OFF となる。また `docs/SETTINGS.md:270` は適用先を NVIDIA and AMD としているが、この変数を読むのは CUDA kernel 経路であり、HIP は別の WMMA 分岐から戻る。性能値はこの文書では記載しない。

## 根拠

- `engine/src/kernels/cuda/qsa_prompt_attn.cu:2376, 2432, 2471-2481, 2509-2518, 2519-2568` — 状態、test setter、backend/device/KV 条件、値判定と kernel 選択。
- `engine/src/kernels/cuda/qsa_prompt_attn.cu:1154-1200, 1401-1431` — v3 kernel と launch、失敗時の扱い。
- `engine/include/strata/core/sm120_series.hpp:146-149`, `engine/include/strata/core/defaults_026.hpp:21-29` — unset 時の default 条件と `STRATA_DEFAULTS` との関係。
- `engine/src/prefill/prefill.cpp:5537-5569, 9462-9472` — 呼び出し元、旧経路指定、失敗時の fallback。
- `docs/DETAILS.md:1302`, `docs/SETTINGS.md:270` — ソース実装との照合対象となる要約。
