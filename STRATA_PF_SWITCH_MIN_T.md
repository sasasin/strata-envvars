# `STRATA_PF_SWITCH_MIN_T`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

prompt の chunk token 数 `T` が指定した下限以上のときだけ、ほかの環境変数で opt-in した一部の prompt 経路を使うための共通しきい値です。この変数自体は経路を有効にしません。主な対象は hyper-connection の upmix／padded projection、HIP の FP16 GEMM と weight padding、HIP prompt attention の fast WMMA variant です。通常の既定値は `0` なので、別の opt-in と経路条件を満たす場合、token 数による追加制限はありません。

## 値と判定

読み取りは各箇所の `std::atoll()` です。unset は `0`、空文字や数値に変換できない文字列も `0` になります。符号と先頭空白を含む数値接頭部を読み、後続の非数値文字は変換結果に含めません（例: `4096junk` は `4096`、`-1` は `-1`）。全体一致やエラー報告はありません。読み取り値と `T` を比較する箇所では `T >= 値` が条件です。padding 関連の箇所はさらに `max(値, 64)` をしきい値にします。

値は参照箇所ごとの function-local `static` に保存されます。その箇所で初めて評価された後にプロセス環境を変えても反映されません。別々の読み取り箇所はそれぞれ初回評価時に値を取得します。

## 有効になる条件

- **Hyper-connection upmix:** `STRATA_HC_UPMIX` の先頭文字が `1` で、`T >= STRATA_PF_SWITCH_MIN_T`、通常の fused hyper-connection 経路であり、低精度分割や重み形式などの追加条件を満たす場合に `gr_upmix` を試します。条件を満たさない場合は通常の射影と mix を使います（`src/prefill/prefill.cpp:323-325,2593-2619`）。
- **Hyper-connection padded stride:** `STRATA_PF_HCDOWN` または `STRATA_HCD_EXACT` が有効で、`T >= max(しきい値, 64)`、fused 経路で、低精度 remainder がない場合に hyper-connection activation の stride を `D + 64` にします。実際の特別な down projection は環境変数、重み形式および kernel 条件にも依存します（`src/prefill/prefill.cpp:330-345,2570-2590`）。
- **GDN／QSA の activation padding:** `STRATA_PF_PAD=1` と `STRATA_PF_GEMM=1` の両方が必要です。`T >= max(しきい値, 64)` なら GDN recurrence 出力または QSA attention 出力の row stride を `ZV + 64` にします。これは対応する GEMM 経路で使われます（`src/prefill/prefill.cpp:2648-2652,2864-2882`）。
- **HIP FP16 GEMM:** `STRATA_PF_GEMM` の先頭文字が `1` で `T >= しきい値` の場合、HIP build の `Gemm::f16` は `strata_pf_gemm_f16` を試します。関数が成功すればその結果を使い、そうでなければ後続の通常経路へ進みます（`src/prefill/gemm.cu:675-700`）。
- **HIP quantized-weight padding:** `STRATA_PF_PAD=1` と `STRATA_PF_GEMM=1`、`T >= しきい値` に加え、`T >= 64`、`N >= 512`、`K` が32の倍数、scratch 容量内という条件が必要です。条件内で重みを `K + 64` stride に展開して専用 GEMM を試し、成功すれば終了します（`src/prefill/gemm.cu:819-835`）。
- **HIP prompt attention:** `STRATA_PA_FAST=1` の場合、HIP WMMA prompt-attention 経路で `n_q >= しきい値` の chunk は `<false>` kernel、未満なら `<true>` kernel を選びます。この経路自体にも QSA shape／KV 条件と `STRATA_HIP_WMMA=1`、対応 GPU 世代（RDNA 3／4）の条件があります。使えない場合は呼び出し元が通常の attention 経路へ fallback します（`src/kernels/cuda/qsa_prompt_attn.cu:1400-1448,1483-1491`; `src/prefill/prefill.cpp:2864-2876`）。

## 実行時の詳細

このしきい値は prompt の各 chunk の `T` と比較されます。全 prompt の長さではありません。`T` 未満のときはこの値で gate される経路を選ばず、呼び出し元の後続経路に進みます。後続経路は別の環境変数や backend により異なり、必ずしも汎用の既定 kernel とは限りません。`STRATA_PF_FUSED` が選ぶ expert 経路にはこの変数による token 下限はかかりません。

`docs/STRIX_HALO.md` は fast 設定例として `STRATA_PF_SWITCH_MIN_T=4096` を示し、短い prompt を既定数値経路に保つ設定として説明しています（同ファイル 100-125 行）。同ファイル 124 行は expert の fused 経路にはこのしきい値がかからず、HC と padding を gate すると説明しています。一方、現行ソースには上記の HIP GEMM と HIP prompt-attention variant に対する追加の読み取りもあります。`docs/AMD_HIP.md` にも HIP の測定例の設定値として `4096` が記載されています（238-239 行）。いずれも使用例・特定条件の測定記録であり、4096 がコード上の既定値という意味ではありません。

## 根拠

- 共通の読み取り、未設定時 `0`、hyper-connection 用判定: `src/prefill/prefill.cpp:318-345`。
- hyper-connection の stride と upmix 適用条件: `src/prefill/prefill.cpp:2570-2590,2593-2619`。
- GDN／QSA padded activation stride: `src/prefill/prefill.cpp:2648-2652,2864-2882`。
- HIP GEMM と quantized weight padding のしきい値および追加条件: `src/prefill/gemm.cu:675-700,819-835`。
- HIP prompt-attention の fast variant 判定と適用経路: `src/kernels/cuda/qsa_prompt_attn.cu:1400-1448,1483-1491`。
- SYCL prefill 側にも helper と hyper-connection／activation-padding 判定があります: `sycl/src/prefill/prefill.cpp:252-281,2813-2836,2905-2909,3194-3196`。
- 設定例・適用範囲の説明: `docs/STRIX_HALO.md:100-125`, `docs/AMD_HIP.md:238-239`。
