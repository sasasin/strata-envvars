# `STRATA_HCD_EXACT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

HIP prefill の hyper-connection read にある down projection（形状 N=320、K=10240）を、通常の GEMM から専用 WMMA kernel `strata_pf_hcdown_exact_bf16` に切り替える opt-in です。この kernel を選ぶのは、hipBLASLt の tuning table が同じ入力で solution 1176 または 1177 を選ぶ場合だけです。対象は down projection のみで、up projection と inject projection はこの分岐では切り替わりません。呼び出しと fallback は `engine/src/prefill/prefill.cpp:5111-5124`、solution 判定と kernel 呼び出しは `engine/src/prefill/gemm.cu:1025-1049` にあります。

## 値と判定

HIP/CUDA 共通 prefill と SYCL prefill のそれぞれで、`hcd_exact()` の初回呼び出し時に `std::getenv` を static local に保存し、値が存在し、かつ先頭文字が `'1'` の場合だけ true とします。文字列全体の比較や数値変換はしません。空文字、`0`、`true`、` 1` は無効で、`1`、`1anything`、`10` は有効です。大文字小文字や後続文字は判定されません。unset と空文字はいずれも false です（`engine/src/prefill/prefill.cpp:1012-1015`、SYCL 版 `engine/sycl/src/prefill/prefill.cpp:395-398`）。

| 条件（build / GPU） | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP build、gfx1151 の arch defaults が適用される | startup で既定値 `1` が設定される（`STRATA_GFX1151_DEFAULTS=0` なら既定値適用なし） | 先頭が `1` | 空文字、`0` など。値がすでに設定されていると arch default は上書きしない |
| HIP build、その他の arch | false | 先頭が `1` | 空文字、`0` など |
| CUDA / SYCL build | false | helper のフラグは true になるが、HIPBLASLt 対応 kernel 実装は呼べず通常 GEMM に戻る | 空文字、`0` など |

gfx1151 の既定値は `arch_default_env()` が `STRATA_HCD_EXACT=1` を候補に含め、`apply_arch_defaults()` が未設定の場合だけ設定します。ユーザーが空文字や `0` を明示してもそれを保持します。gfx12 は既定値のリストから明示的に除外されています（`engine/src/core/arch_defaults.cpp:28-66,67-77,218-223,302-310`）。エンジン起動側では HIP build に限り、GPU 情報取得後、switch の初回読み取りより前にこの適用を行います（`engine/src/program/generate.cpp:4287-4320`）。

## 有効になる条件

- exact kernel を実行するには HIP compiler build と `STRATA_HIPBLASLT_AVAILABLE` が必要です。これらの条件は `Gemm::bf16_hcd_exact()` のコンパイル分岐にあります。非 HIP build では同関数は常に false を返します（`engine/src/prefill/gemm.cu:1025-1049`）。
- prefill chunk で `T >= max(STRATA_PF_SWITCH_MIN_T, 64)`、`!gr_unfused()`、`!m.xn16_lo` の場合にだけ入力 stride `ldx` が `D + 64` になります。`STRATA_PF_SWITCH_MIN_T` は unset 時 0、設定時 `atoll` で読む static cache です（`engine/src/prefill/prefill.cpp:975-978,1008-1016,5101-5104`）。
- `STRATA_PF_HCDOWN` が先頭文字 `1` で有効な場合は、exact 分岐ではなく down と inject の融合経路が優先されます。exact 分岐の条件は `!pf_hcdown()` です（`engine/src/prefill/prefill.cpp:1001-1006,5111-5122`）。
- hyper-connection down weight が `q8_scale` を持つ場合、exact 分岐は使われず `bf16_proj()` の通常経路に進みます。exact 分岐は `wd->q8_scale == nullptr` の場合に限られます（`engine/src/prefill/prefill.cpp:5111-5124`）。さらに weight が `Bf16InF32`、`data` が非 null、shape が `ne0 == D` / `ne1 == LR` でなければ exact 関数を呼ばず通常経路になります（同 `5111-5124`）。
- HIPBLASLt tuning state がロードされ、形状が N=320 / K=10240、T が正である必要があります。さらに table の `hipblaslt_solution_for()` が 1176 または 1177 を返す必要があります（`engine/src/prefill/gemm.cu:1025-1045`）。
- `STRATA_HIPBLASLT_TUNING` が未指定または空の場合、Strata は `STRATA_HIPBLASLT_TABLE` を見て packaged table の利用を止める設定か判定し、そうでなければ package tuning directory を検索します。したがって明示的に exact を有効にしても、table がない場合は kernel は選ばれません（`engine/src/prefill/gemm.cu:284-300`）。

