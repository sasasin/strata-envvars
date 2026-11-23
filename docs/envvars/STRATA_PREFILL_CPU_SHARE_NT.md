# `STRATA_PREFILL_CPU_SHARE_NT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CPU prefill share が CPU に割り当てる候補にできる「1 expert に route された token 数」の上限を決める。8 以下なら CPU pool の一 job 幅である 8 と同じ扱いになり、8 より大きい値はより多く route された expert も候補にする。CPU が取る expert 数の割合や prompt chunk の上限を決める変数ではない。候補を CPU で処理した行は既存どおり GPU に戻される。`engine/src/prefill/prefill.cpp:715-729,6034-6057,6301-6318`、`engine/include/strata/kernels/cpu/expert.hpp:143`。

## 値と判定

`std::getenv` の結果を `std::atoi` で整数化する。文字列全体の妥当性検査やエラー報告はなく、変換後の値を下表の規則で 8〜256 に収める。したがって空文字、数字で始まらない文字列、`0anything` は `atoi` が 0 を返し 8 になる。`9`〜`256` はその整数、`257` 以上は 256、負数と `0`〜`8` は 8 になる。`atoi` が認識する先頭空白や符号は許容され、後続文字は数値変換に使われない。大文字小文字の比較はない。`engine/src/prefill/prefill.cpp:720-728`。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 通常の CPU share | `env_n=0` を 8 に丸める | 9〜256。1〜8 は 8、257 以上は 256 に丸める | 独立した無効値扱いはない。空文字・`abc`・`0anything` は変換値 0 から 8 |
| 未設定かつ `g_share_default` が立ち、share 自体も未指定で、default-arm が `g_share_nt_arch` を設定 | 正の `g_share_nt_arch` を使い、その後 8〜256 に丸める | 環境変数を設定するとこの arch 値に優先する | 空文字を含め、設定値が存在すれば arch 値を使わない |

`cpu_share_nt()` は最初の呼び出しで設定有無と `atoi` の結果をそれぞれ `static` に保存する。そのため実行中の環境変更は反映されない。arch 由来の幅は呼び出し時に判定されるが、環境値が設定済みなら優先されない。`STRATA_PREFILL_CPU_SHARE=auto` など CPU share 自体が明示されている場合も arch 由来の幅は選ばれず、この変数が未設定なら 8 になる。`engine/src/prefill/prefill.cpp:691-704,720-728`。

CUDA では、起動時に全可視 GPU の compute capability が同じ場合に NVIDIA 既定表が適用され、ユーザーが未設定なら sm_86、sm_89、sm_120 の各表が本変数を `32` に設定する。適用前にユーザー設定の有無を確認し、設定済みなら値を保持する。sm_86 は `STRATA_SM86_PERF` が先頭 `0` なら表を使わず、sm_89/sm_120 は対応する `STRATA_SM89_PERF` / `STRATA_SM120_PERF` が先頭 `0` または `STRATA_DEFAULTS=026` なら表を使わない。異なる capability の複数 GPU ではこの NVIDIA 既定表適用をスキップする。`engine/src/core/nv_defaults.cpp:15-18,41-74,75-103,104-129,222-234`、`engine/src/program/generate.cpp:4416-4444`。

## 有効になる条件

