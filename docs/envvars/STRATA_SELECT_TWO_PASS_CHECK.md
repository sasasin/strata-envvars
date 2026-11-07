# `STRATA_SELECT_TWO_PASS_CHECK`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の chunk-major prompt selection で、`STRATA_SELECT_TWO_PASS=1` による two-pass QSA scorer が実際に使われた query について、得られた scores と top-k ids を通常の 3xTF32 scorer で再計算した結果と比較する診断スイッチです。two-pass scorer の有効化スイッチではありません。比較は prompt の本来の選択結果を書き換えず、統計を蓄積します（`src/prefill/prefill.cpp:4404-4412,4435-4480`）。

## 値と判定

CUDA 実装は `std::getenv()` の値が存在し、かつ文字列全体がちょうど ASCII の `1` である場合だけ有効とします。数値変換や前後空白の除去はしません（`src/kernels/cuda/qsa_select.cu:3793-3799`）。

| 環境値 | 判定 |
| --- | --- |
| 未設定 | 無効 |
| 空文字 | 無効 |
| `1` | 有効要求 |
| `01`, `10`, `1x`, `true`, ` 1`, `1 ` など | 無効 |

有効要求でも、実際の比較は two-pass selection が採用された呼び出しだけです。`STRATA_SELECT_TWO_PASS` が無効なら短絡評価により check の getter は呼ばれず、この変数単独では処理を有効にしません（`src/prefill/prefill.cpp:4404-4406,4422-4428`）。CLI 引数による上書きはこの経路にありません。

## 有効になる条件

- CUDA 向けの非 Metal の chunk-major prompt 実装であること。HIP 用の `qsa_two_pass_check_on()` は常に `false` を返します。Metal の該当コードもコンパイル対象から除かれます（`src/kernels/cuda/qsa_select.cu:3793-3799,3897-3910`; `src/prefill/prefill.cpp:4398-4406,4437-4442`）。SYCL はこの `qsa_select.cu` の実装経路ではありません。
- `STRATA_SELECT_TWO_PASS` が有効で、two-pass scorer が実行可能な CUDA device であること。実装上の適用範囲は tensor-core scorer が動く sm_80 以上で、`STRATA_QSA_WARP` が warp scorer を選ぶ場合は対象外です（`include/strata/kernels/qsa_select.hpp:97-108`; `src/kernels/cuda/qsa_select.cu:3762-3781,3785-3791`）。
- chunk-major の selection であること。layer-major prompt path は two-pass selection の対象外です（`src/prefill/prefill.cpp:7970-7975`; `include/strata/kernels/qsa_two_pass_status.hpp:2-6`）。
- 対象 chunk のキー scratch が準備でき、最後の query の block 数が `STRATA_SELECT_TWO_PASS_MIN`（既定 4096 blocks）以上であること。さらに各 query batch で `old_sel` が無効で、two-pass の scores 呼び出しが成功した場合だけ比較します。形状、capacity、scratch の条件でも scorer が不採用になり得ます（`src/prefill/prefill.cpp:4407-4412,4422-4428`; `include/strata/kernels/qsa_two_pass.hpp:60-62,97-105`）。

`STRATA_SELECT_TWO_PASS_CHECK` 自体が無効にする scorer や選択 fallback はありません。条件を満たさない場合、従来の scorer selection が続き、check の比較も行われません。ソースの check 呼び出し箇所には「one GPU」とコメントがありますが、この箇所にこの環境変数のための device-count 分岐はありません（`src/prefill/prefill.cpp:4438-4442`）。

## 実行時の詳細

prefill の selection ループに入った時、`tp_on` と `tp_check` は関数内 `static const bool` として評価されます。`tp_check` は `tp_on` が true の場合に限り `qsa_two_pass_check_on()` を呼びます。getter 側も `static const bool` に値を保存するため、最初に評価された後のプロセス内環境変更は反映されません（`src/prefill/prefill.cpp:4404-4406`; `src/kernels/cuda/qsa_select.cu:3793-3799`）。

各 query batch では two-pass scores と通常の `qsa_block_topk` の後に、3xTF32 scorer をもう一度実行して reference scores と ids を作り、check kernel が差分を数えます。診断は selection の結果を差し替えません。prompt 完了時には `strata prefill: two-pass check: ...` の stderr 行に、比較した query 数、id が異なる query と id の数、再計算した block のうち score が bitwise で異なる数、bound 外だった kept score の数、最大比率を出します。この行は two-pass の統計取得が成功し、prompt 中に two-pass calls があった場合だけ出ます（`src/prefill/prefill.cpp:4473-4480,6398-6421`）。

観測可能な失敗経路は次のとおりです。

- check 用の共有領域が 48 KiB を超える block 数の場合、初回に `qsa two-pass check: %lld blocks are too many to check` を stderr に出して、その check 呼び出しをスキップします（`src/kernels/cuda/qsa_select.cu:3864-3873`）。
- 共有領域が足りない場合に専用 buffers を確保できなければ、prefill は `STRATA_SELECT_TWO_PASS_CHECK: no room for its buffers` をエラー文字列にして失敗します。通常 scorer を実行できない場合は `STRATA_SELECT_TWO_PASS_CHECK: the tensor-core scorer did not run` で失敗します（`src/prefill/prefill.cpp:4451-4477`）。
- check kernel の起動エラーは `qsa two-pass check: <CUDA error>` を stderr に出して `std::exit(1)` します（`src/kernels/cuda/qsa_select.cu:3874-3883`）。

## 根拠

- 値の読取とキャッシュ、HIP stub: `src/kernels/cuda/qsa_select.cu:3793-3799,3897-3910`。
- two-pass scorer と check の呼出条件、比較処理: `src/prefill/prefill.cpp:4398-4480`。
- 集計と stderr 出力: `src/prefill/prefill.cpp:6398-6422`。
- 診断 kernel と失敗時のログ・終了: `src/kernels/cuda/qsa_select.cu:3686-3760,3864-3895`。
- 関連する two-pass scorer の条件と閾値: `include/strata/kernels/qsa_select.hpp:97-108`, `include/strata/kernels/qsa_two_pass.hpp:60-62`, `include/strata/kernels/qsa_two_pass_status.hpp:12-34`。
