# `STRATA_GFX906_ATTN_REDUCE12`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

gfx906 向けの QSA batched attention で、INT8 KV 用の query-swizzled カーネルを起動するとき、score の warp reduction を専用の reduce-scatter 実装に切り替えます。標準の query-swizzled 経路と比べて score の加算順序は同じ意図で、shuffle 交換を 60 回から 16 回に減らす実装です。softmax、value accumulation、chunk merge は変わりません（`src/kernels/cuda/qsa_decode_attn.cu:87-111,206-237`）。

この環境変数は通常の単一 query 用 `qsa_decode_attn_step()` には適用されません。`qsa_decode_attn_batch()` 内の分岐にあり、batched attention を呼ぶ prefill、verification、MTP 経路が対象です（同ファイル `:618-709,716-756`、`src/prefill/prefill.cpp:2848`、`src/core/verify.cpp:1376-1391`、`src/core/mtp.cpp:825`）。

## 値と判定

コードは文字列全体を `v[0] == '1' && v[1] == '\0'` と比較します。数値変換や空白除去、大文字小文字変換はしません。

| 値 | reduce12 選択フラグ |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `1` | 有効 |
| `10`、`01`、`true`、` 1`、`1 `、その他 | 無効 |

フラグは `qsa_decode_attn_batch()` 内の関数ローカル `static const bool` です。実際に query-swizzle 経路へ入った最初の呼び出しで評価され、その後プロセス内で環境変数を変更しても再評価されません（`src/kernels/cuda/qsa_decode_attn.cu:660-670`）。

## 有効になる条件

環境変数を `1` にしても、次の条件を満たす呼び出しでなければ専用カーネルは選ばれません。

- `STRATA_HIP_GFX906` を定義した gfx906 compat build である。CMake では `STRATA_HIP_GFX906=ON` が CUDA ターゲットを HIP でコンパイルし、この定義を付けます（`CMakeLists.txt:59-70,122-138`）。通常の CUDA build や wave32 HIP build にはこの分岐がコンパイルされません。
- `STRATA_GFX906_ATTN_QUERY_SWIZZLE` の先頭文字が `1` である。
- `STRATA_ATTN_LANECELL` の先頭文字が `1` でなく、KV mode が INT8 (`kv_mode == 1`) である。KV mode は pools のポインタ構成から決まります。
- 呼び出しスレッドの現在の device が `gfx906` かつ `warpSize == 64` である。device 判定は thread-local に device ordinal ごとでキャッシュし、HIP API 失敗時はこの経路を使いません。

この条件のうち一つでも満たさない場合、対象の環境変数に `1` が設定されていても reduce12 カーネルは選択されず、通常の query-swizzled kernel または他の KV-mode/lane-cell 用カーネルに進みます（同ファイル `:547-572,637-701`）。

## 実行時の詳細

条件を満たす batched 呼び出しでは `attn_chunk_kernel<1, false, true, true>` を起動します。最後の template 引数 `REDUCE12=true` によって、各 cell の score 計算で 12 query head の部分和を専用 butterfly reduction に渡します。値が未設定または `1` 以外の場合は `attn_chunk_kernel<1, false, true>` を使います。いずれも後続の `attn_merge_kernel` で chunk を統合し、起動エラーがあれば `qsa_decode_attn_batch: <CUDA/HIP runtime error>` を stderr に出して終了します（同ファイル `:206-237,660-706`）。

専用経路が選ばれたことを確認するログは別の `STRATA_GFX906_ATTN_REDUCE12_TRACE` で制御されます。この変数も文字列全体が `1` の場合だけ有効で、最初の該当呼び出し後に thread-local の一度限りログとして、`strata attn-reduce12: selected=1 query_swizzle=1 kv_mode=1 nq=... cap=...` を stderr に出します（同ファイル `:674-683`）。トレース変数を設定しなければ、この分岐固有の選択ログはありません。

## 資料との照合

`docs/AMD_HIP.md:465-472` は gfx906 build を opt-in とし、両 attention switch が既定 OFF で gfx906 build にのみコンパイルされると説明しています。reduce12 専用の測定結果は同資料に分けて記録されていません。続く測定は 2 枚の MI50 などの環境とモデル・実行条件を示していますが、query-swizzle/reduce12 個別の寄与を示す比較ではないため、この変数の性能向上量や正確性を独立に確認した値としては扱えません。

## 根拠

- 値判定、query-swizzle との組み合わせ、カーネル選択、trace ログ: `src/kernels/cuda/qsa_decode_attn.cu:637-701`。
- device 条件とキャッシュ: `src/kernels/cuda/qsa_decode_attn.cu:547-572`。
- reduce の処理と batched / step の区別: `src/kernels/cuda/qsa_decode_attn.cu:87-111,206-237,618-709,716-756`。
- gfx906 build 条件と資料記述: `CMakeLists.txt:59-70,122-138`、`docs/AMD_HIP.md:465-472,508-519`。
