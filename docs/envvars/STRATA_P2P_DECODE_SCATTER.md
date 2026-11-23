# `STRATA_P2P_DECODE_SCATTER`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

peer GPU が担当した decode expert の出力を、従来の pinned host row 経由ではなく、primary GPU の verifier が持つ `hit_out_` バッファへ P2P scatter する opt-in 変数です。`Verifier::set_plan_slot` が条件を満たすと `GpuPlanSink::hit_out_dev` に `hit_out_` の該当 token-group のアドレスを設定し、`expert_pool_dispatch_multi` が peer の出力先に選びます。通常の plan 経路では peer の担当 row も `P.dst` に登録され、GPU 側の hit 出力を既存の MoE 合成に渡します（`engine/src/core/verify.cpp:4339-4366`, `engine/src/core/expert_source.cpp:5681-5715`, `engine/src/core/verify.cpp:2921-2937`）。

## 値と判定

`Verifier::set_plan_slot` 内の関数ローカル `static const bool` が、初回評価時に `std::getenv` で値を読みます。値全体の parse や数値検査はなく、未設定・空文字・先頭 byte が `'0'` の値は無効、それ以外の非空値は有効です。従って `1`、`true`、`false`、` 0` は有効、`0`、`0anything`、`00`、空文字は無効です。大文字小文字・後続文字・空白を検査しません（`engine/src/core/verify.cpp:4360-4363`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| verifier の plan 設定 | 無効 | 空でなく先頭 byte が `0` 以外（例: `1`, `true`, `false`, ` 0`） | 空文字、先頭 byte が `0`（例: `0`, `0anything`, `00`） |

## 有効になる条件

- peer expert tier が存在し、その layer の routed expert を peer が保持している必要があります。peer tier は `--peer-device N` で構成されます（`engine/include/strata/core/peer_experts.hpp:31-33`, `engine/src/core/expert_source.cpp:5583-5592`）。
- primary と peer の双方で P2P access が有効である必要があります。デバイス間 access がない、安全でない topology、または P2P の検証失敗時は `p2p_` が false になり、この変数による device-side 出力先は選ばれません（`engine/src/core/peer_experts.cpp:208-236`）。
- `STRATA_PEER_DIRECT` が `0` に変換される場合は direct launch を使いません。この変数は未設定なら direct を有効にし、`std::atoi` が 0 を返す設定値では無効にします（`engine/src/core/peer_experts.cpp:315-317`）。
- verifier の `hit_out_`、session state (`ss_`)、model geometry (`g_`) が存在する場合にだけ出力先ポインタを設定します（`engine/src/core/verify.cpp:4364-4366`）。
- `device_hits_only` の plan では pool が host-side の行リストを作らず、peer row の追加処理も実行しません。device-side hit plan は primary の residency table から作られます。この経路は `STRATA_VERIFY_DEVICE_HITS` が非ゼロで、`--pcie-frac 0` により PCIe share が無効な場合などに有効になります。peer 指定時は起動処理の自動 `pcie_frac=0` 条件から除外されるため、必要なら CLI で明示します。この経路で `hit_out_dev` に scatter された peer row が合成対象へどう組み込まれるかは、該当する plan/list 処理からは確認できないため、同経路での有効性は断定できません（`engine/src/core/verify.cpp:4355`, `engine/src/core/expert_source.cpp:5681-5695`, `engine/src/core/verify.cpp:2691-2694`, `engine/include/strata/core/verify.hpp:439-442`, `engine/src/core/verify.cpp:1414-1428`, `engine/src/program/generate.cpp:5553-5559`）。
- Metal verifier は別の Metal window 実装へ handoff し、peer P2P 経路の対象ではありません（`engine/src/core/verify.cpp:99-115`, `engine/src/core/verify.cpp:5264-5269`）。

## 実行時の詳細

