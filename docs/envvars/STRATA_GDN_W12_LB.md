# `STRATA_GDN_W12_LB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

gfx12 向け HIP の chunked GDN scan における workgroup barrier を選ぶ。既定（未設定）では LDS 用の待機と barrier を使い、0 と解釈される値では `__syncthreads()` を使う。どちらも同じ scan カーネルの同期箇所を切り替えるもので、GDN の数値計算式や経路選択条件を直接変える変数ではない。`gdn_w12_scan_kernel<LB, H16>` の `LB` がこの選択である（`engine/src/prefill/kernels.cu:2216-2224,2263-2270`、`engine/src/prefill/gdn_wmma12.inc:27-41,196-202,263-317`）。

## 値と判定

値は `std::getenv` で取得し、未設定なら `true`、設定済みなら `std::atoi(v) != 0` とする。文字列全体の妥当性や末尾は検査しない。`atoi` が読み取れる先頭の整数部分で判定し、空文字や数値に変換できない文字列は 0 扱いとなる。符号や先頭空白も `atoi` の整数変換に従う（`engine/src/prefill/kernels.cu:2218,2264`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP gfx12 の該当 scan 経路 | 有効（`LB=true`） | `atoi` の結果が非 0。例: `1`, `-1`, `2`, `1junk`, ` 1` | `atoi` の結果が 0。例: `0`, `0anything`, `true`, `false`, 空文字, `junk` |

## 有効になる条件

- Strata が HIP ビルドであること。`gdn_rec_wmma` の gfx12 scan は HIP 実装内にあり、畳み込みと再帰を融合する入口も HIP のときだけ呼び出す（`engine/src/prefill/kernels.cu:2274,3290-3298`）。
- 実行デバイスが gfx12 WMMA 対応として識別されること。非融合経路は gfx11 または gfx12 の WMMA 対応を確認した後に gfx12 分岐へ入り、融合経路は gfx12 以外なら `false` を返す（`engine/src/prefill/kernels.cu:2203-2216,2245-2256`）。
- GDN の chunked 経路が選ばれること。通常の再帰では `STRATA_GDN_CHUNKED=0` 相当だとこの scan に進まず、融合経路では `STRATA_GDN_CHUNKED` が 0 でないことと、`STRATA_GDN_FUSE` が未設定または `atoi` で非 0 であることが融合有効判定に必要（`engine/src/prefill/kernels.cu:1894-1901,2235-2242,3080-3091`）。未設定の `STRATA_GDN_CHUNKED` は gfx12 で長さ条件を満たす場合に chunked を選ぶ。明示的な非 0 値ではその長さ gate を通らず候補になる（`engine/src/prefill/kernels.cu:2211-2213,2255-2256`）。
- chunk 長 `T` が少なくとも 64 で、`ld16` が 8 の倍数であること。融合経路では既定 `ld16` を埋めた後にこの整列条件を検査する。短い・非整列などで scan が適用されない場合、呼び出し元は通常の畳み込みと再帰へ進む（`engine/src/prefill/kernels.cu:1884,2197,2212,2242-2244,2255`; `engine/src/prefill/prefill.cpp:5196-5210,9334-9342`）。
- `STRATA_GDN_W12_LB` 自身に CLI 引数との優先順位や別の上書き値はない。上記の経路条件に合致した後、その scan の barrier 実装だけを選択する。

## 実行時の詳細

非融合経路では `gdn_rec_wmma` が gfx12 分岐に入った時、prep kernel を起動した後にこの値を読み、scan kernel の `LB` を選ぶ。融合経路では `gdn_fused_impl` の融合条件と gfx12・長さ条件を通った後、prep 前の畳み込み kernel 群に続いて値を読み、同じ scan kernel の `H16=true` 版を起動する（`engine/src/prefill/kernels.cu:2216-2224,2245-2270`）。

それぞれの読み取り箇所は関数ローカルの `static const bool` に保存される。2 箇所は別々の static なので各経路が初めて到達した時点で独立に評価され、その後のプロセス内環境変更は対応する経路の値に反映されない（同上）。

`LB=true` は `gw12_barrier` 内で `s_wait_dscnt 0x0` と `__builtin_amdgcn_s_barrier()` を実行し、false は `__syncthreads()` を実行する。これらは scan 内の 2 箇所の LDS 同期と終了時同期で使われる（`engine/src/prefill/gdn_wmma12.inc:27-41,263,306,317`）。値が原因の専用ログや警告はない。通常経路の `gdn_rec_wmma` が適用不可なら `false` を返して呼び出し元が別の再帰へ進み、融合経路が適用不可なら `false` を返して呼び出し元が通常の畳み込み・再帰を実行する（`engine/src/prefill/kernels.cu:2211-2230,2242-2256`; `engine/src/prefill/prefill.cpp:5203-5210,9339-9342`）。カーネル起動後のエラー確認は通常経路では呼び出し元の `check("gdn_recurrence (chunked, WMMA)")`、融合経路では `check("gdn_conv_recurrence_fused")` に委ねられる（`engine/src/prefill/kernels.cu:3087-3090,2271`）。

## ログと測定値

この環境変数の値や選択した barrier を出力するログは、確認した Strata ソースにはない。`docs/DETAILS.md` は `STRATA_GDN_CHUNKED` に関する説明を含むが、この barrier 選択変数の説明や比較測定値は記載していない（`docs/DETAILS.md:1243,1694`）。この調査では測定していない。

## 根拠

- `engine/src/prefill/kernels.cu:2216-2224,2263-2270` — 2 経路での変数読み取りと template 値による scan 起動。
- `engine/src/prefill/gdn_wmma12.inc:27-41,196-202,263,306,317` — barrier の true/false の実装と scan 内での使用。
- `engine/src/prefill/kernels.cu:1884-1901,2195-2230,2232-2274,3075-3091,3290-3298` — chunked 経路の条件、gfx 判定、通常 fallback と HIP 限定の融合入口。
- `engine/src/prefill/prefill.cpp:5196-5210,9334-9342` — 呼び出し元で融合不可時に通常処理へ進む流れ。
- `docs/DETAILS.md:1243,1694` — 関連する chunked GDN の説明と性能情報。`STRATA_GDN_W12_LB` 自体の記述はない。
