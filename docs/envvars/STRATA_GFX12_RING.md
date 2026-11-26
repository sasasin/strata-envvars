# `STRATA_GFX12_RING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

HIP gfx12 の prompt staging ring を、行列コア attention が要求されていて、他の ring 指定がない場合に深くする既定値制御である。無効化すると通常の `ring_slots()` ルールに戻る。この変数自体は ring のスロット数を指定せず、gfx12 用の深い既定値を使うかどうかだけを決める。効果は `engine/src/prefill/prefill.cpp` の `ring_slots()` が返す ring 数と、そこから確保・使用される staging buffer に現れる（同ファイル 843-882、2865-2869 行）。

## 値と判定

`std::getenv("STRATA_GFX12_RING")` の結果を関数内 `static const bool` に保存し、未設定でなく、かつ先頭文字が `'0'` の場合に限って深い既定値を抑止する。文字列全体の比較や数値変換はしない（`engine/src/prefill/prefill.cpp:858-861`）。

| 条件 | unset | 深い既定値を許可する値 | 深い既定値を抑止する値 |
|---|---|---|---|
| 下記「有効になる条件」を満たす経路 | 許可 | 空文字、`1`、`true`、`false`、および先頭文字が `0` でない任意の文字列 | `0`、`00`、`0anything`（先頭文字が `0`） |

空文字は `getenv` が非 null であっても `e[0] == '0'` ではないため許可側になる。大文字小文字、後続文字、数値としての妥当性、空白は検査されない。`0` で抑止される場合も、gfx12 固有ルールが無効になるだけで、ring 自体が無効になるわけではない（同ファイル 860-878 行）。

## 有効になる条件

- HIP ビルドであること。gfx12 用分岐は `STRATA_USE_HIP` の下にある（`engine/src/prefill/prefill.cpp:845-867`）。
- `ring_slots(T)` の呼び出しがあり、その時点で `STRATA_PREFILL_RING` が未設定、`g_ring_override <= 0`、かつ `qsa_prompt_attn_matrix_cores_requested()` が true であること（同ファイル 843-850 行）。明示的な `STRATA_PREFILL_RING` または正の ring override があると、この変数による特例分岐は使われない。
- 現在の HIP device が gfx12 であること。行列コア要求の判定は `STRATA_HIP_WMMA` の設定と arch、失敗状態を参照し、gfx12 判定も別途行う（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2433-2451`）。gfx11 で行列コアを要求しても gfx12 特例にはならない。
- `STRATA_HIP_WMMA` が未設定または空文字の場合、gfx12 の既定は Windows 以外の build で ON、Windows で OFF。`STRATA_HIP_WMMA=1` は Windows でも要求を有効にできる。`auto` も gfx12 では要求扱いになるが、実際の attention kernel の選択は別の per-call 条件に従う（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2236-2250, 2260-2273`; `engine/include/strata/core/gfx12_platform_defaults.hpp:10-16`）。
- prompt chunk が `stream_all_min()` 以上でなければ深い値は返らず、従来どおり `STAGE`（8 slots）になる（`engine/src/prefill/prefill.cpp:849-850, 862-878`）。

## 実行時の詳細

`ring_slots(T)` は `STRATA_PREFILL_RING` を毎回取得し、gfx12 特例の条件を満たした場合、`STRATA_GFX12_RING` の判定結果を初回に static cache する。したがってこの変数の変更は、その static 初期化後にはプロセス内で反映されない。一方、他の ring 条件を満たさず gfx12 特例の枝に入らない限り、この変数の値は読まれない（`engine/src/prefill/prefill.cpp:843-861`）。

特例が有効で chunk が `stream_all_min()` 以上の場合、12,288 tokens 以上なら 96 slots。12,288 未満では、6,144 以下なら最大 256、6,144 超なら最大 192 slots とし、blob サイズに応じた約 800 MiB の上限（`MAXBLOB() > 0` なら `max(96, floor(800 MiB / MAXBLOB())`）で制限する。深い既定値を使わない場合の ring 数は、`STRATA_PREFILL_RING`、layer split の override、ring budget、pinned share など通常ルールに進む。chunk が stream floor 未満なら `STAGE` に戻る（同ファイル 862-878 行）。

`STRATA_PREFILL_RING` が設定されていれば `atoi` の戻り値が明示 ring 数として優先され、gfx12 特例を迂回する。文字列全体の検査ではないため、空文字や数値に変換できない文字列は 0、`96tail` は 96 になる。明示値が `STAGE` (=8) なら 8、それ以外は通常ルールで 16 以上 `ring_cap()` 以下に clamp される（同ファイル 843-850, 873-878 行）。正の layer split override も同様に特例を迂回する（同ファイル 873-875 行）。serve の multi-GPU layer split では `STRATA_SPLIT_RING` から決まった正値を `Prefill::set_ring_override()` に渡す経路がある（`engine/src/program/generate.cpp:11828-11843`; `engine/src/prefill/prefill.cpp:3555-3559`）。CLI の `--prefill` / chunk planning は `T` に影響し、閾値を通じて返る slot 数に影響するが、この変数の値判定そのものを上書きしない（同ファイル 4286-4303 行）。

返された slot 数は prefill layout の `m.ring` と staging slots に使われ、prompt chunk の非 resident experts を stream する経路は `m.ring > STAGE`、chunk が stream floor 以上、かつ expert source があるときに有効になる（`engine/src/prefill/prefill.cpp:2865-2869, 4625-4629`）。

## ログと測定値

`STRATA_GFX12_RING` 自体の値や、特例の採用を示す専用ログは見つからない。行列コア側では device 判定時に条件に応じて `strata: the prompt attention on matrix cores ...` または Windows 向けの案内を stderr に出す（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2262-2273`）。ring に伴う prefill buffer 確保に失敗すると、`Prefill::init` は `prefill: device buffers for a chunk of ... tokens do not fit (...)` をエラー文字列に設定して false を返す（`engine/src/prefill/prefill.cpp:2738-2746`）。無効文字列を拒否したり警告したりする処理はない。

`docs/DETAILS.md:1211` は gfx12/Linux の ring を記載し、`STRATA_GFX12_RING=0` または `STRATA_PREFILL_RING=96` を旧値に戻す指定として挙げ、R9700 の prompt 4K/2K/8K の測定値を示している。ただし同表にはモデル、量子化、測定回数などの条件がないため、本書では数値を一般的な効果として扱わない。実装コメントは R9700 (gfx1201) でリング深度を比較した条件を記すが、一般環境の性能保証ではない（`engine/src/prefill/prefill.cpp:851-857`）。

## 根拠

- `engine/src/prefill/prefill.cpp:843-878` — ring 値の取得、gfx12 特例、値の算出、通常ルールへの fallback。
- `engine/src/prefill/prefill.cpp:2865-2869, 4625-4629` — layout への slot 適用と streaming 条件。
- `engine/src/kernels/cuda/qsa_prompt_attn.cu:2236-2276, 2433-2451` — `STRATA_HIP_WMMA` の mode、platform/arch による要求判定と gfx12 判定。
- `engine/include/strata/core/gfx12_platform_defaults.hpp:10-16` — gfx12 default の Windows 判定。
- `engine/src/program/generate.cpp:11828-11843`; `engine/src/prefill/prefill.cpp:3555-3559` — serve layer split の ring override。
- `docs/DETAILS.md:1211` — gfx12 prompt staging ring に関する資料上の記載。
