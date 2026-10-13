# `STRATA_QFUSE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

verify window 内で使う q8_1 活性値を、後段の量子化 kernel で作らず、その活性値を生む kernel に作らせます。主な対象は GDN 出力 norm と hyper-connection（GR）read の出力です。生成値そのものを変える設定ではなく、既存の q8_1 量子化結果を producer 側で用意して後続 projection / expert の入力に使う経路を選びます。

実装は CUDA/HIP と SYCL の verifier にあり、通常の prefill 経路全体を切り替える設定ではありません。設定判定は `g_qfuse()` の関数内 `static const bool` に保持され、プロセス内の初回評価後に環境を書き換えても再評価されません（`src/core/verify.cpp:156`, `sycl/src/core/verify.cpp:76`）。

## 値と判定

`getenv()` が返す文字列を `atoi()` に渡し、変換結果が 0 以外なら ON です。文字列全体の検証ではありません。

| 値 | 判定 |
|---|---|
| 未設定、空文字、`0`、`false`、数字で始まらない文字列 | OFF |
| `1`、`2`、`-1`、`1junk`、先頭の空白の後に非ゼロ数字がある文字列 | ON |
| `0junk`、`0x1` | OFF（`atoi()` が読む先頭の数値部分が 0）|

`src/core/verify.cpp:156`, `sycl/src/core/verify.cpp:76`。

HIP の gfx1151 では、別の条件により起動時に未設定の `STRATA_QFUSE` を `1` にします。利用者が値を設定済みなら、空文字や `0` を含めその値を保持します。`STRATA_GFX1151_DEFAULTS=0` なら一括既定値設定を止めます。これは `STRATA_USE_HIP` のビルドに限られ、gfx1151 以外の AMD GPU と CUDA には適用されません。gfx12 (RDNA4) 用の既定値表には `STRATA_QFUSE` はありません（`src/program/generate.cpp:2190-2196`, `src/core/arch_defaults.cpp:32-59,61-70`）。

## 有効になる条件

- verifier が verify window を作って処理する経路で参照されます。`STRATA_QFUSE` が ON の場合、GDN layer では `gdn_step_norm_multi()` に q8_1 出力先を渡し、GDN 出力 norm と q8_1 store を同じ kernel 側で行います（`src/core/verify.cpp:1174-1180`, `src/kernels/cuda/verify_kernels.cu:467-497,993-1017`; SYCL 版: `sycl/src/kernels/cuda/verify_kernels.dp.cpp:734-786,1831-1834,1894-1938`）。
- GR read の出力 `mixed` にも q8_1 destination と group counter を渡します。CUDA/HIP 実装は融合 read kernel がこの image を書けた場合、GDN 入力 projection と MoE expert 用の通常 quantize 呼び出しを省略します（`src/core/verify.cpp:1053-1072,1116,1416,1543-1547`; `src/kernels/cuda/fused_gr.cu:1848-1864`）。GR 側の image 用 counter は verifier 準備時に確保・zero 初期化されます。確保に失敗した場合は pointer が null となり、GR read は q8_1 image を書かず、後段の通常量子化が残ります（`src/core/verify.cpp:789-795,1053-1072`）。
- batch recurrence (`batch_rec_`) では GDN recurrence に q8_1 出力先を渡しません。このケースは明示的に通常の `native_quantize_q8_1()` を実行します。GR read の融合出力とは別の例外です（`src/core/verify.cpp:1163-1180`）。
- QSA layer の出力側 q8_1 は引き続き通常の `native_quantize_q8_1()` で作ります（`src/core/verify.cpp:1395-1409`）。
- CUDA/HIP では別変数 `STRATA_QFUSE_HC` が hyper-connection read だけの image 書き込みを独立して有効化できます。counter は `STRATA_QFUSE` またはこの別設定のどちらかが有効なら確保されます。gfx12 の既定分岐は `STRATA_QFUSE_HC` 側にあり、`STRATA_QFUSE` の gfx1151 既定値とは別です（`src/core/verify.cpp:140-154,789-795`）。
- SYCL の GDN norm kernel は q8_1 image を書けますが、SYCL の fused GR read 実装は q8_1 image をサポートせず `false` を返し、呼び出し側が通常 quantize を実行します。したがって、この backend では GR read 側の融合効果はありません（`sycl/src/kernels/cuda/fused_gr.dp.cpp:1755,1882`; `sycl/src/core/verify.cpp:982-1003,1025,1063-1065,1286`）。

## 実行時の詳細

CUDA/HIP の GR read は、全 token 分の destination と token 0 の group counter が揃った場合にだけ q8_1 image 書き込みを有効にします。揃わない場合は destination を無効化し、呼び出し元が後段で量子化します。image が書かれた場合、GDN layer の attention-side入力では通常 quantize を飛ばし、FFN 側では CPU expert layout が native のときに MoE 用の通常 quantize を飛ばします。CPU expert layout が native でない場合は q8_0 用の別の変換経路が使われます（`src/kernels/cuda/fused_gr.cu:1848-1864`, `src/core/verify.cpp:1116,1521-1526,1543-1547`）。

`STRATA_QFUSE` が ON のときは one-token self-commit 経路も選ばれません（`src/core/verify.cpp:844`, `sycl/src/core/verify.cpp:824`）。QFUSE 専用のログは見つかりません。gfx1151 の自動既定値が環境に追加された場合は、arch defaults の集約ログに設定された switch 名が出ます（`src/core/arch_defaults.cpp:61-80`）。

## 文書との照合

`docs/STRIX_HALO.md:85-98` は gfx1151 の既定 switch 表に `STRATA_QFUSE` を挙げ、activation image を producer が書く機能として説明しています。現在の既定値コードでは gfx1151 表に `STRATA_QFUSE=1` があり、説明と一致します。同資料は maintainers の測定環境で各 switch が bitwise 同一だったと述べていますが、ここではその測定を独自に再実行していません。`docs/DETAILS.md` にはこの変数の追加説明を確認できませんでした。

## 根拠

- 値の読み取りと初回キャッシュ: `src/core/verify.cpp:156`, `sycl/src/core/verify.cpp:76`。
- verifier の counter、self-commit 抑止、GR read destination: `src/core/verify.cpp:789-795,844,1053-1072`。
- GDN と QSA の quantize 分岐、batch recurrence 例外: `src/core/verify.cpp:1163-1180,1395-1409`。
- FFN 入力 image と fallback: `src/core/verify.cpp:1416,1521-1526,1543-1547`; `src/kernels/cuda/fused_gr.cu:1848-1864`。
- CUDA GDN producer store: `src/kernels/cuda/verify_kernels.cu:467-497,993-1017`。
- SYCL GDN producer store と GR 未対応: `sycl/src/kernels/cuda/verify_kernels.dp.cpp:734-786,1894-1938`; `sycl/src/kernels/cuda/fused_gr.dp.cpp:1755,1882`。
- gfx1151 の起動時既定値と opt-out: `src/program/generate.cpp:2190-2196`; `src/core/arch_defaults.cpp:32-59,61-80`。
- 関連資料: `docs/STRIX_HALO.md:85-98`。
