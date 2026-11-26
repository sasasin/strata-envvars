# `STRATA_SPEC_COUPLED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

MTP drafter が通常の argmax ではなく、対象モデルと同じ sampling chain と Philox draw を使って draft token を選ぶ機能を有効にします。CUDA/HIP 実装では生成時の出力 token は verifier のサンプルとの完全一致で決まり、coupled draft はウィンドウ内で受理される draft 数に関わります。対象モデルの sampling 設定そのものを変更するスイッチではありません。MTP を使わない実行では効果はありません。実装は `engine/include/strata/core/coupled_draft.hpp`、`engine/src/core/mtp.cpp` と、SYCL 版の `engine/sycl/include/strata/core/coupled_draft.hpp`、`engine/sycl/src/core/mtp.cpp` にあります（`engine/include/strata/core/coupled_draft.hpp:57-83`、`engine/src/core/mtp.cpp:1518-1531`、`engine/sycl/include/strata/core/coupled_draft.hpp:55-70`、`engine/sycl/src/core/mtp.cpp:1227-1237`）。

## 値と判定

`std::getenv` で取得し、未設定でないこと、空文字でないこと、文字列全体が正確に `"0"` ではないことを判定します。数値・真偽値としての parse はなく、大文字小文字や前後の空白も除去しません。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP (`engine/include/strata/core/coupled_draft.hpp:57-61`) | 無効 | `1`、`true`、`false`、`00`、`0anything`、空白だけの文字列 | 空文字、正確に `0` |
| SYCL (`engine/sycl/include/strata/core/coupled_draft.hpp:55-59`) | 無効 | `1`、`true`、`false`、`00`、`0anything`、空白だけの文字列 | 空文字、正確に `0` |

最初に `coupled_draft_state()` が呼ばれたときに関数内 `static` へ一度だけ読み込みます。その後の環境変更は反映されません。ただし `generate` の CLI parser は環境由来の初期値を `--coupled-draft` または `--no-coupled-draft` で上書きし、引数に現れた順で最後の指定が残ります。parse 後に `set_coupled_draft()` がその値を state に書き戻します（CUDA/HIP: `engine/src/program/generate.cpp:873,3838,3978-3979,4614`、SYCL: `engine/sycl/src/program/generate.cpp:551,1878,1996-1997,2231`）。

## 有効になる条件

- 実行経路がこの CUDA/HIP または SYCL `generate` engine で、MTP drafter が bind されること。MTP が指定・ロードされない場合、この変数だけでは drafting は始まりません（CUDA/HIP: `engine/src/program/generate.cpp:24507-24510`、SYCL: `engine/sycl/src/program/generate.cpp:13764-13767`）。
- bind 時に coupled 用の scratch サイズがサポートされる範囲であり、必要な device / mapped buffers の割り当てに成功すること。scratch が 0 の場合は coupled 用 setup を行わず argmax draft に戻ります（CUDA/HIP: `engine/src/core/mtp.cpp:802-808`、SYCL: `engine/sycl/src/core/mtp.cpp:678-685`）。
- request の sampling が greedy でなく、temperature が正であること。CUDA/HIP ではさらに `temperature >= STRATA_SPEC_MIN_TEMP` が必要です。SYCL の `set_draft_sampling` にはこの追加比較がありません（CUDA/HIP: `engine/src/core/mtp.cpp:855-860`、SYCL: `engine/sycl/src/core/mtp.cpp:737-742`）。条件を満たさない request は argmax draft のままです。
- CUDA/HIP では `STRATA_SPEC_PROB` が有効な場合も同じ coupled buffers の setup を要求します（`engine/include/strata/core/coupled_draft.hpp:65-79`、`engine/src/core/mtp.cpp:784-785`）。この別経路は `--no-coupled-draft` で coupled state を無効にしても独立して setup を要求します。SYCL の `coupled_draft_env()` は `STRATA_SPEC_PROB` を参照しません（`engine/sycl/include/strata/core/coupled_draft.hpp:63-65`）。

## 実行時の詳細

