# `STRATA_GR_R2`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

ストリーム分割ハイパーコネクション読み（v3 read, `STRATA_GR_V3`）の down projection で、5〜8 token の launch を exact-T kernel に切り替え、1 warp が受け持つ down 行数（1 / 2 / 4）を選ぶ。up projection では 7・8 token のとき exact-T kernel を使うかどうかだけを決める。行数を増やすとブロック数が減り、同じ活性化の staging を複数行で共有する（`engine/src/kernels/cuda/fused_gr.cu:1609-1614`）。

変えないもの: v3 read 自体の on/off（`STRATA_GR_V3`）、1〜4 token の launch、Q8 / RDNA / persist の各読み経路。出力は「同じ dot を同じ順で計算するので同じビット」とコメントにある（同 1610）。

実装は `gr_r2()`（`fused_gr.cu:1611-1614`）1 箇所で、消費は down の分岐 `fused_gr.cu:4367-4377` と up の分岐 `fused_gr.cu:4387-4388`。

## 値と判定

読み取りは `std::getenv` 1 箇所のみ（`fused_gr.cu:1612`）。環境変数名を動的に渡す helper や転送処理はない。未設定なら 2、設定時は `std::atoi` で整数化し、値が 1 / 2 / 4 のときだけその値を返し、それ以外はすべて 0 を返す（`fused_gr.cu:1612-1613`）。空白除去・範囲 clamp・大文字小文字の判定はない。

| 設定値 | `atoi` | `gr_r2()` |
|---|---|---|
| 未設定 | — | 2（既定） |
| `2`, `02`, ` 2`, `2abc`, `2.9` | 2 | 2 |
| `1`, `4` | 1 / 4 | 1 / 4 |
| 空文字 `""`, `abc`, `3`, `8` | 0 など | 0 |
| `-2`, `-1` | 負値 | 0 |

0 と無効値は区別されない。`atoi` は数字の後ろを無視するため `4x` も 4 になる。

token 数ごとの実際の選択（`S = 1`、`R2V` が行数。`fused_gr.cu:4363-4377`）:

| `n_tok` | R2=1 | R2=2（既定） | R2=4 | R2=0 / 無効値 |
|---|---|---|---|---|
| 1〜4 | `<1,K,true,1>` | 同左 | 同左 | 同左 |
| 5 | `<1,5,true,1>` | `<1,5,true,2>` | `<1,5,true,1>` | `<1,5,true,1>` |
| 6 | `<1,6,true,1>` | `<1,6,true,2>` | `<1,6,true,1>` | `<1,6,true,1>` |
| 7 | `<1,7,true,1>` | `<1,7,true,2>` | `<1,7,true,4>` | `<1,8,false>`（generic） |
| 8 | `<1,8,true,1>` | `<1,8,true,2>` | `<1,8,true,4>` | `<1,8,false>`（generic） |

R2=4 は 5・6 token では 4 行にならず 1 行の exact-T に落ちる（`fused_gr.cu:4367-4370`）。up の `gr_up_v3_kernel` は行数引数を持たず、1〜6 token は R2 に関係なく exact-T、7・8 token は R2 が 1/2/4 なら exact-T、0 なら generic（`fused_gr.cu:983`, `4381-4389`）。

## 有効になる条件

