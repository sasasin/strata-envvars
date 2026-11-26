# `--expert-cache`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（engine の root 引数。generate 実行） |
| オプション | `--expert-cache` |
| 別名 | なし |
| 値 | `N`、または `auto`。`N` は VRAM に置く expert blob の slot 数 |

## 役割

MoE expert blob 用の VRAM cache を確保し、resident expert の行計算を GPU の hit path に回す。`--expert-profile` があれば profile の順位に従って cache を事前充填し、なければ実行中に先に要求された expert を収容する。cache が有効なときは GPU と CPU の演算順序の差により、cache 無効時と出力 token がわずかに異なる場合がある。

## 使い方

```sh
# VRAM の空き容量から cache サイズを自動決定する
strata --pack model.strata --expert-cache auto

# 2,000 slots を指定する（他の VRAM 利用量により確保できない場合がある）
strata --pack model.strata --expert-cache 2000

# expert profile がある場合、0 は自動サイズを選ぶ
strata --pack model.strata --expert-profile profile.bin --expert-cache 0
```

## 値と既定値

- 引数がない場合の初期値は `0`（cache 無効）。usage の説明も `DEFAULT 0` としている。
- `N` は `std::atoi` で整数化され、`N > 0` は明示 slot 数、`N = 0` は初期状態では無効を表す。`--expert-profile` を読み込んだときに限り、`0` は `auto`（自動サイズ）へ変換される。
- `auto` は内部値 `-1` となり、自動サイズ経路に入る。`-1` を直接指定しても同じ経路になる。`-1` より小さい値は resource parameter validation で拒否される。
- `std::atoi` による変換のため、数値でない文字列は `0` に変換され、通常は無指定時と同じ扱いになる。専用の形式エラーはない。引数自体を省略すると stderr に `--expert-cache needs a value` を出して終了コード 2。
- 同じオプションを複数回指定した場合、parser は各回の値で同じ設定値を更新するため、最後に解析された値が残る。

## 実行時の動作

自動サイズでは、重み・session/KV state などのロード後に GPU の空き容量を読み、reserve、prompt buffer、drafter/head 等の後続確保分を差し引いて slot 数を決める。profile がある場合は profile の pair 数を上限とし、native pack の layer ごとの blob サイズや `--expert-cache-per-layer` に応じた slot 構成にする。Metal では自動値に 1,500 slots の上限がある。起動時に `expert cache auto: ... -> ... slots` を stderr に出す。

自動サイズの cache は実 allocation 後にも slot を書き込み、空き VRAM が reserve を下回れば小さくして再確保する。allocation 自体に失敗した場合も自動時は cache を 3/4 に縮めて再試行し、最大 8 回まで縮小を試みる。明示した正の `N` は自動 sizing/retry の対象外で、単一 GPU では allocation 失敗をエラーとして終了する。layer split で明示値が容量を超えると、prompt buffer と reserve 分を残せる値まで切り下げて警告する。

正の slot が確保されると cache が VRAM を占有し、GPU の hit path が resident expert を計算する。profile があれば頻度順位で充填して eviction しない。profile がなければ実行中の routing 順に cache を埋める。`--expert-cache-per-layer` を併用した native pack では layer ごとに独立した slot 枠を割り当てる。prompt が cache slot を借りる構成では prompt 処理中に slot を貸し出し、その後戻す処理がある。

## 適用条件と副作用

- 実際の GPU hit hook は `--no-pool` が指定されると無効になる。cache 用 hit buffer も `--no-pool` 時には確保されないため、cache を指定しても resident expert の GPU 計算経路は有効にならない。
- `--cpu-oracle-q8-0` は `--expert-cache`（内部値が 0 以外）または `--expert-profile` と併用できず、該当時は終了コード 2 で拒否される。
- profile は読み込み時に検査され、読み込み失敗は stderr の理由と終了コード 1 になる。profile を利用する cache は profile に含まれる pair 数を超えて充填されない。
- cache allocation は VRAM を使う。自動 sizing は `--vram-reserve-mib`、prefill 条件、pipeline windows、draft head などと容量を調整する。自動 sizing で必要な最低 cache を確保できない場合は、空き不足の説明を stderr に出す。明示 slot 数は特に layer split で切り下げられる場合がある。
- cache 内 expert を GPU で計算するため、CPU だけで計算した場合と浮動小数点の丸めが異なり、近い logits の場合に出力が変わる可能性がある。
- Windows では GPU allocation が system commit（RAM + page file）にも計上され、VRAM に余裕があっても allocation が失敗する場合がある。自動時は縮小再試行し、最終失敗時は page file と `--expert-cache` を下げる案内を stderr に出す。

## 出力とエラー

- 自動 sizing、per-layer sizing、cache の slot 数と VRAM 使用量、利用 policy は stderr に出る。
- cache allocation と hit-path buffer allocation の失敗はエラーを stderr に出して終了コード 1。
- `--expert-cache < -1` など resource parameter validation に失敗すると `invalid sampling or resource parameter` を stderr に出して終了コード 2。
- layer split で明示値が容量を超える場合は警告を出し、確保可能な slot 数に補正する。

## 根拠

- `engine/src/program/generate.cpp:895-903` — `expert_cache` の初期値 `0` と状態。
- `engine/src/program/generate.cpp:1416-1419` — usage にある slot の説明と既定値。
- `engine/src/program/generate.cpp:3842-3847,3984-3987` — 引数値の取得、欠落時エラー、`auto` と `atoi` の変換。
- `engine/src/program/generate.cpp:5267-5274` — 値が `-1` 未満の場合を含む resource parameter validation と終了コード 2。
- `engine/src/program/generate.cpp:6746-6756` — profile の読込と、profile 指定時に `0` を自動値へ変換する条件。
- `engine/src/program/generate.cpp:9044-9077,9189-9249` — weights/session 後の自動 sizing、reserve と後続確保の考慮、Metal 上限、stderr 表示。
- `engine/src/program/generate.cpp:9420-9435,9444-9497` — layer split での明示値切り下げと、per-layer/profile による slot sizing。
- `engine/src/program/generate.cpp:9640-9715` — 自動 cache の実 allocation 後の空き容量確認、縮小・再試行、失敗時の終了コード 1。
- `engine/src/program/generate.cpp:9717-9741,10389-10427,10480-10484` — cache policy 表示、GPU hit buffer、`--no-pool` 時の hit hook 無効化。
- `engine/src/program/generate.cpp:9398-9418` — 最低 cache を確保できない場合に出す VRAM 不足メッセージ。
- `engine/sycl/src/program/generate.cpp:2002-2005` — SYCL parser にも同じ `auto` / `atoi` の値変換があること。
