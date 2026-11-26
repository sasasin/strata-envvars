# `QA_DUMP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`QA_DUMP` は、合成入力で prompt attention を比較・計測する `qsa_prompt_attn_parity` に、Strata の prefill が記録した QSA 選択セルを読み込ませる診断用フックです。ファイル中の選択 ID でベンチマーク側の合成選択を置き換え、隣接 query 間で重なるセル数を出力します。通常の `strata` エンジンやサーバーの選択処理を切り替える環境変数ではありません。CUDA、HIP、SYCL の parity 実装に読み取り箇所があります（`engine/src/kernels/qsa_prompt_attn_parity.cpp:151-182`, `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:202-233`）。

## 値と判定

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA / HIP parity 実行ファイル、SYCL parity 実行ファイル | 読み込みを行わず、合成生成した選択 ID を使う | `getenv("QA_DUMP")` が非 `nullptr` なら値全体を `fopen(path, "rb")` のパスに渡す。`/tmp/qsa.bin` など、読み取り可能なファイルを開けるパス | 空文字も「設定あり」と判定されるが、空のパスを開けず `QA_DUMP: cannot open` で終了コード 2。存在しない・読めないパスも同じ。値を真偽値・数値・先頭文字として解析しない |

開いたファイルは、4 個の `int32`（layer, `pos0`, query 数 `T`, `cap`）と `T*cap` 個の `int32` 選択 ID が連なる形式として走査されます。`QA_LAYER` が未設定なら layer `3`、設定されていれば `std::atoi` の結果を使います。従って `QA_LAYER=""` や非数値文字列は `0`、`"3tail"` は `3` になり、文字列全体の妥当性検査はありません。ファイル内のレコードは layer、`T == nq`、`pos0 + T == ctx`、`cap` がすべて一致する必要があります。条件に合う複数レコードがあれば最後のものを選びます（`engine/src/kernels/qsa_prompt_attn_parity.cpp:153-167`, `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:204-218`）。

## 有効になる条件

- 対象の parity バイナリがビルドされ、実行される必要があります。CUDA ターゲットは `STRATA_ENABLE_CUDA` と `STRATA_BUILD_TESTS` または `STRATA_PARITY_PROMPT_ATTN` が条件です（`engine/cmake/strata_gpu_engine.cmake:137-143`）。SYCL は `qsa_prompt_attn_parity` ターゲットとして登録されます（`engine/sycl/CMakeLists.txt:583-588`）。HIP は HIP 構成中の `hip_prompt_attn_wmma` として登録されます（`engine/cmake/strata_gpu_engine.cmake:586-588,702-710`）。
- CLI の `context` と `queries`（既定値 32768 / 2048）はそれぞれ `ctx` と `nq` となり、ファイルのレコード一致条件に使われます。`QA_DUMP` はこれらの CLI 値を変更しません。parity の各 `run()` 呼び出しで照合するため、複数の context/query 組を連続実行する呼び出しでは、それぞれに一致するレコードが必要です（`engine/src/kernels/qsa_prompt_attn_parity.cpp:474-492`）。
- `QA_LAYER` で対象 layer を選べます。未設定時は 3 です。ファイルを開けても一致するレコードがなければ `QA_DUMP: no record for layer %d, T %lld, ctx %lld` を stderr に出して終了コード 2 になります。
- `QA_SAME`（CUDA/HIP）や `QA_SAME` / `QA_BLOCK4`（SYCL）が先に合成選択 ID を作っても、ダンプ読み込みが成功すると ID 配列を読み込んだ値で上書きします。一方、query ごとの選択幅を持つ `steps` は合成入力から作られたままです（`engine/src/kernels/qsa_prompt_attn_parity.cpp:95-106,128-149,151-167`; `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:129-145,179-200,202-218`）。
- Strata の通常エンジンやサーバーモードが `QA_DUMP` を読む箇所はありません。エンジン側がファイルを作る設定名は別の `STRATA_QSA_DUMP` です（CUDA: `engine/src/prefill/prefill.cpp:5507-5529`; SYCL: `engine/sycl/src/prefill/prefill.cpp:3820-3843`）。

## 実行時の詳細

環境変数は関数内 static に保存されず、`run()` ごとに `getenv` されます。値の取得後、バイナリファイルを先頭から読み、各レコードの header を照合して payload を seek で飛ばします。一致レコードの選択 ID を `ids` に読み込み、GPU 計算へ渡す配列に反映します。query 幅の `steps`、query、K/V pool などは parity プログラムが生成したままで、ダンプが差し替えるのは選択 ID です（`engine/src/kernels/qsa_prompt_attn_parity.cpp:95-106,151-182,184-202`; SYCL: `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:129-145,202-233,235-252`）。

未設定、ファイルを開けない場合、一致レコードがない場合の各回の扱いは上記の通りです。一致 header はあるが ID payload を所定数読めない場合も終了コード 2 ですが、この経路には専用のエラーメッセージがありません（CUDA: `engine/src/kernels/qsa_prompt_attn_parity.cpp:155-166`; SYCL: `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:206-217`）。

## ログと測定値

開けない場合は stderr に `QA_DUMP: cannot open`、一致レコードがない場合は stderr に `QA_DUMP: no record for layer %d, T %lld, ctx %lld` を出し、どちらも `exit(2)` します。成功すると `grp` が 2、4、8、16 の各場合について、選択 ID の隣接 query グループで重複を除いたセル数を計算し、stdout に `QA_DUMP overlap: %d-query groups read %.2fx the cells of one query (%.1f%% of %d x)` を出します。これは parity プログラムが選択配列から計算する値です（CUDA: `engine/src/kernels/qsa_prompt_attn_parity.cpp:168-182`; SYCL: `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:219-233`）。該当する Strata 資料に、この環境変数による性能測定値はありません。

## 根拠

- CUDA / HIP 読み取り、レコード選択、失敗経路、重複率出力: `engine/src/kernels/qsa_prompt_attn_parity.cpp:151-182`
- SYCL 読み取り、レコード選択、失敗経路、重複率出力: `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:202-233`
- parity CLI の context/query と反復経路: `engine/src/kernels/qsa_prompt_attn_parity.cpp:474-492`; SYCL: `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:474-493`
- 入力 dump の header / selection payload を書く処理: `engine/src/prefill/prefill.cpp:5507-5529`; SYCL: `engine/sycl/src/prefill/prefill.cpp:3820-3843`
- parity ターゲットのビルド条件: `engine/cmake/strata_gpu_engine.cmake:137-143,586-588,702-710`; SYCL: `engine/sycl/CMakeLists.txt:583-588`
