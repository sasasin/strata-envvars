# `STRATA_GFX906_ATTN_QUERY_SWIZZLE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

gfx906 向け QSA batched attention の INT8 K/V 経路で、query の shared-memory 配置を XOR 置換したカーネルを選ぶ opt-in スイッチ。未設定時は通常の chunk kernel を選ぶ。置換は query の LDS 配置とその読み出し位置に適用され、通常の score 計算順序、softmax、value accumulation、merge は変えない（`engine/src/kernels/cuda/qsa_decode_attn.cu:193-200,249-285,301-320`）。

この読み取りと分岐は `STRATA_HIP_GFX906` 定義付きでコンパイルした HIP gfx906 backend に限られる。CMake では `STRATA_HIP_GFX906` は既定 OFF で、ON 時に CUDA ソースを HIP としてコンパイルし、同 macro を定義する（`engine/CMakeLists.txt:92-103,233-237`; `engine/cmake/backends/hip.cmake:6-23,129-135`）。実行時は通常の QSA `qsa_decode_attn_batch` 経路に適用され、verify、MTP、prefill からこの関数へ到達する呼び出しがある（`engine/src/kernels/cuda/qsa_decode_attn.cu:1132-1142`; `engine/src/core/verify.cpp:2580-2589`; `engine/src/core/mtp.cpp:1346-1349`; `engine/src/prefill/prefill.cpp:5567,9470`）。`qsa_decode_attn_step` はこの変数を参照せず、通常の kernel を選ぶ（同 `:1309-1349`）。

## 値と判定

