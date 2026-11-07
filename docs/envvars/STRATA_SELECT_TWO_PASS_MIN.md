# `STRATA_SELECT_TWO_PASS_MIN`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

CUDA の chunked prompt prefill で使う QSA two-pass block scorer の適用下限を、最後の query が持つ block 数で指定します。値は `STRATA_SELECT_TWO_PASS=1` で scorer が要求され、かつ対応する CUDA カード・選択経路などの条件を満たす場合にだけ効果があります。既定値は 4096 blocks（header のコメントでは 16,384 cells 相当）です。

two-pass scorer はまず各 block を single-pass TF32 で採点し、top-k cutoff の誤差境界にかかる block を 3xTF32 で再採点します。閾値はこの scorer を試す prompt 呼び出しの大きさだけを変えます。選択された cells の結果を変える設定ではありません（`src/prefill/prefill.cpp:4399-4412,4423-4436`; scorer の説明: `include/strata/kernels/qsa_two_pass.hpp:1-10`）。

## 値と判定

CUDA 実装は環境変数を `std::atoll` で変換し、変換後の負値を 0 にします。変換・範囲エラーの検査や上限 clamp はありません。

| 環境変数の状態・値 | 閾値 |
|---|---:|
| 未設定 | 4096 |
| 空文字、数字で始まらない文字列 | `atoll` が 0 を返すため 0 |
| 先頭の空白・符号の後に数値がある文字列 | 先頭の整数部分を変換。例: `"  +12tail"` は 12 |
| 負の数 | 変換後に 0 |
| 0 または負数以外の整数 | その整数 |

文字列全体の妥当性は検査されず、整数の後ろの文字は無視されます。したがって `12tail` は 12、`1.5` は 1 です。数値として解釈できない文字列は無効値としてエラーにならず、0 になります。`atoll` の表現範囲を超える入力はコードで検出・処理していないため、その結果はこの実装から保証できません。根拠: `src/kernels/cuda/qsa_select.cu:3800-3806`。

## 有効になる条件

- `STRATA_SELECT_TWO_PASS` が文字列全体で厳密に `1` であること。未設定、空文字、`true`、`01` などでは scorer は要求されません（`include/strata/kernels/qsa_two_pass_status.hpp:12-19`; CUDA での読み取り: `src/kernels/cuda/qsa_select.cu:3785-3791`）。この変数が未設定または無効なら、閾値に関係なく two-pass は使われません。
- CUDA prompt の chunked 選択経路であること。各 chunk の最後の query の `n_bid + 1` が閾値以上なら、その chunk の key 準備を試みます。さらに各 selection batch の `active` blocks も閾値以上である必要があります（`src/prefill/prefill.cpp:4404-4412,4414-4428`）。0 を指定するとこれらのサイズ条件は常に通りますが、ほかの scorer 条件を無効にはしません。
- scorer が当該 GPU と geometry で実行でき、scratch が足りること。CUDA scorer のサポート判定は sm_80 以上で、`STRATA_QSA_WARP=1` または `select` の経路では対象外です。two-pass 呼び出しは `STRATA_SELECT_OLD` が設定されている場合にも飛ばされます。失敗・非対応時は通常の tensor-core scorer、または fallback scorer に進みます（`src/kernels/cuda/qsa_select.cu:3764-3781,3810-3815,3823-3832`; `src/prefill/prefill.cpp:4422-4434`）。
- layer-major prompt path では two-pass scorer 自体が使われません。CUDA では `STRATA_SELECT_TWO_PASS=1` が設定されていると、その経路では未使用で選択結果は変わらない旨を一度 stderr に出します（`src/prefill/prefill.cpp:7969-7975`; 文言: `include/strata/kernels/qsa_two_pass_status.hpp:21-33`）。
- HIP の実装は `qsa_two_pass_min_blocks()` が環境を読まず常に 4096 を返します。また scorer は false を返すため、当変数は HIP では適用されません（`src/kernels/cuda/qsa_select.cu:3897-3907`）。Metal は呼び出し側の two-pass selection 部分が `STRATA_GPU_METAL` 条件で除かれています（`src/prefill/prefill.cpp:4397-4413,4423-4429`）。

CLI 引数や別の設定値がこの閾値を上書きする処理は見つかりませんでした。`STRATA_SELECT_TWO_PASS` は閾値と独立した必須スイッチであり、`STRATA_SELECT_OLD` は二段階 scorer の呼び出しを抑止します（`src/prefill/prefill.cpp:4404-4412,4422-4434`）。

## 実行時の詳細

CUDA の `qsa_two_pass_min_blocks()` は関数内の `static const int64_t` に値を保存します。初回呼び出し時に一度だけ読み、同プロセスで後から環境を変更しても再評価されません。呼び出し側も `Prefill::run` 内の static 値として閾値を保持します（`src/kernels/cuda/qsa_select.cu:3800-3806`; `src/prefill/prefill.cpp:4404-4412`）。

chunk 内の最後の query が閾値に達しない場合、`qsa_two_pass_keys` は呼ばれず、通常の scorer が使われます。達していても batch ごとの `active` が閾値未満ならその batch は two-pass になりません。two-pass の実行が始まると stderr に `qsa select: two-pass scores on ...` が一度出て、設定された閾値が表示されます。prompt の最後には実行時の call 数・再採点 block 数などの要約が、カウンターがあれば stderr に出ます（`src/prefill/prefill.cpp:4410-4434`; `src/kernels/cuda/qsa_select.cu:3841-3845`; `src/prefill/prefill.cpp:6398-6421`）。閾値による通常経路への切替自体に警告・エラーはありません。

CUDA kernel の起動エラーは `qsa two-pass keys: ...` または `qsa two-pass scores: ...` と stderr に出して `exit(1)` します。これは閾値の値判定ではなく、two-pass kernel 実行時の失敗経路です（`src/kernels/cuda/qsa_select.cu:3817-3820,3856-3861`）。

## 根拠

- 実読み取り、既定値、変換、負値 clamp、static cache: `src/kernels/cuda/qsa_select.cu:3800-3806`。
- 閾値の宣言と単位（blocks）、既定値: `include/strata/kernels/qsa_select.hpp:106-109`; `include/strata/kernels/qsa_two_pass.hpp:60-62`。
- 閾値を使う chunk / batch 判定と通常 scorer への fallback: `src/prefill/prefill.cpp:4397-4436`。
- CUDA device 条件と scorer の実行前提: `src/kernels/cuda/qsa_select.cu:3764-3781,3810-3832`。
- HIP stub: `src/kernels/cuda/qsa_select.cu:3897-3907`。
- 補足資料 `docs/DETAILS.md:1124-1134` は、two-pass が opt-in であること、閾値の既定値 4096、対象外経路を説明しています。閾値の値変換は資料に詳述されていないため、上記は実装を根拠としました。
