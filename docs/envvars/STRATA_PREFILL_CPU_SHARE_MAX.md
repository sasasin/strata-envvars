# `STRATA_PREFILL_CPU_SHARE_MAX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU prefill share が使われるとき、routing 後に staged 処理する prompt chunk の上限（token 数）を決める。上限より小さい chunk では、GPU が PCIe 経由で処理する非 resident expert の一部を idle な CPU pool に渡す。対象変数だけでは share を有効にしない。share が無効ならこの上限は CPU share の実行を開始させない。`Prefill::arm_cpu_share()` が share を適用すると `g_stream_min_share` に上限を設定し、通常はこの境界以上の chunk が全 expert を stream する経路に入る（`engine/src/prefill/prefill.cpp:730-743,3868`）。CPU が計算した行は GPU の行と同じ bit になる保証がない（`engine/include/strata/prefill/prefill.hpp:301-308`）。

未設定値は通常 `3072`。ただし CUDA build で見えているカードが同一 compute capability 8.9（Ada）の場合、起動時に Strata が未設定変数を `6144` に設定する。値を明示した場合はこの既定設定と、CPU share のカード別・リンク別上限を上書きする（`engine/src/core/nv_defaults.cpp:75-103,222-237`; `engine/src/program/generate.cpp:4421-4449`; `engine/src/prefill/prefill.cpp:734-743`）。`docs/DETAILS.md:1202` は一般の上限を `3072` と記載しており、現行ソースにある sm_89 の `6144` 起動時既定値までは記載していない。ここでは実装の条件付き動作を優先した。

## 値と判定

`cpu_share_max()` は初回呼び出し時に値を `static` 変数へ保存する。設定値は `std::atoll` で10進数の先頭部分を変換する。先頭空白と符号を許し、数値の後ろは検査しない。変換値が `1024` 未満なら `1024` に clamp する。文字列全体の妥当性検査や上限 clamp はない。`atoll` が数値として読めない文字列は `0` となり、下限に clamp される。数値に続く文字は変換結果に影響しない（例: `1536tail` は `1536`）。`atoll` の表現範囲外の入力の結果はここでは規定しない（`engine/src/prefill/prefill.cpp:733-743`）。

| 状況 | 未設定 | 設定値の例と結果 |
| --- | --- | --- |
| 一般の経路（CPU share が default-armed でない、または明示 share / peer share） | `3072` | `1024` → `1024`; `1536` → `1536`; `6144` → `6144`; `0`、負数、空文字、`true`、`abc` → `1024`; `1536tail` → `1536` |
| CUDA、全可視カードが同一 sm_89、かつ `STRATA_SM89_PERF` が `0` でなく `STRATA_DEFAULTS` が `026` でない | 起動時に Strata が `6144` を設定 | 利用者が空文字を含む何らかの値を設定していれば、その設定を保持し上表の変換を適用 |
| default-armed share、変数未設定、`STRATA_PF_PEER_CPU` が無効 | 通常は `share_rules` の既定値。条件を満たす CUDA/HIP アーキテクチャではカードまたは PCIe link の規則による値 | 明示値はアーキテクチャ規則より優先し、上表の変換後の値を使う |

設定の有無を調べる別の `static` 判定もあり、空文字でも「明示設定」として扱う。そのため空文字は `1024` になり、未設定時のカード別自動上限を選ぶ分岐には入らない。sm_89 の起動時既定値も、環境変数が空文字で設定済みなら適用されない（`engine/src/prefill/prefill.cpp:734-743`; `engine/src/core/nv_defaults.cpp:227-234`）。

`STRATA_PREFILL_STREAM_MIN` が `0` 以上なら、chunk を全 expert stream に切り替える境界は同変数が優先される。CPU share の上限は別にバッファ sizing 等でも参照される。CLI の専用上書き引数は確認できなかった（`engine/src/prefill/prefill.cpp:648-658,2652-2681`）。

## 有効になる条件

