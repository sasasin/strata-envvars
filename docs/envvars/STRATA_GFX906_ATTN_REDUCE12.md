# `STRATA_GFX906_ATTN_REDUCE12`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

gfx906 の INT8 K/V バッチ attention で、query-swizzle 用 chunk kernel の score reduction を `reduce12_gfx906` を使う特殊化に切り替える opt-in 変数です。attention 全体を別 API に切り替えるものではなく、chunk pass の kernel 選択を変えます。`REDUCE12` 特殊化は query-swizzle を使った query の読み出しを保ったまま score を計算し、通常の swizzled kernel では各 query head の和に `warp_sum` を使います。後段の softmax、value accumulation、merge はこの選択では変わりません。実装は `launch_chunks_batch` 内です（`engine/src/kernels/cuda/qsa_decode_attn.cu:133-160, 255-286, 1041-1092`）。

## 値と判定

値は `std::getenv` で取得し、値全体が ASCII の一文字 `1` である場合だけ有効です。数値変換はしません。大文字小文字の差は該当せず、空白の trim や前方一致もしません。

| 条件 | 未設定 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `STRATA_HIP_GFX906` を定義してビルドした場合 | OFF | `1` | 空文字、`0`、`true`、`01`、`1x`、` 1`、`1 ` など |
| それ以外のビルド | この変数を読む分岐自体がない | 該当なし | 実行時値は参照されない |

読み取り結果は `launch_chunks_batch` 内の関数ローカル `static const bool` に保存されます。最初に query-swizzle 経路へ入ったときに一度だけ評価され、その後の環境値変更は反映されません。CLI 引数や設定ファイルとの優先順位はなく、この分岐は環境値を直接読みます（同ファイル `:1072-1075`）。

## 有効になる条件

- `STRATA_HIP_GFX906` を定義して Strata の CUDA ソースを HIP でビルドしていること。この専用構成は `STRATA_HIP_GFX906` CMake option で有効になり、`STRATA_ENABLE_HIP` の wave32 backend とは別です（`engine/CMakeLists.txt:91-104, 919-920`; `engine/cmake/backends/hip.cmake:16-22`）。
- `STRATA_GFX906_ATTN_QUERY_SWIZZLE` が先頭文字 `1` で有効になっていること。親スイッチは `1`, `10`, `1anything` も有効扱いですが、空文字や `0` は無効です（`engine/src/kernels/cuda/qsa_decode_attn.cu:1043-1048`）。
- 呼び出しが通常の環境選択バッチ経路（`kernel < 0`）で、`STRATA_ATTN_LANECELL` による lane-cell 経路が選ばれていないこと（同ファイル `:1038-1048, 1057-1069`）。
- K/V pool が INT8（`kv_mode == 1`）で、呼び出し元スレッドの現在の device が正確に gfx906、wavefront size が 64 であること。device 判定はスレッド内で device ordinal ごとにキャッシュされます（同ファイル `:1028-1029, 1047-1048, 868-893`）。
- この変数が選ぶのは `qsa_decode_attn_batch` の chunk pass です。prefill はこの API を呼びます。MTP と verification は fused slot API が gfx906 query-swizzle + INT8 のとき `false` を返すため、呼び出し元が行単位の `qsa_decode_attn_batch` にフォールバックする経路で対象になり得ます（`engine/src/prefill/prefill.cpp:5565-5569`; `engine/src/kernels/cuda/qsa_decode_attn.cu:1174-1179`; `engine/src/core/mtp.cpp:2489-2499`; `engine/src/core/verify.cpp:2435-2447`）。
- `qsa_decode_attn_step` は別の単一 query 経路で、この特殊化を呼びません（`engine/src/kernels/cuda/qsa_decode_attn.cu:1309-1349`）。

## 実行時の詳細

`qsa_decode_attn_batch` は chunk pass を `kernel = -1` で呼びます。gfx906 query-swizzle 条件を満たすときにだけこの変数を読み、`1` なら `attn_chunk_kernel<1, false, true, true>`、それ以外なら `attn_chunk_kernel<1, false, true>` を起動します（`engine/src/kernels/cuda/qsa_decode_attn.cu:1026-1029, 1065-1092, 1132-1143`）。

特殊化では 12 query head の score reduction を `reduce12_gfx906` に通し、スコアを書き出します。ソースコメント上は各 head の `warp_sum` 群に対して shuffle exchange を 60 回から 16 回に減らす設計です。query-swizzle が無効、lane-cell が有効、pool が INT8 以外、または gfx906 wave64 以外なら、この変数にかかわらず別の kernel 経路になります（同ファイル `:133-160, 255-286, 1041-1092`）。

## ログと測定値

通常、この変数の読み取りや kernel 選択を知らせるログは出ません。別の `STRATA_GFX906_ATTN_REDUCE12_TRACE` が値全体 `1` のとき、特殊化を選んだスレッドで一度、stderr に次の形式で出力します。trace 変数は reduction 特殊化の分岐内でのみ読みます。

```text
strata attn-reduce12: selected=1 query_swizzle=1 kv_mode=1 nq=<n_q> cap=<cap>
```

kernel 起動後の `cudaGetLastError` が失敗した場合、`qsa_decode_attn_batch: <runtime error text>` を stderr に出し、プロセスを終了コード 1 で終了します（`engine/src/kernels/cuda/qsa_decode_attn.cu:1076-1087, 1140-1147`）。`docs/AMD_HIP.md` は両 gfx906 attention switch が既定 OFF で gfx906 専用ビルドにのみ含まれると記載しています（`docs/AMD_HIP.md:570-580`）。この変数固有の性能値は、調査対象ソースと参照した資料に記載がないため記載しません。

## 根拠

- `engine/src/kernels/cuda/qsa_decode_attn.cu:1026-1092` — バッチ kernel の条件、値判定、選択される二つの kernel、trace。
- `engine/src/kernels/cuda/qsa_decode_attn.cu:1132-1147` — chunk/merge の呼び出しと失敗時の終了。
- `engine/src/kernels/cuda/qsa_decode_attn.cu:1150-1179, 1309-1349` — slot 経路の拒否条件と、単一 query 経路に当該分岐がないこと。
- `engine/src/kernels/cuda/qsa_decode_attn.cu:133-160, 193-201, 255-286` — reduction と query-swizzle の score 計算。
- `engine/src/kernels/cuda/qsa_decode_attn.cu:868-893` — gfx906 / wave64 device 判定と thread-local cache。
- `engine/CMakeLists.txt:91-104, 919-920`; `engine/cmake/backends/hip.cmake:16-22` — gfx906 HIP compat build の有効化。
- `engine/src/prefill/prefill.cpp:5565-5569`; `engine/src/core/mtp.cpp:2489-2499`; `engine/src/core/verify.cpp:2435-2447` — バッチ API の呼び出しと slot からの fallback。
- `docs/AMD_HIP.md:570-580` — gfx906 build と attention switches の資料上の位置づけ。