- CUDA の v3 read が動いていること。`STRATA_GR_V3=1`、または compute capability 12.0 のディスクリート GPU で 13 GiB 超の既定（`fused_gr.cu:4303-4307`）。HIP ビルドは既定 off で、同じ分岐は `STRATA_GR_V3=1` のときだけ到達する（本調査では実行確認していない）。
- `split == 1` であること。8 token 分の dynamic shared memory（`8 * N * 4` = 80 KB）の opt-in が取れるカードだけが `split = 1` になり、64 KB のカードは `split = 2` で R2 の分岐に来ない（`fused_gr.cu:4313-4349`）。
- Q8 read でないこと（`q8_down` / `q8_up` が null、`fused_gr.cu:4284-4292`）、`s_down` / `s_up` が null（`STRATA_HC_REQ8` off、`fused_gr.cu:4349`）。
- `STRATA_GR_RDNA` の読みが有効でないこと（`fused_gr.cu:4293-4301`）。`STRATA_HC_PERSIST=1` の persist read は呼び出し側で先に試される（`engine/src/core/verify.cpp:1816`）。
- `STRATA_GR_V3_PF` の mask が先に dispatch しないこと。down は bit 7 かつ `n_tok >= 5`、bit 8、bit 0-1 のいずれかで先取りされ（`fused_gr.cu:4358-4362`）、up は bit 2-3 で先取りされる（`fused_gr.cu:4380`）。この既定 mask は `STRATA_SM120_PERF` 有効かつ `STRATA_DEFAULTS` が 026 でない sm_120 で 133（bit 0・2・7）なので（`engine/include/strata/core/bw_dense_defaults.hpp:16`）、そのカードでは down・up とも R2 の分岐に到達しない。
- 値が 1 / 2 / 4 のいずれかであること。

満たさないときは exact-T 1 行版または generic kernel に落ちるだけで、ログもエラーも出ない。

## 実行時の詳細

`static const int` の初回呼び出し時に 1 度だけ読み、以降はその値を返す（`fused_gr.cu:1612`）。プロセス起動時ではなく、最初に 5〜8 token の v3 read がこの分岐を通った時点で確定するため、実行中の変更は反映されない。子プロセスへ値を渡す処理はない。

効果は down kernel の起動形だけである。`THREADS = 256`、`WARPS = 8`、`LR = 320` より、grid は `LR / (WARPS * R2) + 1` ブロック × `HC` で、R2=1 が 41×4、R2=2 が 21×4、R2=4 が 11×4 になる（`fused_gr.cu:54-55`, `4367-4376`）。kernel 側では warp が `R2` 行（`row0 = (rg * WARPS + warp) * R2`）を受け持ち、inject ブロックは warps 0-3 の 1 行ずつのまま（`fused_gr.cu:782-786`）。dynamic shared memory は `K * N * 4` バイトで行数によらず、opt-in は `fused_gr.cu:4322-4329` で行われる。

token 数は呼び出し元の verify window 幅（`engine/src/core/verify.cpp:1683`, `1817`）で、8 を超える window は 8 以下のスライスに分けて読まれる（`engine/include/strata/kernels/fused_gr.hpp:70-72`）。

## ログと測定値

この変数専用のログ・警告・終了経路はない。無効値も無言で 0 として扱われる。

ソースとコメントに本変数の測定値はない。導入 commit `21f950b4b` のメッセージは "decode c=8 +5%" とだけ書き、機種・モデル・量子化・回数を残していないため、条件付きの測定値としては引用しない。`docs/DETAILS.md` と `docs/SETTINGS.md` に本変数の記載はない。設定台帳 `terminal/data/settings-register.json:12851-12883` は `status: "default"`、`code_default: "2"` として載せ、`engine_sets` / `launch_sets` は空（`docs/SETTINGS.md` は opt-in と rollback のみを掲載する）。同台帳の note が指す 1595 行はコメント位置で、`getenv` は 1612 行。

## 根拠

- `engine/src/kernels/cuda/fused_gr.cu:1609-1614` — コメントと `gr_r2()`（getenv / atoi / 1・2・4 以外は 0）
- `engine/src/kernels/cuda/fused_gr.cu:4356-4377` — v3 mask による先取りと down の分岐順
- `engine/src/kernels/cuda/fused_gr.cu:4379-4389` — up の分岐（R2 は 7・8 token の exact-T 選択のみ）
- `engine/src/kernels/cuda/fused_gr.cu:4303-4349` — v3 の決定、`split` の算出、Q8 / `s_down` の除外
- `engine/src/kernels/cuda/fused_gr.cu:772-786` — `gr_down_v3_kernel` の `R2V` と行の割り当て
- `engine/include/strata/core/bw_dense_defaults.hpp:16` — `STRATA_GR_V3_PF` の既定 mask 133
