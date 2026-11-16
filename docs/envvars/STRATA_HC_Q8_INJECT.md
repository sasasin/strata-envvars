# `STRATA_HC_Q8_INJECT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`STRATA_HC_Q8` が有効な native dense の重みロードで、GGUF 内の F32 hyper-connection injection 行列にも Q8_0 のコピーを作るかを選ぶ。対象行列は `blk.<layer>.hc_attn_inject.weight` と `blk.<layer>.hc_ffn_inject.weight`。既定ではこの F32 行列に Q8_0 コピーを作らず、injection の読み取りは BF16 行を使う。値を有効にするとロード時に F32 から Q8_0 へ量子化して device memory にコピーし、verify の fused GR 読み取りへ `q8_inject` として渡す。通常の down/up 投影の Q8_0 化を有効にするスイッチではなく、それには親スイッチ `STRATA_HC_Q8` が必要である（`src/core/native_dense.cpp:91-102,503-536`; `src/core/verify.cpp:1602-1613`; `src/kernels/cuda/fused_gr.cu:2023-2036`）。

## 値と判定

CUDA/HIP 実装では `hc_q8_inject_env()` の関数内 `static` 初期化、SYCL 実装ではロードループ内の関数内 `static` 初期化で `getenv` の値を取得し、値の先頭 1 文字が `'1'` かだけを調べる。文字列全体の数値変換・妥当性検査はしない。したがって空文字・未設定は無効で、`1`、`10`、`1anything` は有効、`0`、`true`、`True`、` 1`、`01` は無効となる（`src/core/native_dense.cpp:92-95`; `sycl/src/core/native_dense.cpp:393-399`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP native dense | false | 先頭文字が `1`（例: `1`, `1foo`） | 空文字、`0`, `true`, ` 1`, `01` など |
| SYCL native dense | false | 先頭文字が `1`（例: `1`, `1foo`） | 空文字、`0`, `true`, ` 1`, `01` など |

## 有効になる条件

- `STRATA_HC_Q8` が有効であること。無効なら CUDA/HIP は `hc_q8_env()` の分岐に入らず、SYCL は `hc_q8_requested()` が false となり、この変数による処理は行われない。親スイッチの条件は backend ごとに異なる。CUDA/HIP 共通の判定は先頭文字 `1` で ON、空でない値（ただし完全一致の `auto` を除く）で OFF。HIP では unset / 空 / `auto` が gfx1151・gfx12 で既定 ON（gfx12 は `STRATA_GFX12_DEFAULTS=0` で抑止）。非 HIP の CUDA では unset / 空 / `auto` 自体は OFF だが、通常 generate 経路は Q8_0 hyper-connection を含む GGUF の場合に unset を `1` に設定する（明示設定は保持）。SYCL は値の先頭文字が `1` の場合だけ ON（`src/core/native_dense.cpp:47-85,646-653`; `src/program/generate.cpp:4844-4848`; `sycl/src/core/native_dense.cpp:33-36,393-399`）。
- native dense のロード対象 GGUF に、名前が `hc_q8_name()` の対象で、型が F32 (`tensor.type == 0`)、名前末尾が `_inject.weight`、2 次元の tensor があること。その他の型・名前・次元の行列はこの変数では追加コピーされない（`src/core/native_dense.cpp:96-102,503-508`; `sycl/src/core/native_dense.cpp:38-44,393-399`）。
- CUDA/HIP では stage-local のフィルターが既定で有効で、別 stage またはロード範囲外の層はコピーを飛ばす。`STRATA_HC_Q8_ALL_STAGES=1` はこの stage-local 判定を無効にする（`src/core/native_dense.cpp:86-89,509-515`）。SYCL 側の該当ロードにはこのフィルターがない。
- BF16 pack 側で行う Q8_0 変換ループは down/up projection のみを対象とし、injection 行列を対象にしない。そのため、この変数が扱うのは F32 injection tensor が GGUF のロード対象にある場合であり、BF16 pack の injection 行を Q8_0 化する条件ではない（`src/core/native_dense.cpp:539-571`）。
- ソース上、この判定に CLI 引数やサーバーモード固有の分岐はない。native dense `load` を通る経路で共通に評価される。

