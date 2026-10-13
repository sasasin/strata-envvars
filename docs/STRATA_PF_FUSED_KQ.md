# `STRATA_PF_FUSED_KQ`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP の fused int8 prompt expert 経路で、UD-Q4_K_XL などの K-quant 形式を fused native kernel の対象に加えます。対象は gate/up の `Q4_K` または `Q5_K` と、down の `Q5_1` または `Q8_0` の組み合わせです。通常の native fused 対象にこれらの型を加える opt-in であり、単独では fused 経路を有効にしません。

## 値と判定

値は文字列全体や数値として parse せず、環境変数の有無と先頭文字だけを調べます。

| 値 | `kq_on()` の判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | 有効 |
| その他（例: `0`, `true`, ` 1`） | 無効 |

大文字小文字や後続文字は判定に影響しません。`kq_on()` の結果は関数内の `static const bool` に保存されるため、最初に判定された後のプロセス内変更は反映されません。

## 有効になる条件

- `__HIPCC__` のコード経路でのみ、K-quant 型を `gu_covered()` / `d_covered()` に追加します。CUDA および非 HIP の SYCL 経路ではこの追加分岐がコンパイルされず、この変数による K-quant 対応追加はありません。
- `STRATA_PF_FUSED=1` が必要です。HIP の `requested()` は同変数が存在し、先頭文字が `1` の場合に fused native を要求します。未設定時に gfx12 で一部 IQ 型が既定有効になる場合もありますが、K-quant 型はその既定対象ではありません。
- `STRATA_PF_FUSED_NATIVE=0` は native fused を無効にします。
- 対応デバイス上で native kernel が利用可能である必要があります。HIP の `dev_info()` は gfx11 / gfx12 の WMMA 対応 arch と実カーネルの属性を確認します。ソースコメントと `docs/STRIX_HALO.md` は K-quant 対応を gfx11 向けとして説明しています。K-quant を gfx12 で使えるという個別の測定・説明は資料にありません。
- prompt 処理では、native 型の expert layout であること、対象 layer の gate/up と down の両形式がカバーされること、MMQ 計画に対象 layer が含まれること、`stream_all`、単一 GPU（`--peer-device` なし）などの条件も必要です。`STRATA_PF_FUSED_KQ=1` だけで常に fused kernel が選ばれるわけではなく、条件に合わない layer/chunk は既存の MMQ または FP16 経路を使います。

## 実行時の詳細

HIP の `kq_on()` は `STRATA_PF_FUSED_KQ` を初回に読みます。有効な場合、`gu_covered()` は `Q4_K` / `Q5_K` を、`d_covered()` は `Q5_1` / `Q8_0` を追加で許可します。これらはソースコメント上、Unsloth UD-Q4_K_XL の gate/up と down の各層にある形式です。native の組み合わせ判定 `native_supported()` は両側の形式、デバイス対応、`STRATA_PF_FUSED=1` の要求を確認します。

prompt 実行時は `fused_nat` が選ばれた layer で `quantize_act_native()` と `experts_native()` を使います。ソースコメントは fused 出力が FP16 expert 経路と丸めレベルで異なるとしています。`docs/STRIX_HALO.md` は K-quant pack に `STRATA_PF_FUSED_KQ=1` も必要と記載していますが、同資料の性能表は複数の設定をまとめた測定であり、この変数単独の性能差を切り分けていません。`docs/AMD_HIP.md` も K-quant pack は未測定としています。

この変数自体についての専用ログ出力は見当たりません。fused path に入る場合は、prefill 側で `strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)` が stderr に一度出ますが、このログは K-quant opt-in の有無を区別しません。

## 根拠

- `src/prefill/moe_fused_iq.cu:1067-1088`: KQ opt-in の判定、先頭文字 `1` の規則、HIP のみで K-quant 型を追加する条件。
- `src/prefill/moe_fused_iq.cu:1118-1139`: `STRATA_PF_FUSED`, `STRATA_PF_FUSED_NATIVE`, 対応形式および device 判定を組み合わせた native 対応判定。
- `src/prefill/moe_fused_iq.cu:1027-1049`: HIP device の gfx11/gfx12 arch と kernel 属性の確認。
- `sycl/src/prefill/moe_fused_iq.dp.cpp:1214-1235,1361-1366`: SYCL 移植側にも同じ読み取り箇所があるが、K-quant 型の追加は `__HIPCC__` 条件内であること。
- `src/prefill/moe_fused.cu:667-673`: native fused 経路で必要な `STRATA_PF_FUSED=1` の判定。
- `src/prefill/prefill.cpp:2952-2961,3028-3034`: prompt の layer 選択条件と native fused kernel の呼び出し。
- `docs/STRIX_HALO.md:119-125`: prompt chunk の適用条件および K-quant pack で本変数も必要との説明。
- `docs/AMD_HIP.md:361`: K-quant pack を `STRATA_PF_FUSED_KQ=1` で使う条件は未測定との記載。