値はプロセス起動時に必ず読むのではなく、`set_plan_slot` が最初に呼ばれた時点で一度だけ読み、関数ローカル `static` に保持します。その後の環境変更は反映されません。`set_plan_slot` は通常の verifier window、batch、pipelined 経路から呼ばれます（`engine/src/core/verify.cpp:4360-4366`, `engine/src/core/verify.cpp:4075-4083`, `engine/src/core/verify.cpp:5471-5478`, `engine/src/core/verify.cpp:5694-5700`, `engine/src/core/verify.cpp:6066-6075`）。

この値が有効で P2P/direct の条件も満たすと、dispatch が `hit_out_dev` を peer launch に渡します。peer は担当 entry の native expert 出力を計算し、`scatter_rows_f32` でその row index に従って出力先へ書きます。direct 経路では `finish` は device-to-host copy や host memcpy をせずに完了扱いにします（`engine/src/core/expert_source.cpp:5705-5715`, `engine/src/core/peer_experts.cpp:385-393`, `engine/src/core/peer_experts.cpp:396-413`）。通常 plan 経路では `kind == 2` の row を計画へ追加し、primary 側で mapped CPU rows と hit 出力を合成します（`engine/src/core/expert_source.cpp:5681-5695`, `engine/src/core/verify.cpp:2921-2937`）。

変数が無効、P2P が使えない、または `STRATA_PEER_DIRECT=0` の場合、dispatch は通常の `out` row buffer を peer に渡します。peer direct mode が有効なら peer kernel が mapped host rows に scatter し、無効なら peer GPU の `h_out_` から device-to-host copy 後に `finish` が host row へ memcpy します（`engine/src/core/expert_source.cpp:5705-5715`, `engine/src/core/peer_experts.cpp:363-393`, `engine/src/core/peer_experts.cpp:396-413`）。

## ログと測定値

この変数自体を有効・無効にしたことを示す専用ログはありません。peer GPU 初期化時に P2P が選べない場合は、条件に応じて `strata: peer GPU ... using portable host-pinned staging instead of P2P ...` または `strata: peer GPU ... the prompt path takes the host route instead ...` が stderr に出ます（`engine/src/core/peer_experts.cpp:214-234`）。peer launch / scatter が失敗した場合は dispatch が `strata: <error> (layer <n>)` を stderr に出し、dispatch を失敗状態にします（`engine/src/core/peer_experts.cpp:385-393`, `engine/src/core/expert_source.cpp:5710-5715`）。

`docs/NVIDIA_V100.md:85` は dual Tesla V100-SXM2-16GB、NVLink NV6、指定モデル・量子化・CLI 引数等を含む測定構成の一つとして `STRATA_P2P_DECODE_SCATTER=1` を記載しますが、同資料の表はこの変数だけの比較ではありません。この値の単独効果や一般的な性能差は資料からは判断できません。

## 根拠

- 値の読み取り、判定、buffer address 設定: `engine/src/core/verify.cpp:4358-4366`
- peer と P2P の初期化条件: `engine/src/core/peer_experts.cpp:192-236`; peer direct mode: `engine/src/core/peer_experts.cpp:315-317`
- peer row の計画追加と出力先選択: `engine/src/core/expert_source.cpp:5681-5715`
- peer scatter / host fallback / finish: `engine/src/core/peer_experts.cpp:363-413`
- hit 出力と CPU row の合成: `engine/src/core/verify.cpp:2921-2937`
- device hit plan の適用条件: `engine/include/strata/core/verify.hpp:439-442`; environment / CLI 条件: `engine/src/core/verify.cpp:1414-1428`, `engine/src/program/generate.cpp:5553-5559`; plan 経路: `engine/src/core/verify.cpp:2691-2694`, `engine/src/core/expert_source.cpp:5681-5695`
- Metal handoff: `engine/src/core/verify.cpp:99-115`, `engine/src/core/verify.cpp:5264-5269`
- 測定構成: `docs/NVIDIA_V100.md:83-93`
