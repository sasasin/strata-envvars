# `strata --no-coupled-draft`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（root） |
| オプション | `--no-coupled-draft` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

MTP drafter がサンプリング中に target と同じ sampler chain・乱数 draw を使って draft を提案する coupled draft sampling を無効にし、通常の argmax draft にします。MTP 自体や target 側のサンプリングを無効にするフラグではありません。索引上の配置は `strata-engine/root/` です（[`docs/cli/README.md`](../../README.md) の `strata-engine` 節）。parser は CUDA/HIP 系の `engine/src/program/generate.cpp` と SYCL 系の `engine/sycl/src/program/generate.cpp` にあります（`engine/src/program/generate.cpp:873,3978-3979`、`engine/sycl/src/program/generate.cpp:551,1996-1997`）。

## 使い方

```sh
# MTP を使う実行で、draft 提案を argmax にする
strata --pack /path/to/model.strata --mtp /path/to/mtp --no-coupled-draft
```

`--mtp` の指定方法など、モデル・入力に必要な条件はこのフラグの parser では検証しません。例は `strata` の root parser が受け取るフラグの組み合わせを示しています（`engine/src/program/generate.cpp:3851,4055`）。

## 値と既定値

値は不要です。parser は引数列を順に走査し、このフラグで `o.coupled_draft = false` を設定します。値の validation はありません。同じ実行で `--coupled-draft` と両方を指定した場合は、後に処理された方が最終値になります（`engine/src/program/generate.cpp:3978-3979`、SYCL: `engine/sycl/src/program/generate.cpp:1996-1997`）。

このフラグを省略したときの初期値は `coupled_draft_env()` によります。CUDA/HIP 系では `STRATA_SPEC_COUPLED` が空でなく、文字列 `0` でなければ有効です。SYCL 系も同じ環境変数を同じ条件で読みます（`engine/include/strata/core/coupled_draft.hpp:57-62`、`engine/sycl/include/strata/core/coupled_draft.hpp:55-60`）。

## 実行時の動作

引数処理後、CUDA/HIP 系と SYCL 系はいずれも設定値を `set_coupled_draft` に渡します（`engine/src/program/generate.cpp:4614`、`engine/sycl/src/program/generate.cpp:2231`）。MTP がロードされている場合に限り、各生成経路が request の sampler 設定を drafter に渡します（CUDA/HIP: `engine/src/program/generate.cpp:21426,24541`、SYCL: `engine/sycl/src/program/generate.cpp:11578,13784`）。

coupled draft が有効で、request が greedy でなく温度が正の場合に MTP は coupled sampling を使います。CUDA/HIP 系ではさらに温度が `spec_min_temp()` 以上であることが条件です。無効時または条件外では MTP の draft head の argmax を選びます（CUDA/HIP: `engine/src/core/mtp.cpp:855-860,1521-1539`、SYCL: `engine/sycl/src/core/mtp.cpp:737-742,1231-1242`）。このため、MTP がない実行や greedy request では、このフラグによる draft 提案の変化はありません。

coupled sampler の setup は MTP の bind 時にフラグ状態を確認して行われ、無効ならその coupled 用バッファは通常確保されません（CUDA/HIP: `engine/src/core/mtp.cpp:802-825,1014`、SYCL: `engine/sycl/src/core/mtp.cpp:678-699,875`）。ただし CUDA/HIP 系では `STRATA_SPEC_PROB` が有効だと `coupled_draft_env()` が true になり、同じ setup が必要です。また `set_draft_sampling()` は setup 成功状態を見て有効化するため、この環境変数が有効な場合は `--no-coupled-draft` だけでは probabilistic draft sampling を止めません（`engine/include/strata/core/coupled_draft.hpp:65-79`、`engine/src/core/mtp.cpp:818-820,842-856`）。SYCL 側の `coupled_draft_env()` は `STRATA_SPEC_COUPLED` の状態だけを返します（`engine/sycl/include/strata/core/coupled_draft.hpp:63-69`）。

## 適用条件と副作用

- 対象は `engine/src/program/generate.cpp` の root parser です。Qwen3.5 MoE は model header に応じて `engine/src/qwen35` の別 parser に先に振り分けられますが、このオプション文字列は同 parser 側には見つかりません。したがって本書の説明を Qwen3.5 専用 parser に適用できるとは確認できません（振り分け: `engine/src/program/generate.cpp:3804-3818`）。
- parser 自体は GPU・ファイル・ネットワークへの副作用を行いません。実行経路では、coupled sampling が有効な場合に限り MTP 用 GPU buffer / scratch を確保し、失敗時は `mtp: the coupled draft sampler's buffers do not fit` などの bind error を返します。無効化すれば、`STRATA_SPEC_PROB` が有効な CUDA/HIP 経路を除き、この coupled setup を省きます（`engine/src/core/mtp.cpp:802-820`、`engine/sycl/src/core/mtp.cpp:678-695`）。
- SYCL は `STRATA_SPEC_MIN_TEMP` 条件をこの `set_draft_sampling()` の判定に使わず、CUDA/HIP 系とは有効条件が異なります（`engine/sycl/src/core/mtp.cpp:737-742`）。

## 出力とエラー

このフラグ固有の成功メッセージや validation error はありません。parser に認識されない引数は `unknown argument: ...` を stderr に出し、usage を表示して status 2 で終了します（`engine/src/program/generate.cpp:4268-4273`）。coupled setup を有効にした経路では、scratch が draft logits の幅に対応できない場合は stderr に理由を出して argmax draft に fallback します（CUDA/HIP: `engine/src/core/mtp.cpp:802-809`、SYCL: `engine/sycl/src/core/mtp.cpp:678-684`）。

## 根拠

- `engine/src/program/generate.cpp:873,3978-3979,4614` — 初期値、parser 登録、global state への反映。
- `engine/sycl/src/program/generate.cpp:551,1996-1997,2231` — SYCL parser と global state への反映。
- `engine/include/strata/core/coupled_draft.hpp:57-83`、`engine/sycl/include/strata/core/coupled_draft.hpp:55-70` — 環境変数の読み取りと state の設定。
- `engine/src/core/mtp.cpp:802-856,1521-1539`、`engine/sycl/src/core/mtp.cpp:678-742,1231-1242` — sampler setup、request 条件、coupled / argmax の分岐。
- `engine/src/program/generate.cpp:3804-3818` — Qwen3.5 MoE の別 parser への振り分け。
