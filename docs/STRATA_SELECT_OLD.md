# `STRATA_SELECT_OLD`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリ、生成済みコード、テスト専用コードは挙動の根拠に含めていない。

## 役割

QSA の batched prompt prefill で、各 query の block score を計算するカーネルを選びます。設定されていると、`qsa_block_scores_tc()` による Tensor Core / 対応する別 scorer の試行を飛ばし、warp scorer の `qsa_block_scores()` を呼びます。設定されていない場合は別 scorer を試し、その関数が `false` を返したとき warp scorer に fallback します。Top-k による cell 選択はどちらの場合もその後に実行されます。

## 値と判定

値の parse はせず、`std::getenv("STRATA_SELECT_OLD") != nullptr` だけを見ます。

| 環境変数 | 判定 | 動作 |
|---|---|---|
| 未設定 | false | `qsa_block_scores_tc()` を試す。利用できなければ warp scorer に fallback |
| 設定あり | true | `qsa_block_scores_tc()` を呼ばず warp scorer を使う |

空文字、`0`、`false` なども「設定あり」です。文字列の内容、大文字小文字、数値としての妥当性は確認しません。値に応じた警告や専用ログはこの分岐にはありません。

判定結果は `prefill.cpp` 内の関数ローカル `static const bool` に保存されます。最初にこの選択処理へ到達した後、プロセス内で環境変数を変更しても再評価されません。

## 有効になる条件

- 実行経路が QSA を含む prompt prefill で、複数 query の block score を計算する箇所に到達する場合に参照されます。通常の decode、QSA 以外のモデル経路、この score 選択を通らない経路には影響しません。
- CUDA では、unset 時に `qsa_block_scores_tc()` が利用できる GPU・形状なら、その scorer が使われます。CUDA sm_80 以上では TF32 Tensor Core scorer を試し、sm_80 未満では `STRATA_SELECT_SIMT=1` が有効な場合に限り tiled FP32 scorer を試します。sm_80 未満でその条件を満たさない場合や、geometry/device 判定などで別 scorer が使えない場合は warp scorer になります。`STRATA_SELECT_OLD` を設定するとこれらの試行を抑止します。
- HIP では、unset 時に `STRATA_SELECT_WMMA` と gfx12 device 条件を満たせば WMMA scorer を試し、それ以外は warp scorer に fallback します。`STRATA_SELECT_OLD` の設定は WMMA の試行を抑止します。
- SYCL の prefill 呼び出し側にも同じ環境変数判定と scorer 呼び出し条件があります。ただし scorer の DPCT 生成実装はこの調査の根拠対象外としたため、SYCL で unset 時に別 scorer が実際に使われるかはここでは断定しません。

## 実行時の詳細

QSA prefill は indexer の batch append 後、selection batch ごとに `old_sel || !qsa_block_scores_tc(...)` を評価します。左辺が true なら短絡評価により `qsa_block_scores_tc()` 自体を呼びません。右辺を呼んで `false` なら warp scorer に進み、`true` なら追加の scorer 呼び出しをせず `qsa_block_topk()` に進みます。

ソースの API コメントでは Tensor Core scorer は FP32-level accuracy だが和の順序が異なり bitwise ではないと説明されています。したがって、この変数が scorer を切り替えることは確認できますが、選択結果や後続出力が常に同一であるとは断定できません。文書・資料から `STRATA_SELECT_OLD` 固有の測定値は確認できませんでした。

## 根拠

- `src/prefill/prefill.cpp:2760-2775` — CUDA/HIP prefill の batch score 選択、環境変数の有無判定、warp fallback、後続 top-k。
- `sycl/src/prefill/prefill.cpp:3018-3032` — SYCL prefill 側の同じ呼び出し側分岐。
- `src/kernels/cuda/qsa_select.cu:1118-1173` — CUDA/HIP での別 scorer の条件と利用不可時の `false` fallback。sm 条件、`STRATA_SELECT_SIMT`、`STRATA_SELECT_WMMA` を確認。
- `include/strata/kernels/qsa_select.hpp:32-37` — scorer の精度・和の順序に関する API 説明。
- `docs/OLDER_GPUS.md:111-122` — `STRATA_SELECT_SIMT` の pre-sm_80 条件に関する説明。`STRATA_SELECT_OLD` 自体の説明や測定は見つかりませんでした。