- CPU share が適用されること。通常の CLI 経路では CPU pool があり、単一 GPU・batch 無効・resident cache に未収容の expert があるなど、default share の条件を満たす場合だけ自動で arm される。server 経路も pool、batch、share layout、未収容 expert の有無で適用を判定する（`engine/src/program/generate.cpp:11868-11883,11903-11906,23977-23983`）。
- 未設定時の default share は CUDA の対応経路に加え、HIP では gfx12 / gfx11 の条件を満たす経路がある。その他で `STRATA_PREFILL_CPU_SHARE` を設定した場合の適用可否は `arm_cpu_share()` の分岐に従う。この対象変数だけを設定しても share は arm されない（`engine/src/prefill/prefill.cpp:681-686,3812-3868`）。
- default-armed share では、GPU cache に全 expert が resident なら自動 arm されない。CLI/server の default share は host RAM / Windows commit に必要な余裕がない場合にも arm されない。explicit な `STRATA_PREFILL_CPU_SHARE` はこの memory gate で止められず、RAM 不足の警告対象になる。batch は通常無効で、server batch は `STRATA_PREFILL_CPU_SHARE_BATCH=1` で pool 条件を満たしても、slot が decode 中の prompt read では share が block される（`engine/src/program/generate.cpp:11868-11883,12273-12300,12374-12390,23979-23983`; `engine/src/prefill/prefill.cpp:4630-4639`）。
- 通常の CPU share は staged chunk に対して働く。`stream_all_min()` 以上の chunk、chunk 化されない経路、CPU pool が同時に使われている経路では CPU share は処理しない（`engine/src/prefill/prefill.cpp:648-658,4630-4639,5876-5877`）。
- default-armed CUDA share では `STRATA_SWITCH_POINT` が有効なカードの floor から上限を計算し、さらに `STRATA_PREFILL_CPU_SHARE_AUTO` の link rule が有効なら PCIe link・resident expert 数・pool worker 数から上限を計算する。前者は CUDA の測定クラス（single discrete GPU、link probe 済み、sm_86）で unset 時に有効、`=1` なら任意 CUDA card、`=0` または `1` 以外なら無効。後者は CUDA discrete card の link probe 後、unset 時は sm_120/sm_89/sm_86、`=1` なら任意 CUDA card、空文字または `1` 以外は無効。link rule 自体が自動算出する上限は最大 `20480` tokens だが、明示した `STRATA_PREFILL_CPU_SHARE_MAX` はこの cap を経由せず、下限 `1024` のみ適用される（`engine/include/strata/prefill/share_rules.hpp:60-82`）。明示 max はこれらの算出上限より優先される（`engine/src/prefill/prefill.cpp:470-510,3816-3834`; `engine/include/strata/prefill/switch_point_rule.hpp:113-122`; `engine/include/strata/prefill/share_rules.hpp:89-99`）。
- default-armed HIP gfx12 は `STRATA_DEFAULTS=026` または `STRATA_GFX12_DEFAULTS=0` で無効化される。gfx12 の自動上限は fused IQ2_S / IQ4_XS の状態から `2304` または `3072`。HIP discrete gfx11 (gfx1100/1101/1102) の既定 share は `STRATA_DEFAULTS=026` または `STRATA_GFX11_DEFAULTS=0` で無効化され、上限は既定 `3072`。明示した max は有効な share のこれらの値を上書きする（`engine/src/prefill/prefill.cpp:3842-3868`; `engine/src/core/arch_defaults.cpp:109-116`; `engine/include/strata/core/gfx11_extra.hpp:27-30,139-146`; `engine/include/strata/prefill/share_rules.hpp:23-36`）。
- two-card CUDA layer split の default share layout は `STRATA_SPLIT_CPU_SHARE=0` で無効化できる。split の link rule は staged-stream floor が `3072` を超える場合に default share を arm する。明示 max はその後の上限選択でも優先される（`engine/include/strata/prefill/share_rules.hpp:106-118`; `engine/src/prefill/prefill.cpp:3880-3892`; `engine/src/program/generate.cpp:11890-11906`）。
- `STRATA_PF_PEER_CPU` による peer GPU 経路では、変数が未設定の default share 上限をカード別自動値へ置き換える条件から除外され、fallback は `3072` となる。明示した上限値は使われる（`engine/src/prefill/prefill.cpp:705-713,734-743`）。

## 実行時の詳細

CUDA の起動処理では、同一 compute capability の可視カード群について `apply_nv_defaults()` が engine の env switch を読む前に呼ばれる。sm_89 の場合は `STRATA_SM89_PERF=0` または `STRATA_DEFAULTS=026` で既定表を外せる。表にある環境変数ごとに `getenv` を確認し、未設定なら Windows は `_putenv_s`、それ以外は上書きなしの `setenv(..., 0)` で値を入れる。したがって利用者が設定した空文字も保持される。異なる compute capability のカードが混在する場合、この `apply_nv_defaults()` 呼び出しは行われない（`engine/src/program/generate.cpp:4421-4450`; `engine/src/core/nv_defaults.cpp:75-103,222-237`）。