## 実行時の詳細

`STRATA_HCD_EXACT` 自体は prefill 内の `hcd_exact()` 初回呼び出し時に読み込まれ、関数 static に保持されます。その後の環境変更は反映されません。gfx1151 の HIP 起動では arch defaults がエンジンの switch 初回読み取り前に値を補います（`engine/src/prefill/prefill.cpp:1012-1015,5101-5113`、`engine/src/program/generate.cpp:4287-4320`）。

パディング条件が成立し、融合 down が無効で、weight が条件を満たすと `bf16_hcd_exact()` を試します。HIPBLASLt 対応時に tuning state がなければ false を返し、条件に合う分岐から最初の通常 shape 呼び出しで次の stderr を一度だけ出します。通常 GEMM が呼ばれるため、このメッセージ自体は終了エラーではありません。

`strata: STRATA_HCD_EXACT: no hipBLASLt tuning table is loaded, so the exact kernel has nothing to match: the hyper-connection down projection stays on hipBLAS`

table が solution 1176 / 1177 以外を返す場合も false となり、通常 GEMM に戻ります。`T >= 4096` のときに限り、同じ atomic flag で一度だけ次の stderr を出します（短い chunk ではこの理由ログを抑制）。

`strata: STRATA_HCD_EXACT: the tuning table gives the hyper-connection down projection (N 320, K 10240) solution %d at T %lld, not 1176 / 1177: hipBLASLt runs it (a changed table or library; tools/hip/gfx1151-hipblaslt-100401.txt is the one measured)`

exact kernel を使わず通常経路に戻った場合でも、条件を満たして `ldx` が padded stride になっていれば後続 projection はその stride を使います。HIPBLASLt 対応でない build では `bf16_hcd_exact()` はログなしで false を返し、通常 projection に進みます。通常 projection 自体が失敗すれば `bf16_proj()` の失敗が prefill 呼び出し元へ返ります（`engine/src/prefill/prefill.cpp:5111-5124`）。

## ログと測定値

上記の table 不在または solution 不一致の理由ログは stderr に出ます。通常どおり exact kernel を選んだことを示す専用ログはありません。`docs/STRIX_HALO.md:109-113` は gfx1151 向けスイッチとして説明し、table が 1176 / 1177 を選ぶ場合だけ走ると記載しています。`engine/src/core/arch_defaults.cpp:75` のコメントには 64K prompt で +1.8%（stream S）とありますが、同ファイルの記載以外に条件を含む測定記録を今回の調査範囲で確認できなかったため、一般的な性能値とは扱いません。`docs/DETAILS.md` にこの変数の追加説明はありません。

## 根拠

- 読み取り・cache・stride・fallback: `engine/src/prefill/prefill.cpp:975-1016,5101-5124`、SYCL counterpart `engine/sycl/src/prefill/prefill.cpp:372-399,3438-3459`。
- HIPBLASLt table 条件、solution 判定、stderr、kernel 呼び出し: `engine/src/prefill/gemm.cu:284-300,1025-1049`。
- gfx1151 の既定値、gfx12 除外、未設定時だけの適用: `engine/src/core/arch_defaults.cpp:28-77,218-223,302-310`。
- 起動時に defaults を適用する HIP 経路: `engine/src/program/generate.cpp:4287-4320`。
- 文書との照合: `docs/STRIX_HALO.md:106-113,125-140`、`docs/DETAILS.md:1304,1710`。
