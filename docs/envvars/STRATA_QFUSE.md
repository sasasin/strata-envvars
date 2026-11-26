# `STRATA_QFUSE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

verify window 内で activation の Q8_1 量子化データを、後段の利用元で別途作る代わりに、その activation を作る GDN 出力正規化と hyper-connection (HC) 読み取りの producer が同じバッファへ書く制御です。通常経路では HC 読み取り後の `mixed` と GDN の `y_` を `quant_in` しますが、QFUSE が出力を書いた場合はこの個別量子化を省きます。HC 入力は attention 側と FFN 側の読み取りで扱われます（`engine/src/core/verify.cpp:1796-1820,1880-1906,2005-2013,2613-2614,2740-2772`）。

CUDA/HIP の verify では QFUSE が有効だと one-token self-commit を使わず、window commit 側の処理を通します（`engine/src/core/verify.cpp:1486-1489,4531-4541,4588-4594`）。同一バイト列・性能向上などの一般保証はここではしません。

## 値と判定

`engine/src/core/verify.cpp:320` と `engine/sycl/src/core/verify.cpp:135` で `std::getenv` の結果を `std::atoi` に渡し、非 null かつ変換結果が非ゼロなら ON とします。文字列全体の検証はなく、数値として読める先頭部分を `atoi` が変換します。設定値は各プロセスで最初に `g_qfuse()` が呼ばれた時に関数内 `static` へ保存されます。

| 条件 | unset | ON になる値の例 | OFF になる値の例 |
|---|---|---|---|
| 明示値（CUDA/HIP/SYCL の verify） | `false` | `1`, `-1`, `2`, `1tail`, ` 1` | 空文字, `0`, `0tail`, `true`, ` 0` |

`atoi` の整数変換に収まらない値の結果は文書化された入力として扱えず、コードに範囲検証・警告・fallback はありません。環境変数を実行中に変更してもキャッシュ済み判定は変わりません。

起動時には、対象 GPU の arch defaults がこの名前を未設定の場合だけ値 `1` を追加することがあります。すでに空文字や `0` を含む値が設定されていれば、それが優先されます（`engine/src/core/arch_defaults.cpp:64-90,302-310`; `engine/src/program/generate.cpp:4287-4320`; `engine/src/core/nv_defaults.cpp:104-129,176-214,222-234,240-255`）。

| 起動経路 | unset 時に自動設定される条件 | 自動設定を止める条件 |
|---|---|---|
| HIP、gfx1151 (Strix Halo) | `STRATA_GFX1151_DEFAULTS` が先頭 `0` でなく、ユーザー値が未設定なら `1`。Windows/Linux とも arch table に含まれる | `STRATA_GFX1151_DEFAULTS=0` または任意の明示値 |
| CUDA、sm_120 / sm_121 | 同一 compute capability の可視 GPU 群で defaults table が適用され、`STRATA_SM120_PERF` / `STRATA_SM121_PERF` が先頭 `0` でなく、`STRATA_DEFAULTS=026` でない場合、未設定なら `1` | 上記 switch、`STRATA_DEFAULTS=026`、任意の明示値。混在 compute capability の GPU 群では当該 table 自体が適用されない |
| その他 | 自動設定なし | — |

`STRATA_DEFAULTS=026` は `026`、`0.2.6`、`v0.2.6` の完全一致で有効です（`engine/include/strata/core/defaults_026.hpp:21-29`）。gfx1151 table はこのフラグで QFUSE を除外しません。上表の default は arch table の値であり、明示された `STRATA_QFUSE` の値判定とは別です。

## 有効になる条件

