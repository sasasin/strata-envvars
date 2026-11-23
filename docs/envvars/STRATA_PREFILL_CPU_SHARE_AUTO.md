# `STRATA_PREFILL_CPU_SHARE_AUTO`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

既定で有効になる CPU prefill share の chunk 上限と、CPU が担当してよい expert の token 数を、GPU の PCIe link 測定値と GPU 上に resident でない expert 数から決める規則を有効化する。これは CPU share 自体の on/off ではなく、その既定 share の上限・幅を決める追加規則である。規則が適用されると、prompt chunk の staging と、CPU が担当する非 resident expert の範囲が変わる。規則を使わない場合の既定 share は通常 3,072 tokens / 8-token experts である。`Prefill::arm_cpu_share` が規則の結果を保存し、既定 share を有効にする（`engine/src/prefill/prefill.cpp:3812-3840`、`engine/include/strata/prefill/share_rules.hpp:38-46`）。

## 値と判定

`link_rule_env()` は `std::getenv` の値を `share_rules::env_state()` に渡す。未設定または空文字は `-1`（自動判定）、文字列全体が厳密に `"1"` の場合だけ `1`、それ以外は `0` になる。数値変換はせず、空白除去・大文字小文字変換・前方一致もしない。そのため `1` だけが明示的な有効値で、`01`、`1x`、`true`、`0`、` 1` は無効値。値は `link_rule_env()` の関数内 `static` に初回評価時保存され、プロセス実行中の環境変更は反映されない（`engine/src/prefill/prefill.cpp:499-503`、`engine/include/strata/prefill/share_rules.hpp:89-99`）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
| --- | --- | --- | --- |
| 非 HIP の単一 GPU 経路 | cc 12.0、8.6、8.9 の離散 GPU で link probe が取れていれば自動有効 | `1` は離散 GPU で probe が取れれば compute capability を問わず有効 | `0`、空白以外の任意文字列（例: `true`、`01`）は規則を無効化 |
| 非 HIP の2-card layer split | 全 stage が cc 12.0 の場合だけ自動有効。規則の計算結果が 3,072 を超える場合に share を既定で有効化 | `1` はこの規則の class 判定を外す | `0` は split の既定 share をこの経路で有効にしない |
| HIP | link 規則の呼び出しが無効 | 該当なし | `1` でもこの規則を有効にしない |

単一 GPU の link 規則は `F = (total - resident) × mean expert blob / link GB/s` を stream floor とし、pool worker 数に応じた係数を適用して 256-token 単位に切り下げる。上限は 3,072〜20,480 tokens。limit が 3,072 を超える場合、CPU が担当する expert 幅は通常 32 tokens、`F >= 3,000 ms` なら 64 tokens。上限が 3,072 のとき幅は規則から設定されず、通常の pool 上限（8 tokens）が使われる（`engine/include/strata/prefill/share_rules.hpp:60-87`）。split 経路では各 stage の stream floor の合計を同じ規則に渡す（`engine/src/program/generate.cpp:11811-11825`）。

## 有効になる条件

- **単一 GPU:** HIP を除くこのコード経路で、GPU が離散型であり、起動時 PCIe link probe が正の値を返し、card/cache 情報が設定済みであること。unset/空文字の自動判定では compute capability 12.0、8.6、8.9 が対象。`1` は compute capability の制限を外すが、離散 GPU と probe の条件は残る（`engine/src/prefill/prefill.cpp:477-511`、`engine/include/strata/prefill/share_rules.hpp:94-99`）。
- **2-card layer split:** serve の pool と欠けている expert があり、split の link probe が有効であること。実装は HIP を除く経路で規則を呼ぶ。unset/空文字時は全 stage が cc 12.0 であることが必要で、さらに計算された limit が 3,072 を超えた場合だけ既定 share を arm する。`1` は cc 判定を外す。ほかの split 構成ではこの既定 arm は行われない（`engine/src/program/generate.cpp:11811-11825`、`engine/src/prefill/prefill.cpp:3878-3896`）。
- 通常の非 serve 経路では単一 GPU、pool 有効、batch slots なしで、GPU cache に全 expert が収まっていないことが既定 share の条件。serve では pool が使え、share layout と欠けた expert があり、host memory gate を通る必要がある。batch slots と併用する serve は `STRATA_PREFILL_CPU_SHARE_BATCH=1` で pool を許可できるが、card 情報の設定は batch が 0 以下の経路だけなので、この link 規則は使われない。serve の既定 share layout は `STRATA_USE_SYCL` build を除外する一方、`link_rule_on()` 自体に SYCL 固有の guard はない。したがって通常経路での SYCL 適用可否は、同経路が設定する GPU 情報と link probe の値に依存し、この checkout の分岐だけから一律に断定できない（`engine/src/program/generate.cpp:11783-11810`、`engine/src/program/generate.cpp:11801-11804`、`engine/src/program/generate.cpp:12295-12310`、`engine/src/program/generate.cpp:23871-23877`、`engine/src/prefill/prefill.cpp:499-511`）。
- `STRATA_PREFILL_CPU_SHARE` が設定されていると既定 share の arm をこの規則で行わず、明示設定が優先される。特に `STRATA_PREFILL_CPU_SHARE=auto` も明示設定として扱われる。単一 GPU では先行する `STRATA_SWITCH_POINT` 規則が limit を設定した場合も、`g_share_limit_arch != 0` のため link 規則を適用しない（`engine/src/prefill/prefill.cpp:691-704`、`engine/src/prefill/prefill.cpp:3814-3827`、`engine/src/prefill/prefill.cpp:3880-3885`）。
- `STRATA_PREFILL_CPU_SHARE_MAX` を明示すると limit はその値が優先し、`STRATA_PREFILL_CPU_SHARE_NT` を明示すると expert 幅はその値が優先する。AUTO による limit / 幅の片方だけが上書きされることもある（`engine/src/prefill/prefill.cpp:720-743`）。
- HIP の default-share arm は別の gfx11/gfx12 判定を持つが、`STRATA_PREFILL_CPU_SHARE_AUTO` の link 規則呼び出しは HIP build で無効。`STRATA_GFX12_DEFAULTS` 等による HIP の既定動作はこの変数が制御するものではない（`engine/src/prefill/prefill.cpp:505-511`、`engine/src/prefill/prefill.cpp:3812-3867`）。

