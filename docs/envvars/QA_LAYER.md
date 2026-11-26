# `QA_LAYER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`QA_LAYER` は QSA prompt-attention parity 診断プログラムが `QA_DUMP` の記録から選択セル列を読む際、対象 layer 番号を指定する変数です。通常の `strata` engine、サーバー、モデル生成処理では読み取られません。CUDA/HIP 版と SYCL 版の `qsa_prompt_attn_parity` だけで使われ、選んだ記録のセル列が診断用の比較計算に渡されます。モデルの layer 動作や生成 token を制御する設定ではありません（CUDA/HIP: `engine/src/kernels/qsa_prompt_attn_parity.cpp:151-183,207-218`; SYCL: `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:202-234`）。

## 値と判定

両実装とも `QA_DUMP` が NULL でない場合に限り `QA_LAYER` を読み、設定有無を `std::getenv` で確認した後、値を `std::atoi` で整数化します。変換後の値は dump の layer 番号との整数一致に使われます。unset は `3`、空文字は `atoi("")` により `0` です。文字列全体や範囲の検証、clamp はありません。`atoi` が数値として読める先頭部分を使うため、例えば `3tail` は `3`、`0anything` と `true` は `0`、`-1` は `-1` として照合されます。正数の上限・下限はコードで定めておらず、実際に一致する dump 記録があるかで選択可否が決まります（CUDA/HIP: `engine/src/kernels/qsa_prompt_attn_parity.cpp:153-164`; SYCL: `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:204-215`）。

| 実行経路 | unset | 設定例・判定 | 照合に使われる値 |
|---|---:|---|---|
| CUDA/HIP `qsa_prompt_attn_parity`、SYCL `qsa_prompt_attn_parity`（`QA_DUMP` 設定時） | `3` | `3`, `3tail` → 3。空文字、`0`, `0anything`, `true` → 0。`-1` → -1 | 整数化後の layer 番号 |
| 上記以外、または `QA_DUMP` unset | 読まれない | `QA_LAYER` の値は参照されない | なし |

`QA_DUMP` が空文字でも NULL ではないため `QA_LAYER` を評価した後に空のパスを開こうとし、open 失敗で終了します。`QA_DUMP` と CLI の context / queries / reps 引数の間に優先順位はありません。CLI 引数は dump 記録との他の照合条件（`T`, `pos0 + T`, `cap`）を決めます（CUDA/HIP: `engine/src/kernels/qsa_prompt_attn_parity.cpp:153-164,364-366`; SYCL: `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:204-215,474-477`）。

## 有効になる条件

- `QA_DUMP` に読み取り可能な parity dump ファイルのパスが設定されている必要があります。ファイルは `fopen(..., "rb")` で開かれます。
- 指定 layer の記録があり、その記録の query 数が今回の `nq` に等しく、`pos0 + T` が `ctx` に等しく、capacity が今回の `cap` に等しい必要があります。走査中に一致する記録が複数あれば最後の記録の位置を使います（CUDA/HIP: `engine/src/kernels/qsa_prompt_attn_parity.cpp:155-166`; SYCL: `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:206-218`）。
- CUDA 版の実行ファイルは CUDA が有効で、`STRATA_BUILD_TESTS` または `STRATA_PARITY_PROMPT_ATTN` が有効な build で作られます。HIP 版の同じソースはテスト build 側の `hip_prompt_attn_wmma` target です（`engine/cmake/strata_gpu_engine.cmake:137-143,702-710`）。
- SYCL 版は `engine/sycl/CMakeLists.txt` の `qsa_prompt_attn_parity` test target です（`engine/sycl/CMakeLists.txt:583-588`）。いずれも通常の engine / server target ではありません。
- `QA_DUMP` がない場合や上記の記録条件を満たさない場合、`QA_LAYER` に有効な数値があっても選択セル列の読み込みは行われません。

## 実行時の詳細

`run()` が合成入力と通常の選択列を用意した後、`QA_DUMP` の有無を調べます。その分岐内で `QA_LAYER` を整数化し、dump を先頭から走査して条件に合う記録を探します。一致記録が見つかると記録内の `T * cap` 個の整数を `ids` 配列へ読み込み、重なり率を出力した後、CUDA/HIP と SYCL の各 parity kernel・FP64 参照計算に同じ `ids` を渡します（CUDA/HIP: `engine/src/kernels/qsa_prompt_attn_parity.cpp:95-107,153-183,207-230,241-284`; SYCL: `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:129-160,204-234,315-370`）。

値は `run()` のこの箇所で都度読み、関数内 static cache はありません。`main()` は複数の形式や context で `run()` を呼ぶため、各呼び出しで dump 分岐に入れば再評価されます。CLI の context / queries / reps は `main()` の引数から設定され、環境変数値を上書きしません（CUDA/HIP: `engine/src/kernels/qsa_prompt_attn_parity.cpp:346-376`; SYCL: `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:455-494`）。

## ログと測定値

`QA_LAYER` 自体の有効・無効ログはありません。`QA_DUMP` を開けない場合は stderr に `QA_DUMP: cannot open` を出して終了コード 2、一致記録がない場合は stderr に `QA_DUMP: no record for layer %d, T %lld, ctx %lld` を出して終了コード 2 です。記録の読み込み後は stdout に `QA_DUMP overlap: %d-query groups read %.2fx the cells of one query (%.1f%% of %d x)` を group 2, 4, 8, 16 ごとに出し、続く parity 比較は `PASS` / `FAIL` と所要時間・誤差等を出力します（CUDA/HIP: `engine/src/kernels/qsa_prompt_attn_parity.cpp:155-166,168-182,333-342`; SYCL: `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:206-217,219-233,432-451`）。この調査では build や GPU 実行をしておらず、測定値はありません。

## 根拠

- CUDA/HIP の値読み取り・dump 記録照合・失敗経路: `engine/src/kernels/qsa_prompt_attn_parity.cpp:151-183`。
- CUDA/HIP の診断 target 条件: `engine/cmake/strata_gpu_engine.cmake:137-143,702-710`。
- SYCL の値読み取り・dump 記録照合: `engine/sycl/src/kernels/qsa_prompt_attn_parity.cpp:202-234`。
- SYCL の診断 target 登録: `engine/sycl/CMakeLists.txt:583-588`。
- 候補一覧の `QA_LAYER` は索引にのみ記載されていました（strata-envvars `docs/envvars/000_envvers.md:675`）。Strata の補助ドキュメントに `QA_LAYER` の説明は見つかりませんでした。
