# `STRATA_GFX906_ATTN_QUERY_SWIZZLE_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

gfx906 HIP ビルドで QSA の batched attention chunk pass が呼ばれたとき、query-swizzle 経路が実際に選択されたかを示す診断行を `stderr` に出す。値は `getenv(...) != nullptr` で判定されるため、この変数自体は kernel の選択や計算を変えない。kernel 選択を有効にする別設定は `STRATA_GFX906_ATTN_QUERY_SWIZZLE` であり、trace は選択結果を `active=0` または `active=1` として記録するだけである（`engine/src/kernels/cuda/qsa_decode_attn.cu:1043-1055`）。

## 値と判定

`launch_chunks_batch` 内の関数ローカル `static const bool` に `std::getenv` の null 判定結果を保存する。値の変換・文字列比較・数値変換はなく、unset だけが無効。空文字、`0`、`false`、`0anything` を含め、環境変数が設定されていれば有効になる。大文字小文字、空白、数値範囲の検査もない（`engine/src/kernels/cuda/qsa_decode_attn.cu:1049-1055`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_HIP_GFX906` を定義した gfx906 HIP compat build | ログを出さない | 空文字、`0`、`false`、任意の文字列 | unset のみ |
| それ以外の build | このコードはコンパイルされず、読み取りもログもない | 該当なし | 該当なし |

このコードは build macro `STRATA_HIP_GFX906` の `#if` 内にあり、CMake の gfx906 HIP toolchain が同 macro を定義する。通常の CUDA や wave32 HIP build ではこの trace 処理は含まれない（`engine/src/kernels/cuda/qsa_decode_attn.cu:8-10,1043-1056`; `engine/cmake/backends/hip.cmake:6-23`）。

## 有効になる条件

- 実行バイナリが `STRATA_HIP_GFX906` 付きでビルドされていること。CMake では `STRATA_HIP_GFX906` が gfx906 compat toolchain を選ぶ（`engine/CMakeLists.txt:97-104,233-238`）。
- `qsa_decode_attn_batch` が `n_q > 0` で呼ばれ、形状・必須バッファ検査を通過して `launch_chunks_batch` に到達すること。無効な形状などは trace 判定より前に `qsa_decode_attn_batch: unsupported geometry or missing buffers` を出して終了する（`engine/src/kernels/cuda/qsa_decode_attn.cu:1132-1142`）。
- trace 行の出力には、この変数が unset でないことだけが必要。query-swizzle が選ばれるためには、さらに次の条件が必要である（`engine/src/kernels/cuda/qsa_decode_attn.cu:1043-1054`）。
  - `STRATA_GFX906_ATTN_QUERY_SWIZZLE` が設定され、その値の先頭文字が `'1'`。文字列全体の検査はなく、たとえば `1anything` もこの判定を通る。
  - `STRATA_ATTN_LANECELL` による lane-cell 経路が無効。lane-cell 側はその値の先頭文字が `'1'` のとき有効になる（`engine/src/kernels/cuda/qsa_decode_attn.cu:992-996,1041-1048`）。
  - KV pool が `kv_mode=1`、すなわちこの関数の判定上 INT8 K/V であること。FP16、Q4、K8V4 は対象外（`engine/src/kernels/cuda/qsa_decode_attn.cu:1026-1029`）。
  - 呼び出し側が環境選択 kernel を使うこと。`qsa_decode_attn_batch` は `kernel=-1` で chunk pass を呼ぶ（`engine/src/kernels/cuda/qsa_decode_attn.cu:1023-1027,1140-1142`）。
  - 呼び出しスレッドの HIP device が `gfx_arch_is(..., "gfx906")` を満たし、`warpSize == 64` であること。device 取得または property 取得に失敗した場合は `false` となり、query-swizzle は選ばれない（`engine/src/kernels/cuda/qsa_decode_attn.cu:868-893`）。
- trace 変数は query-swizzle 有効化変数に従属しない。trace だけ設定した場合もログは出て、条件を満たさなければ `active=0` となる。逆に query-swizzle だけを設定し trace が unset なら、この診断行は出ない（`engine/src/kernels/cuda/qsa_decode_attn.cu:1043-1055`）。
- `STRATA_GFX906_ATTN_REDUCE12` が先頭 `'1'` かつ直後が終端文字のとき、query-swizzle が既に選ばれた経路内で別の reduce12 kernel variant を選択する。これはこの trace 変数の判定とは独立している（`engine/src/kernels/cuda/qsa_decode_attn.cu:1065-1093`）。

## 実行時の詳細

環境値はプロセス起動時ではなく、`launch_chunks_batch` が最初に実行されたときに関数ローカル static として一度評価される。以後プロセス実行中に環境値を変更しても、trace の有効・無効は更新されない。判定が有効なら `static thread_local` の `query_swizzle_said` により、診断行はホストスレッドごとに最初の該当呼び出しで一度だけ出る。したがって複数ホストスレッドから呼ばれれば各スレッドで一行ずつ出る（`engine/src/kernels/cuda/qsa_decode_attn.cu:1049-1055`）。

この診断箇所は `qsa_decode_attn_batch` の chunk pass にある。QSA prefill は batch ごとにこの関数を呼び、MTP draft attention も split attention が処理しないときに呼ぶため、これらの実行で診断対象になりうる（`engine/src/prefill/prefill.cpp:5558-5569,9466-9472`; `engine/src/core/mtp.cpp:1346-1349`）。trace は CLI 引数やサーバーモードで上書きされず、値を読み直すコードもない。

## ログと測定値

変数が有効で、そのホストスレッドが最初の `launch_chunks_batch` に到達すると、次の形式を `stderr` に出す。書式文字列は実装どおりで、`active` は swizzle 経路選択結果、`nq` は query 数、`cap` は cap、`kv_mode` は pool 形式、`lane_cell` は lane-cell 選択状態を表す。

```text
strata attn-query-swizzle: active=%d nq=%lld cap=%lld kv_mode=%d lane_cell=%d
```

trace 専用の警告・エラー・終了処理はない。通常の batch 関数では chunk/merge launch 後に runtime error があると `qsa_decode_attn_batch: %s` を `stderr` に出して `exit(1)` するが、これは trace の値により発生する処理ではない（`engine/src/kernels/cuda/qsa_decode_attn.cu:1051-1055,1140-1147`）。この文書では trace の効果を示す Strata の測定値は記載しない。

## 根拠

- `engine/src/kernels/cuda/qsa_decode_attn.cu:868-893` — gfx906 / wave64 の runtime device 判定と cache。
- `engine/src/kernels/cuda/qsa_decode_attn.cu:992-996,1023-1055` — lane-cell、KV mode、swizzle 条件、trace の読み取り・ログ。
- `engine/src/kernels/cuda/qsa_decode_attn.cu:1065-1093,1132-1147` — swizzle kernel 選択、呼び出し条件、通常の失敗経路。
- `engine/cmake/backends/hip.cmake:6-23`; `engine/CMakeLists.txt:97-104,233-238` — gfx906 HIP build macro と toolchain。
- `engine/src/prefill/prefill.cpp:5558-5569,9466-9472`; `engine/src/core/mtp.cpp:1346-1349` — runtime からの batch 関数呼び出し例。
