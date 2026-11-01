# `STRATA_GDN_CHUNKED`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。外部ライブラリ・GPU driver の環境変数動作は対象外。

## 役割

Gated DeltaNet (GDN) の prompt recurrence を、token ごとの逐次 kernel から複数 token の chunk をまとめる経路へ切り替える opt-in 変数です。CUDA では FP32 の chunked recurrence、HIP では gfx11/gfx12 の WMMA recurrence を選びます。どちらも通常の GDN recurrence を置き換える計算経路で、CUDA と HIP で値の精度・適用条件・chunk 長が異なります。

Strata 所有コードにある実際の環境読み取りは `src/prefill/kernels.cu` の CUDA/HIP recurrence dispatcher と、HIP gfx12 の convolution/recurrence 融合 helper の計 4 箇所です（`src/prefill/kernels.cu:1247,2163-2167,2883-2889,2982-2986`）。`serve/server.py` は特定の構成で子 engine に値を設定しますが、値の自動設定は明示値を上書きしません（`serve/server.py:3728-3745,3747-3764`）。

## 値と判定

カーネル側は `std::atoi()` で数値変換し、CUDA/HIP dispatcher では変換結果が 0 かどうかを見ます。文字列全体の数値検証はなく、先頭の空白・符号と数値部分を読み、数値以降の文字は判定に使いません。したがって未設定または空文字、`true`、数値として読めない文字列は 0 になり、`1`, `-1`, `1tail` などは非 0 です。CUDA の追加 SM 条件では変換値が 2 以上かを別に判定します。値の範囲検証や clamp はありません（`src/prefill/kernels.cu:1247,2163-2167,2887,2985`）。

| 値（`atoi` の結果） | CUDA recurrence | HIP gfx11/gfx12 recurrence | HIP gfx12 融合 |
|---|---|---|---|
| 未設定、空文字、0、非数値文字列 | 無効 | 無効 | 無効 |
| 非 0（例: `1`, `-1`） | 有効候補 | 有効候補 | 有効候補 |
| 2 以上 | 有効候補。128 SM 条件を省略 | 有効候補。CUDA の SM 条件はない | 有効候補 |

これは経路を試す条件であり、その値だけで kernel が必ず起動することを意味しません。CUDA では別の `STRATA_GDN_TC` 経路が先に選ばれる場合もあります。HIP gfx12 では融合経路の可否と通常 recurrence の可否を別々に評価します（`src/prefill/kernels.cu:1247-1251,2163-2181,2982-3044`）。

## 有効になる条件

### CUDA

- HIP ではないビルドの通常 recurrence dispatcher が対象です。値が非 0 で、`T >= 128` のとき chunked FP32 recurrence を試します（`src/prefill/kernels.cu:934-935,2982-2986,3039-3043`）。
- device の compute capability major が 8 以上、chunk scan に必要な opt-in shared memory があり、scratch を確保できる必要があります。通常は scan 用の 128 block を一度に置ける 128 SM も必要です。`atoi(value) >= 2` のときだけこの SM 数条件を飛ばします。compute capability と shared memory 条件は `=2` でも残ります（`src/prefill/kernels.cu:1231-1253`）。
- 条件を満たさない、prompt が短い、または scratch が取れない場合はこの経路を採らず、後続の通常 kernel に進みます。通常 dispatch では `STRATA_GDN_TC` が有効でその経路が成功すれば TC が優先され、chunked は選ばれません（`src/prefill/kernels.cu:3026-3055`）。
- CUDA の chunk は 32 token 単位です。数値演算の実装は chunk prep と scan の FP32 kernel で、通常 recurrence とは演算順序が異なります（`src/prefill/kernels.cu:927-944,1231-1277`）。

### HIP