- CPU prefill share が実際に使われること。本変数は share の ON/OFF を決めない。share は他の設定・既定 arm によって有効になる必要がある。`engine/src/prefill/prefill.cpp:691-704,3812-3868`。
- Prefill が CPU pool を保持し、`stream_all` ではなく、share が block されていないこと。さらに native expert layout で、expert source があり、CPU 側で処理停止状態でないことが必要。`engine/src/prefill/prefill.cpp:4635-4640,5876-5887`。
- 対象 expert は当該 chunk で 1 token 以上が route され、GPU cache に resident でなく、peer GPU が処理する対象でもない必要がある。さらに重み blob が pinned、または transient でない安定した host source でなければ候補に入らない。`engine/src/prefill/prefill.cpp:6015-6035`。
- 候補は route token 数の少ない順に検討され、share の割合に応じた個数まで CPU に割り当てる。1 layer あたりの CPU rows は `kShareRowsMax`（16384）で制限され、上限を超える候補で打ち切る。`engine/src/prefill/prefill.cpp:6037-6047,729`。
- 呼び出し元の通常経路は multi-GPU でなく、`--no-pool` でなく、default share 条件が成立する場合に既定 arm を依頼する。バッチ設定、モデルの全 expert が GPU cache にある状態、GPU/backend ごとの既定条件などで既定 share が arm されない場合がある。明示的な CPU share 設定は別経路で扱われる。`engine/src/program/generate.cpp:23871-23877`、`engine/src/prefill/prefill.cpp:3812-3868`。
- NVIDIA の上記環境変数既定値は CUDA の起動時処理だけで設定される。一方、`cpu_share_nt()` 自体は共有 prefill 実装にあり、CPU share が有効な経路で値を参照する。対象変数に同名 CLI 引数は見つからず、CLI の `--no-pool` などは share の適用可否に影響する。`engine/src/program/generate.cpp:4416-4444,23871-23877`。
- `docs/DETAILS.md` の説明と測定条件は CUDA の share 適用時に限られる。本調査ではそこに記された性能値を AMD に一般化しない。`docs/DETAILS.md:1181`。

## 実行時の詳細

CUDA prefill の初期化では、share が有効で CPU pool がある場合に `cpu_share_nt()` を使って rows buffer の容量を確保する。実際の layer 処理では `c <= cpu_share_nt()` を候補条件として判定し、選ばれた expert の入力を CPU pool に渡す。幅が 8 を超える expert も CPU job にする場合、expert blob を共有しつつ処理を最大 8 token/job に分割し、出力 rows を GPU に戻す。router の選択自体はこの上限で変更されない。`engine/src/prefill/prefill.cpp:2676-2682,6034-6057,6301-6318`、`engine/include/strata/kernels/cpu/expert.hpp:143`。

値と設定有無は `cpu_share_nt()` の初回呼び出し時に cache される。CUDA の `apply_nv_defaults()` は engine の環境設定読み取りより前に呼ばれ、未設定の既定表項目だけを環境へ追加するため、同一プロセスの後続読み取りではその値が使われる。`engine/src/program/generate.cpp:4416-4444`、`engine/src/core/nv_defaults.cpp:222-234`。

## ログと測定値

この変数専用の有効・無効ログや parse error はない。CUDA の既定表が何かを設定した場合は `strata: sm_86 (Ampere): ... speed switches on by default ...`、`sm_89 (Ada)`、`sm_120 (Blackwell)` のいずれかの一覧行に設定名が含まれる。CPU share の default arm がリンク規則を使った場合は `prefill: CPU share rule: ... experts of up to %d tokens go to the CPU.` の行が幅を表示する。`engine/src/core/nv_defaults.cpp:247-253`、`engine/src/prefill/prefill.cpp:3831-3840`。

## 根拠

- `engine/src/prefill/prefill.cpp:715-729` — 役割、parse、clamp、arch-derived override。
- `engine/src/prefill/prefill.cpp:2676-2682,3812-3868` — 初期化時の容量計算と share arm 条件。
- `engine/src/prefill/prefill.cpp:4635-4640,5876-5887,6015-6057,6301-6318` — pool・source 条件、候補選定と CPU job 実行。
- `engine/src/program/generate.cpp:4416-4444,23871-23877` — 起動時 NVIDIA defaults と通常生成経路からの arm。
- `engine/src/core/nv_defaults.cpp:41-74,75-103,104-129,222-253` — GPU 世代ごとの既定値、ユーザー設定優先、観測ログ。
- `engine/include/strata/kernels/cpu/expert.hpp:143` — CPU job の `MAXT=8`。