- `g_qfuse()` を使う verify window の実行が必要です。CLI 引数による個別の上書きはこの実装にありません（`engine/src/core/verify.cpp:1486-1489,1796-1820,2005-2013`）。
- GPU バッファ `qcnt_` の確保が成功した時、HC 読み取りへ Q8_1 出力先を渡します。確保またはゼロ初期化に失敗するとポインタを null に戻し、HC 側はこの経路を使いません。コード上、ここで QFUSE 専用のエラーや警告は出しません（`engine/src/core/verify.cpp:1431-1437,1810-1817`）。
- QFUSE は GDN 出力にも適用されますが、batch recurrence 経路は出力先を渡さず、その後 `quant_in` します（`engine/src/core/verify.cpp:1995-2013`）。
- CUDA/HIP の QFUSE 対応 kernel を含む build が必要です。SYCL 側も値を読み、GDN 出力にポインタを渡しますが、SYCL port の fused HC read は Q8_1 image を書かず `false` を返すため、HC 読み取りの生成経路は使われません（`engine/sycl/src/core/verify.cpp:1209-1231,1307-1312`; `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3289-3297`）。
- `STRATA_HC_PERSIST=1` の persistent HC read は `q8_mixed` が設定されている場合に fallback して既定 read を使います（`engine/src/core/verify.cpp:1810-1817`; `engine/src/kernels/cuda/fused_gr.cu:5304-5315`）。
- folded native expert layer は、HC 側で作った未回転 activation の Q8_1 image を後段で回転済み入力から書き直します（`engine/src/core/verify.cpp:2761-2772`）。

## 実行時の詳細

`g_qfuse()` の判定は function-local `static` です。arch defaults は `generate.cpp` が engine switch の初回読み取り前に適用します。HIP の gfx1151 では `apply_arch_defaults` がユーザー設定のない変数だけを追加し、CUDA の sm_120 / sm_121 では `apply_nv_defaults` が同様に設定します。追加した場合、CUDA の既定 switch 一覧は stderr に `strata: sm_120 (Blackwell): ... speed switches on by default ...` または `strata: sm_121 (GB10): ...` 形式で出ます（`engine/src/program/generate.cpp:4287-4320,4421-4449`; `engine/src/core/arch_defaults.cpp:302-310`; `engine/src/core/nv_defaults.cpp:222-255`）。gfx1151 の `apply_arch_defaults` は設定した switch 名を返しますが、当該関数内で QFUSE 専用のログは出しません。

CUDA/HIP は QFUSE または `STRATA_QFUSE_HC` が有効な場合、HC の q8 group counter buffer を `n_embd / 32` 個確保・ゼロ初期化します。QFUSE が有効で buffer が使える場合、HC read の各出力へ `q8_mixed` を設定し、GDN norm にも `xq_` を渡します。通常の後段 `quant_in` は HC image が用意されていれば省略し、GDN では QFUSE が有効かつ batch recurrence でないときに省略します（`engine/src/core/verify.cpp:1431-1437,1796-1820,1880-1906,2005-2013,2613-2614`）。

buffer が存在するかを示す診断行は `strata::dispatch::notef` の `hc read: weights Q8_0 copies=%ld (0 = bf16 rows), half=%ld, qfuse=%ld` です。これは環境変数の文字列値ではなく、HC read 時点の `qcnt_ != nullptr` を出します（`engine/src/core/verify.cpp:1796-1798`）。

## ログと測定値

QFUSE の明示 ON/OFF に対する専用ログ、無効値警告、終了コード経路はありません。CUDA の defaults table が QFUSE を含む複数 switch を追加した場合は、上記の起動時一覧が stderr に出ます。HC read 時の `qfuse` 診断値は buffer 確保状態の表示です（`engine/src/core/nv_defaults.cpp:240-255`; `engine/src/core/verify.cpp:1796-1798`）。

## 根拠

- 値の読み取り・cache: `engine/src/core/verify.cpp:320`; `engine/sycl/src/core/verify.cpp:134-135`
- arch defaults: `engine/src/core/arch_defaults.cpp:64-90,302-310`; `engine/src/core/nv_defaults.cpp:104-129,176-234`; `engine/src/program/generate.cpp:4287-4320,4421-4449`
- HC/GDN output wiring, fallback, commit path: `engine/src/core/verify.cpp:1431-1437,1486-1489,1796-1820,1880-1906,1995-2013,2613-2614,2732-2774,4531-4541,4588-4594`
- SYCL HC behavior: `engine/sycl/src/core/verify.cpp:1209-1231,1307-1312`; `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3289-3297`
- Persistent HC fallback: `engine/src/kernels/cuda/fused_gr.cu:5304-5315`
