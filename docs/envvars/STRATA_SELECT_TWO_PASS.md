# `STRATA_SELECT_TWO_PASS`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の対応 GPU で、プロンプト処理中の QSA block score の選択計算を二段階にします。全 block を single-pass TF32 で採点し、top-k の境界にかかる block だけを通常の 3xTF32 で再採点することで、`qsa_block_topk` が選ぶ cell を通常の tensor-core scorer と揃える実装です。これは opt-in で、未設定時は無効です。選択スコア計算の入口は chunk-major の CUDA prefill であり、layer-major prefill では使われません（`src/prefill/prefill.cpp:4398-4412,4422-4436,7970-7975`、`include/strata/kernels/qsa_two_pass.hpp:5-11`）。

候補名の全参照を検索したところ、本番コードでの読み取りは CUDA/HIP の scorer、CUDA の layer-major 判定、Metal と SYCL の未対応警告経路にありました。テスト用 parity program にも値をセットする参照がありますが、本番動作の根拠にはしていません（`src/kernels/cuda/qsa_select.cu:3785-3786,3897-3900`、`src/prefill/prefill.cpp:7925-7931,7970-7975`、`sycl/src/prefill/prefill.cpp:5199-5202`、テスト参照: `src/kernels/qsa_two_pass_parity.cpp:195-197`）。

## 値と判定

共通判定は文字列全体が厳密に `"1"` の場合だけ有効です。数値変換や trim、大文字小文字変換はありません（`include/strata/kernels/qsa_two_pass_status.hpp:12-18`）。

| 環境変数の状態 | 要求判定 |
| --- | --- |
| 未設定 | 無効 |
| 空文字 | 無効 |
| `1` | 有効要求 |
| `0`、`true`、`01`、`1x`、空白を含む文字列など | 無効 |

CUDA/HIP scorer、Metal、SYCL、layer-major の各読み取りは関数内 `static` の `RequestStatus` に保持され、最初の該当呼び出しで一度だけ環境値を読みます。実行中に環境値を変更しても再評価されません（`src/kernels/cuda/qsa_select.cu:3785-3786,3898-3900`、`src/prefill/prefill.cpp:7930,7972`、`sycl/src/prefill/prefill.cpp:5200`）。

二段階処理を始める block 数のしきい値は別変数 `STRATA_SELECT_TWO_PASS_MIN` で、CUDA 側で一度だけ `atoll` します。未設定なら 4096、設定値は負数を 0 に clamp します。したがって空文字や数字で始まらない文字列は `atoll` により 0、数値の後ろに文字があっても数値の prefix が使われます。0 はしきい値をなくし、全呼び出しを対象にします（`src/kernels/cuda/qsa_select.cu:3800-3806`、既定値: `include/strata/kernels/qsa_two_pass.hpp:60-62`）。

## 有効になる条件

有効要求が実際の二段階 scorer を使うには、次の条件が必要です。

- CUDA backend で、現在の GPU が compute capability 8.0 以上であること。`STRATA_QSA_WARP` が厳密に `1` または `select` の場合も scorer は使えません。GPU ごとの可否判定は cache されます（`src/kernels/cuda/qsa_select.cu:3762-3781`）。
- chunk-major prefill の block selection であること。layer-major prefill は選択結果を通常経路で計算し、要求があれば非対応理由を一度出します（`src/prefill/prefill.cpp:4422-4436,7970-7975`）。
- `STRATA_SELECT_OLD` が設定されていないこと。設定の有無だけで旧 selector を選び、二段階 scorer を呼びません（`src/prefill/prefill.cpp:4422-4434`）。
- batch の最後の query の block 数が `STRATA_SELECT_TWO_PASS_MIN` 以上であること。さらに各 batch の active block 数、QSA shape、query 数（`nq <= nq_cap <= 4096`）、scratch 容量・alignment など scorer の制約を満たす必要があります（`src/prefill/prefill.cpp:4407-4412,4414-4429`、`src/kernels/cuda/qsa_select.cu:3810-3815,3823-3832`）。