## 実行時の詳細

CUDA/HIP では `hc_q8_inject_env()` の初回呼び出し時に環境を読み、結果を `static const bool` に保存する。呼び出し元は容量見積もり `weight_bytes_for()` と実ロードの両方にあるため、親スイッチが有効なら容量見積もり時にこの値が初期化され得る。SYCL では親スイッチが有効で GGUF tensor 走査に入ったとき、最初のループで値を static cache する。いずれも同一プロセス内での後からの環境変更は反映されない（`src/core/native_dense.cpp:92-95,220-244,503-508`; `sycl/src/core/native_dense.cpp:393-399`）。

有効時、F32 injection tensor の各要素を `q8_0_of()` で Q8_0 に量子化し、`ne0 / 32 * 34 * ne1` bytes の device buffer にコピーして `WeightRef::hc_q8` に設定する。shape が canonical table と一致しない、または行幅が 32 の倍数でない場合は `native dense (STRATA_HC_Q8): incompatible matrix <name>` を `err` に設定してロードを失敗させる。device allocation / upload が失敗した場合もロードは失敗し、エラー文字列は CUDA/HIP では `native dense (STRATA_HC_Q8) upload <name>`、SYCL では同じ形式になる（`src/core/native_dense.cpp:520-536`; `sycl/src/core/native_dense.cpp:403-429`）。

CUDA/HIP verify 経路は `WeightRef::hc_q8` を `FusedGrArgs::q8_inject` に渡す。CUDA fused GR kernel はその pointer が null でなければ injection 行を Q8_0 側から読み、null なら injection 行の BF16 側を使う（`src/core/verify.cpp:1602-1613`; `src/kernels/cuda/fused_gr.cu:2023-2036`）。この変更は injection 行列の読み取り表現に関するもので、Strata のソース資料にはこの変数単独の速度・出力差の測定値は見当たらない。SYCL もロードした `hc_q8` を verify 引数へ設定するが、この調査では SYCL kernel 内の消費箇所を特定できなかったため、その先の SYCL 側計算への効果は断定しない（`sycl/src/core/verify.cpp:1141`）。

## ログと測定値

この変数専用のログは確認できなかった。親スイッチが有効な場合、ロード成功時には `strata: STRATA_HC_Q8=1: %.2f GiB of Q8_0 hyper-connection projections for the verify read` が stderr に出るが、F32 injection コピーだけの有無や個数は表示しない（`src/core/native_dense.cpp:626-628`; `sycl/src/core/native_dense.cpp:480-482`）。CUDA/HIP では `STRATA_MANIFEST` 有効時に injection コピーが manifest の `dense_hc_q8_copy` と型 `F32->Q8_0` で記録される（`src/core/native_dense.cpp:536`）。

## 根拠

- `src/core/native_dense.cpp:91-102` — 値判定の static cache と対象 tensor 名。
- `src/core/native_dense.cpp:220-244,503-536` — 容量見積もり、F32 injection 行の選別、変換・転送、エラーと manifest 記録。
- `src/core/native_dense.cpp:509-515,539-571,626-628,646-653`; `src/program/generate.cpp:4844-4848` — stage filter、BF16 pack の対象範囲、成功時ログ、CUDA の親スイッチ既定設定。
- `sycl/src/core/native_dense.cpp:393-429,480-482` — SYCL の値判定、変換・転送、エラーと成功時ログ。
- `src/core/verify.cpp:1602-1613`; `src/kernels/cuda/fused_gr.cu:2023-2036` — CUDA verify から fused GR kernel へ渡す経路と Q8_0 / BF16 選択。
- `sycl/src/core/verify.cpp:1141` — SYCL verify 引数への `hc_q8` pointer 設定。