`docs/DETAILS.md:1182` は unset 時の対象を compute capability 12.0 とし、`=1` は any CUDA card と記す。一方、実装の既定判定には離散 cc 8.6/8.9 も含まれ、`=1` でも離散 GPU と link probe が必要である。cc 8.6 では先行する switch-point limit が設定されると link rule が飛ばされるため、実際に link rule が使われるとは限らない。serve の通常の default layout は SYCL build を除外するが、split の arm 呼び出しには SYCL 固有の guard がない。GPU 情報や probe がこの経路でどう設定されるかは当該条件のコードから一律に断定しない（`engine/include/strata/prefill/share_rules.hpp:94-99`、`engine/src/prefill/prefill.cpp:3812-3827`、`engine/src/prefill/prefill.cpp:3880-3895`、`engine/src/program/generate.cpp:11796-11825`）。

## 実行時の詳細

単一 GPU 経路は GPU/cache 情報と起動時 link probe を `Prefill::set_card_expert_share` に保存し、その後 `Prefill::arm_cpu_share` が既定 share を arm する際に link 規則を評価する（`engine/src/program/generate.cpp:23871-23877`、`engine/src/prefill/prefill.cpp:3581-3596`、`engine/src/prefill/prefill.cpp:3812-3830`）。規則は値を初回呼び出し時に cache する。link 情報が欠けている場合や対象 GPU でない場合は規則が適用されず、既定 share の標準値が残る（`engine/src/prefill/prefill.cpp:499-511`、`engine/include/strata/prefill/share_rules.hpp:85-99`）。

規則が上限を引き上げると、その範囲の prompt chunk は expert routing 後に staging され、GPU cache にない expert の一部を idle CPU pool が処理できる。limit を超える chunk は GPU にない expert を link 経由で stream する経路になる。これにより prompt の計算担当が変わり、回答が既定 share 無効時とわずかに異なる場合がある（`engine/include/strata/prefill/share_rules.hpp:38-46`、`engine/src/prefill/prefill.cpp:3831-3840`）。

## ログと測定値

規則が適用された単一 GPU では、stderr に `prefill: CPU share rule:` で始まる行が出て、probe bandwidth、resident 外 expert 数、stream floor、pool worker 数、決定した limit と expert 幅を示す。その後、既定 share 有効の行が出る。split では `prefill: CPU share rule on a layer split:` の行が出る。規則が不適用・無効値の場合、AUTO 値そのものを知らせる警告やエラーはなく、条件を満たさなければ link rule 行も出ない（`engine/src/prefill/prefill.cpp:3831-3840`、`engine/src/prefill/prefill.cpp:3880-3892`）。

## 根拠

- `engine/include/strata/prefill/share_rules.hpp:38-99`
- `engine/src/prefill/prefill.cpp:477-511`
- `engine/src/prefill/prefill.cpp:3581-3596`
- `engine/src/prefill/prefill.cpp:3812-3896`
- `engine/src/program/generate.cpp:11783-11827`
- `engine/src/program/generate.cpp:12295-12313`
- `engine/src/program/generate.cpp:23871-23877`