`cpu_share_max()` の数値と設定有無は初回アクセスで cache され、プロセス稼働中に環境を書き換えても反映されない。share が arm されるとその上限は `g_stream_min_share` に入り、`stream_all_min()` が staged / stream の境界として参照する。`STRATA_PREFILL_STREAM_MIN` が設定されていれば、その値が境界に優先する。上限は prefill 初期化時の CPU share buffer sizing にも使われる（`engine/src/prefill/prefill.cpp:648-658,734-743,2486-2488,2652-2681,3868`）。

初期化時の pinned buffer 確保失敗はその箇所ではエンジン終了にせず、prompt 処理側に再確保を残す。prompt 中に activation または rows buffer を確保できなければ、その実行の CPU share を止め、GPU が全 expert を処理する。明示的な終了や失敗はこの変数の変換処理にはなく、上限に応じたバッファ確保が資源不足に至る場合の挙動は個別の確保経路に従う（`engine/src/prefill/prefill.cpp:2655-2690,5878-5886,5907-5951`）。

## ログと測定値

- default-armed share の初回 arm 時、CUDA は stderr に `prefill: the CPU share is ON by default for prompt chunks up to %lld tokens (the idle CPU takes some of the experts the GPU would stream; answers can differ slightly from 0.1.40.3, mean KL ~0.004 below 1024 tokens, ~0.011 at 1-3K). STRATA_PREFILL_CPU_SHARE=0 turns it off, STRATA_PREFILL_CPU_SHARE_MAX=1024 keeps the old limit.\n` を出す。HIP gfx12 は `prefill: the CPU share is ON by default for prompt chunks up to %lld tokens on this gfx12 card (the idle CPU takes some of the experts the GPU would stream; answers can differ slightly: first-token KL ~0.02 at 1K tokens, prompts of 500-1,000 tokens +18..+31%, 2K and up unchanged). STRATA_PREFILL_CPU_SHARE=0 or STRATA_GFX12_DEFAULTS=0 turns it off, STRATA_PREFILL_CPU_SHARE_MAX=1024 keeps a 1,024 limit.\n`、gfx11 は `prefill: the CPU share is ON by default for prompt chunks up to %lld tokens on this gfx11 card (the idle CPU takes some of the experts the GPU would stream; answers can differ slightly: first-token KL ~0.01-0.02 below 3K tokens). STRATA_PREFILL_CPU_SHARE=0 or STRATA_GFX11_DEFAULTS=0 turns it off, STRATA_PREFILL_CPU_SHARE_MAX=1024 keeps a 1,024 limit.\n` を出す。表示値は `cpu_share_max()` の結果なので明示値やカード別規則が反映される（`engine/src/prefill/prefill.cpp:3837-3861`）。
- CUDA sm_89 の既定表で一つ以上の値が設定されると、`apply_nv_defaults()` は `strata: sm_89 (Ada): %zu speed switches on by default (STRATA_SM89_PERF=0 turns them off, as does STRATA_DEFAULTS=026; a switch you set is kept): ` に続けて設定名一覧を stderr に出す。一覧に `PREFILL_CPU_SHARE_MAX` が含まれる（`engine/src/core/nv_defaults.cpp:240-255`）。利用者設定が優先されてこの変数が一覧に含まれない場合もある。
- prompt 中に share 用 buffer を確保できない場合は `prefill: the CPU share is off for this run: the host could not give ... (RAM is short); the GPU streams every expert` を stderr に出す（`engine/src/prefill/prefill.cpp:5882-5886`）。
- 性能値はこの調査では測定していない。ソースコメントや `docs/DETAILS.md` の測定は条件付きの報告であり、現環境で再測定した結果としては扱わない。

## 根拠

- `engine/src/prefill/prefill.cpp:730-743,3812-3868` — 値の変換、cache、default-armed 上限との優先順位、arm 時の境界設定。
- `engine/src/prefill/prefill.cpp:648-658,2486-2488,2652-2690,4630-4639,5876-5886,5907-5951` — stream 境界、buffer sizing、CPU share の実行条件と失敗時 fallback。
- `engine/src/core/nv_defaults.cpp:75-103,222-255` — Ada sm_89 既定値の設定と既存設定の保持。
- `engine/src/program/generate.cpp:4421-4450,11868-11906,23977-23983` — 起動時順序、server / CLI の share 条件。
- `engine/include/strata/prefill/prefill.hpp:301-318`; `engine/include/strata/prefill/share_rules.hpp:23-36,60-78` — CPU share の効果と default rule の値。