この変数自体を上書きする CLI 引数は実装にありません。CLI や設定が prefill の経路を layer-major にした場合は、その経路で二段階 scorer が使われないという適用範囲の違いがあります。`STRATA_QSA_WARP`、`STRATA_SELECT_OLD` は別々の選択条件で、`STRATA_SELECT_TWO_PASS_MIN` は実行対象のしきい値です（`src/prefill/prefill.cpp:4422-4436,7953-7975`、`src/kernels/cuda/qsa_select.cu:3771-3778`）。

未設定または無効値には何も要求されず、通常の scorer が使われます。二段階 scorer が要求されても上記条件や scratch 条件を満たさない場合は `qsa_block_scores_two_pass` が false を返し、呼び出し元が tensor-core scorer、さらに必要なら通常の block scorer に進みます（`src/prefill/prefill.cpp:4422-4436`）。CUDA 以外では選択処理は変更されません。

## 実行時の詳細

CUDA の有効要求は `qsa_two_pass_on()` が保持します。対応外 GPU では要求状態の `RequestStatus::on()` が警告しますが、`qsa_two_pass_on()` 自体は要求を true として返します。実際の keys/scores 関数が GPU 可否を再確認して false を返すため、呼び出し元は通常 scorer に fallback します（`src/kernels/cuda/qsa_select.cu:3785-3791,3810-3815,3823-3829`）。

HIP、Metal、SYCL では二段階 scorer を実行しません。要求値が厳密な `1` なら、それぞれ HIP scorer、Metal prefill、SYCL prefill の入口で stderr に一度、`strata: STRATA_SELECT_TWO_PASS=1 is not used on <backend>: ...` の形式の行を出し、選択は変更しません（`src/kernels/cuda/qsa_select.cu:3897-3907`、`include/strata/kernels/qsa_two_pass_status.hpp:21-34`、`src/prefill/prefill.cpp:7929-7931`、`sycl/src/prefill/prefill.cpp:5199-5202`）。CUDA の layer-major 経路も同じ request-status helper で理由を一度表示します。

CUDA chunk-major prefill で二段階 scores が初めて実行されると、stderr に `qsa select: two-pass scores on ...` の案内を一度出します。prompt 完了後には実行された call/query/block の統計を `strata prefill: two-pass QSA select: ...` として出します。統計取得に成功し、`STRATA_SELECT_TWO_PASS_CHECK=1` も有効なら、通常 scorer との id 差や bound の診断行も出します（`src/kernels/cuda/qsa_select.cu:3841-3845`、`src/prefill/prefill.cpp:6398-6421`）。

CUDA kernel 起動エラーは `qsa two-pass keys: ...` または `qsa two-pass scores: ...` を stderr に出して `exit(1)` します。check 用 kernel の起動エラーも `qsa two-pass check: ...` と `exit(1)` です。診断用バッファ確保に失敗した場合は prefill が false を返し、`STRATA_SELECT_TWO_PASS_CHECK: no room for its buffers` をエラー文字列にします。通常 tensor-core scorer が使えない場合の check は `STRATA_SELECT_TWO_PASS_CHECK: the tensor-core scorer did not run` で失敗します（`src/kernels/cuda/qsa_select.cu:3817-3820,3859-3861,3881-3883`、`src/prefill/prefill.cpp:4455-4476`）。

## 根拠

- 共通の厳密な `"1"` 判定、要求保持、非対応時の一度限りの警告: `include/strata/kernels/qsa_two_pass_status.hpp:12-39`。
- CUDA の GPU 条件、環境値の読み取り、最小 block 数、未対応 backend 実装: `src/kernels/cuda/qsa_select.cu:3762-3808,3810-3861,3897-3910`。
- prompt 選択経路、旧 selector と min block の併用、通常 scorer fallback、診断失敗: `src/prefill/prefill.cpp:4397-4481`。
- Metal / SYCL / HIP と layer-major の警告入口: `src/prefill/prefill.cpp:7925-7931,7970-7975`、`sycl/src/prefill/prefill.cpp:5199-5202`。
- Strata の説明資料も opt-in、sm_80+、min 既定 4096、未対応経路での警告を記載しています。性能値はこの文書では再検証していません（`docs/DETAILS.md:1124-1134`）。