- `STRATA_GDN_CHUNKED` が非 0 で、recurrence の `variant` が 0 または 1、`STRATA_GDN_REC_HEADS` が未設定であるとき WMMA 経路を試します。`STRATA_GDN_REC_HEADS` は設定有無で serial 経路を選び、値が空でも設定されていれば WMMA を止めます（`src/prefill/kernels.cu:2882-2891`）。
- WMMA 経路は gfx11 WMMA または gfx12 WMMA device に限られ、`T >= 64`、出力 stride `ld16` が 8 の倍数である必要があります。その他の device、短い入力、stride 不適合なら `false` を返し、後続の recurrence kernel に進みます。gfx11 の WMMA intrinsic は対応する gfx11 device pass で定義されます（`src/prefill/kernels.cu:1814-1828,2121-2155`）。
- HIP の chunk は 16 token です。WMMA の行列積は FP16 operand、FP32 accumulation で実行されます。通常の FP32 recurrence と丸め結果が異なり得ます（`src/prefill/kernels.cu:1803-1813,1817-1822`）。
- gfx12 では prefill 側が先に畳み込み込み経路を試します。この融合は `STRATA_GDN_CHUNKED` が非 0、`T >= 64`、gfx12、stride 条件適合で、かつ `STRATA_GDN_FUSE` が未設定または `atoi` 結果非 0 のときに限られます。`STRATA_GDN_FUSE=0`（または `atoi` 結果 0）は融合を止めますが、その後の通常 recurrence で WMMA chunked を選ぶ条件は別なので、chunked recurrence 自体を止める設定ではありません。融合不可の場合は通常の `gdn_conv()` と recurrence 呼出しに進みます（`src/prefill/prefill.cpp:3817-3831`, `src/prefill/kernels.cu:2157-2181,3090-3099`）。

### server.py による子 engine への設定

`child_env()` はまず親プロセス環境をコピーし、config の `env` を上書き適用した後 `gdn_stack_env()` を呼びます。Linux 上の `qwen4exp`、HIP backend で、表示対象の全 AMD device が `gfx12` であることを検出できた場合、`setdefault` で `STRATA_GDN_CHUNKED=1` を追加します。ユーザー環境または config の `env` に同名キーがあればその値を保持します。対象構成外、device arch が不明、あるいは gfx12 以外を含む場合、この helper は値を自動追加しません（`serve/server.py:3728-3745,3747-3764`）。これは server の子プロセス環境設定であり、engine 側で gfx11 も対象となる HIP 経路を gfx12 専用に制限するものではありません。

## 実行時の詳細

CUDA dispatcher の `chunked`、HIP dispatcher の `chunked`、HIP gfx12 融合 helper の `on` は、それぞれ関数内 `static const` に初回評価結果を保持します。`gdn_rec_chunked()` 内の `=2` 用 SM bypass も別の `static const` です。そのため各読み取り箇所で最初に評価された後、プロセス内で環境を変更してもその値は再評価されません。HIP の fused helper と通常 recurrence dispatcher は別々に初期化されるため、それぞれが最初に呼ばれた時点の判定を保持します（`src/prefill/kernels.cu:1247,2163-2167,2883-2889,2982-2986`）。

CUDA の chunked 経路が eligibility check や scratch allocation に失敗した場合、その呼出しは kernel を起動せず通常 dispatch に戻ります。`gdn_chunk_why()` の理由文字列は probe がある場合の診断情報用です。HIP で gfx11/gfx12 判定や入力長条件が合わない場合も WMMA helper が false を返し、呼出し元が通常経路を続けます。通常利用時に「環境変数を設定したが不適格だった」という専用警告は確認できません（`src/prefill/kernels.cu:1231-1253,1370-1393,2121-2155,2887-2891,3039-3055`）。

kernel launch 後の `check()` が CUDA/HIP runtime error を検出すると、stderr に `prefill <処理名>: <runtime error>` を出して exit status 1 で終了します。これは fallback 可能な事前 eligibility 不成立とは異なる経路です（`src/prefill/kernels.cu:102-105,2887-2890,2157-2197,3071`）。

## 根拠

- `src/prefill/kernels.cu:1231-1253,1272-1277` — CUDA chunked kernel の device 条件、`=2` の SM 数 bypass、scratch、launch。
- `src/prefill/kernels.cu:927-944,2982-2986,3026-3055` — CUDA の chunk 長、env 判定、TC 優先と fallback。
- `src/prefill/kernels.cu:1814-1828,2121-2155,2882-2891` — HIP gfx11/gfx12 WMMA 対象、64 token 下限、stride と recurrence dispatch。
- `src/prefill/kernels.cu:2157-2197` — gfx12 融合条件、`STRATA_GDN_FUSE` の関係、kernel launch check。
- `src/prefill/prefill.cpp:3817-3831` — GDN prefill 呼出し順と融合失敗後の通常 convolution/recurrence。
- `src/prefill/kernels.cu:102-105,3071` — runtime error の stderr と終了処理。
- `serve/server.py:3728-3745,3747-3764` — server が gfx12 HIP 条件で子 engine 環境へ既定値を加え、親環境/config の値を保持する処理。
- 現行 `docs/DETAILS.md:1029,1436` は CUDA と gfx11 の記述に留まり、現行ソースで確認できる gfx12 WMMA 経路と server 側の gfx12 設定は列挙していません。実装条件の根拠には上記ソースを用いました。