環境変数の state は最初の helper 呼び出しで初期化され、`Options` の初期値にも使われます。CLI 指定は parse 後に state を上書きします。MTP bind 時に機能が有効なら、draft logits の幅をもとに scratch と penalty history ring、SamplerParams 用領域などを確保し、coupled 用の状態 `coupled_ok_` を立てます。幅が大きすぎる場合は setup を省略し、失敗ではなく argmax draft に戻ります（CUDA/HIP: `engine/src/core/mtp.cpp:802-852`、SYCL: `engine/sycl/src/core/mtp.cpp:678-731`）。

sampling 条件を満たすたびに `set_draft_sampling()` が request の SamplerParams を保存し、penalty history を初期化します。CUDA/HIP の serve 経路は request sampling を作るたびに呼び出し、通常の generate 経路も sampling parameters を設定した後に呼び出します（`engine/src/program/generate.cpp:21418-21426,24538-24542`）。SYCL も同じ箇所で呼び出します（`engine/sycl/src/program/generate.cpp:11562-11578,13781-13784`）。coupled 状態では MTP draft logits から token を sampling し、penalty history と対象側の chain / Philox draw を使います（CUDA/HIP: `engine/src/core/mtp.cpp:1518-1531,1595-1605`、SYCL: `engine/sycl/src/core/mtp.cpp:1227-1237,1330-1340`）。

バッファ確保など coupled setup が失敗すると `bind()` が失敗を返します。通常の generate は `strata generate: <error>` を stderr に出して終了コード 1、serve は `print_start_refusal("strata serve", err)` を経由して起動を拒否します（CUDA/HIP: `engine/src/core/mtp.cpp:811-820`、`engine/src/program/generate.cpp:24507-24510`、`engine/src/program/generate.cpp:7884-7889`。SYCL: `engine/sycl/src/core/mtp.cpp:691-695`、`engine/sycl/src/program/generate.cpp:13764-13767`）。

## ログと測定値

coupled setup が成功すると stderr に次の行を出します（語句は実装どおり）。

- CUDA/HIP: `strata mtp: coupled draft sampling on (STRATA_SPEC_COUPLED): sampled requests draft with the target's chain and Philox draw over <語彙数> tokens`（`engine/src/core/mtp.cpp:850-851`）。
- SYCL: 同じ形式の行（`engine/sycl/src/core/mtp.cpp:729-730`）。
- draft logits が広すぎる場合は `strata mtp: STRATA_SPEC_COUPLED: <語彙数> draft logits are too wide for the coupled sampler; argmax drafts` を stderr に出します（CUDA/HIP: `engine/src/core/mtp.cpp:805-808`、SYCL: `engine/sycl/src/core/mtp.cpp:681-684`）。

`STRATA_SPEC_PROB` が有効な CUDA/HIP 経路では、代わりに `strata mtp: probabilistic draft acceptance on (STRATA_SPEC_PROB): ...` のログを出します（`engine/src/core/mtp.cpp:843-848`）。測定値は本書では扱いません。`docs/DETAILS.md` には複数設定を組み合わせた測定表がありますが、この環境変数単独の効果を分離した結果ではありません（`docs/DETAILS.md:1724-1725`）。

## 根拠

- 環境変数の読み取り・CLI override: `engine/include/strata/core/coupled_draft.hpp:57-83`、`engine/src/program/generate.cpp:873,3838,3978-3979,4614`、`engine/sycl/include/strata/core/coupled_draft.hpp:55-70`、`engine/sycl/src/program/generate.cpp:551,1878,1996-1997,2231`
- MTP bind、setup、fallback、sampling activation: `engine/src/core/mtp.cpp:802-860`、`engine/sycl/src/core/mtp.cpp:678-742`
- request sampling と draft 処理: `engine/src/program/generate.cpp:21418-21426,24507-24510`、`engine/src/core/mtp.cpp:1518-1531,1595-1605`、`engine/sycl/src/program/generate.cpp:11562-11578,13764-13784`、`engine/sycl/src/core/mtp.cpp:1227-1237,1330-1340`
- 関連する記載: `docs/SETTINGS.md:317`、`docs/DETAILS.md:625-628,1724-1725`