`launch_chunks_batch` と `qsa_decode_attn_slots` に、それぞれ関数ローカル `static const bool` の初期化式があり、`std::getenv` の返す文字列の先頭 1 文字だけを `'1'` と比較する（`engine/src/kernels/cuda/qsa_decode_attn.cu:1043-1046,1174-1177`）。値全体の parse、数値検証、大文字小文字変換、空白除去はしない。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_HIP_GFX906` 定義あり | `getenv` が null なので無効 | 先頭文字が `1`（`1`, `11`, `1anything`） | 空文字、`0`, `0anything`, `true`, `false`, ` 1` |
| `STRATA_HIP_GFX906` 定義なし | この環境変数を読むコードがコンパイルされない | 該当なし | 該当なし |

有効判定は最初の呼び出し時に各関数内で一度だけ行われ、以降その関数のプロセス内設定変更は反映されない。`launch_chunks_batch` と `qsa_decode_attn_slots` は別々の static 値を持つ（同 `:1043-1046,1174-1177`）。優先順位を変える CLI 引数、設定ファイル、別環境変数はこの判定にはない。`STRATA_ATTN_LANECELL` が先に有効なら query swizzle 経路は選ばれない（同 `:1041-1048,1057-1064`）。

## 有効になる条件

- gfx906 compat HIP build であること。CUDA、wave32 HIP、SYCL の同名実装は確認できず、コード上この分岐は `STRATA_HIP_GFX906` で限定される（`engine/src/kernels/cuda/qsa_decode_attn.cu:1043-1048,1065-1069`）。
- `qsa_decode_attn_batch` の通常 kernel 選択（内部の `kernel < 0`）を通ること。テスト用の明示 kernel 指定は環境変数を選択根拠にしない（同 `:1023-1027,1038-1042`）。
- `STRATA_ATTN_LANECELL` が先頭文字 `1` で有効になっていないこと（同 `:993-996,1041-1048`）。
- KV pool が `kv_mode == 1`、すなわち量子化 K と V の INT8 pool であること。他の pool format では選ばれない（同 `:998-1001,1028-1030,1047-1048`）。
- 呼び出し thread の現在 HIP device が gfx906（`gcnArchName` が `gfx906` または `gfx906:` suffix 付き）かつ `warpSize == 64` であること。device 照会失敗や property 取得失敗時は false となり通常 kernel に戻る（同 `:868-893`; `engine/include/strata/kernels/gfx_arch.hpp:15-20`）。

条件を満たさない場合、`qsa_decode_attn_batch` は通常の INT8 chunk kernel を選ぶ。slot-batched 呼び出しでは、条件に合うと `qsa_decode_attn_slots` が `false` を返し、呼び出し元が per-row の `qsa_decode_attn_batch` に切り替える。HIP gfx906 では batch-rows launcher 自体も per-row 経路にする（`engine/src/kernels/cuda/qsa_decode_attn.cu:1093-1116,1174-1179,1259-1269`; `engine/src/core/verify.cpp:2439-2447,2489-2497`）。

## 実行時の詳細

`launch_chunks_batch` は環境値を見て `use_query_swizzle` を決め、その分岐で `attn_chunk_kernel<1, false, true>` を起動する。これは INT8 pool、warp scoring、query-swizzled specialization を表す template 選択である。通常値なら後続の `kv_mode == 1` 分岐から swizzle なしの kernel が起動する。`STRATA_GFX906_ATTN_REDUCE12` が別途先頭文字 `1` かつ文字列長 1 のときだけ、swizzled kernel の score reduction variant も変えるが、この別変数が未設定でも query swizzle 自体は使われる（`engine/src/kernels/cuda/qsa_decode_attn.cu:1065-1093`）。

device ordinal は dispatch ごとに `hipGetDevice` で取り直し、property は呼び出し thread ごとに最後の ordinal 1 件だけ cache する。device 変更時に再取得し、HIP API 失敗時は false として HIP error 状態を消費する。別 thread の cache を共有しない（同 `:871-892`）。環境値の static cache と device property cache は別の仕組みである。

`qsa_decode_attn_slots` は swizzle 条件に合う場合に false を返し、それ自体では swizzled slot kernel を起動しない。verify/MTP 側の呼び出し元はその結果を受け、通常 batch kernel を行単位で呼ぶ（`engine/src/kernels/cuda/qsa_decode_attn.cu:1150-1179`; `engine/src/core/verify.cpp:2435-2447`; `engine/src/core/mtp.cpp:2481-2499`）。`qsa_decode_attn_step` は環境値を読まないため、この設定の対象外（同 `:1309-1349`）。

## ログと測定値

この変数単独ではログを出さない。別変数 `STRATA_GFX906_ATTN_QUERY_SWIZZLE_TRACE` が設定されていると（空文字も含め、値の中身を問わず設定有無で判定）、`launch_chunks_batch` の初回に stderr へ `strata attn-query-swizzle: active=%d nq=%lld cap=%lld kv_mode=%d lane_cell=%d` を thread ごと一度出し、実際に guard を通ったかを `active` で示す（`engine/src/kernels/cuda/qsa_decode_attn.cu:1049-1055`）。kernel 起動後の CUDA/HIP 互換 runtime エラーは `qsa_decode_attn_batch: <error string>` として stderr に出し `exit(1)` する（同 `:1143-1147`）。

Strata の gfx906 qualification 資料は、`n_q=32`、context 65,536、unmasked pages の attention component screen（A/B/B/A、各 run 50 repetitions）の中央値から 14.646806% の throughput gain を報告している。これは限定した component 測定であり、一般の workload の速度向上を示す値ではない（`docs/bench-results/2026-10-08-gfx906-qsa-query-swizzle/README.md:33-41`）。同資料のモデル比較も単一の 65,536 input / 1,024 output 比較として条件を限定している（同 `:5-11`）。

## 根拠

- `engine/src/kernels/cuda/qsa_decode_attn.cu:1023-1055,1065-1093` — batch dispatch、環境値判定、device guard、trace。
- `engine/src/kernels/cuda/qsa_decode_attn.cu:1150-1179,1245-1269,1309-1349` — slot fallback、HIP rows fallback、変数の対象外である step 経路。
- `engine/src/kernels/cuda/qsa_decode_attn.cu:133-160,193-200,249-285,301-320,868-893` — kernel specialization と runtime device 条件。
- `engine/CMakeLists.txt:92-103,233-237`; `engine/cmake/backends/hip.cmake:6-23,129-135` — gfx906 build 条件。
- `engine/src/core/verify.cpp:2435-2447,2485-2497,2579-2589`; `engine/src/core/mtp.cpp:1346-1349,2481-2499`; `engine/src/prefill/prefill.cpp:5567,9470` — 実行時の batch 呼び出し元。
- `docs/AMD_HIP.md:570-580`; `docs/bench-results/2026-10-08-gfx906-qsa-query-swizzle/README.md:13-19,33-41` — gfx906 適用範囲と限定付き qualification 記録。動作の説明は上記ソースコードに基づく。
