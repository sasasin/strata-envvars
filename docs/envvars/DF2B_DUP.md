# `DF2B_DUP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`DF2B_DUP` は SYCL の `dflash2_bench` で、指定した名前の kernel launch を追加で実行する診断用設定です。Strata の通常の推論実行を制御する変数ではありません。対象の実行ファイルは SYCL CMake 設定内で独立した `dflash2_bench` executable として定義されています（`sycl/CMakeLists.txt:437-438`）。

## 値と判定

`main()` は `std::getenv("DF2B_DUP")` が null でなければ値全体を `g_dup` にコピーします。数値変換や真偽値判定はありません。launch 時に `g_dup` が空でなく、`DO` マクロの名前と大文字小文字を含めて完全一致したときだけ追加実行します（`sycl/src/kernels/dflash2_bench.cpp:206-209,894-896`）。

| 設定 | 結果 |
|---|---|
| 未設定 | `g_dup` は空のまま。追加 launch なし |
| 空文字 | 空文字がコピーされ、`g_dup.empty()` により追加 launch なし |
| `gemm:qkv` など `DO` の名前と一致 | 下記の `DF2B_DUPN` 条件に従って一致した launch を追加実行 |
| 名前が一致しない文字列、前後に空白のある文字列、大文字小文字だけが異なる文字列 | 追加 launch なし |

受け付ける名前は `quant_rows`, `gemm:fc`, `rms_quant`, `gemm:kp`, `kv_ring`, `embed`, `gemm:akp`, `conv_quant`, `gemm:qkv`, `norm_rope_qk`, `attention`, `gemm:o`, `conv_rms_quant`, `gemm:mkp`, `gemm:gate_up`, `swiglu_quant`, `gemm:down`, `quant_q8_1`, `head`, `topk`, `gemm:hsel`, `select`, `d2h` です。これらは `DO` 呼び出しに書かれた名前で、別名や部分一致は使われません（`sycl/src/kernels/dflash2_bench.cpp:210-256`）。

追加回数は別変数 `DF2B_DUPN` が決めます。これは `envi("DF2B_DUPN", 1)` で読み、未設定または空文字なら 1、それ以外は `std::atoi` の結果です（`sycl/src/kernels/dflash2_bench.cpp:56,896`）。`DO` は元の launch を一度実行した後、`DF2B_DUPN == 1` または `g_layer == 0` の場合に限り、ループを `DF2B_DUPN` 回実行します（同 `:209`）。そのため値が 1 なら各一致 launch は合計 2 回、正の値が 1 より大きければ条件を満たす launch は元の 1 回に指定回数を加えた回数、0 または負値なら追加分は 0 回です。`atoi` は文字列全体の妥当性を検証せず、先頭から数値として読める部分を変換します（例: `2tail` は 2、`tail2` は 0）。

## 有効になる条件

- `dflash2_bench` の `bench`（引数なしの場合の既定値）、`small`、または `ctx` 経路で `DO` を通る launch が対象です。`bench` と `small` は `record_round()` を呼び、`ctx` は `record_context()` を呼びます。`record_round()` は `record_context()` と `record_block()` の両方を呼びます（`sycl/src/kernels/dflash2_bench.cpp:259-272,486,739-746,825-833,894-901`）。
- `test`, `gemm`, `attn`, `dp4a`, `bubble`, `poison`, `poison2` はそれぞれ別の経路に分岐します。`test` の検証処理では `DO` を通らず、他の列挙経路も `record_round()` / `record_context()` を呼ばないため、この変数による追加 launch はありません（同 `:359-479,894-901`）。
- `DF2B_DUPN=1` の場合は現在の layer 値に関係なく一致した launch を追加実行します。1 より大きい値の場合は `g_layer == 0` のときだけ追加します。`g_layer` は `record_block()` の layer loop で設定され、他に初期値 0 から戻す処理はありません（同 `:208-209,230-235`）。したがって `record_context()` が実行されるときの判定は直前の値に依存します。最初の呼び出し前は 0、`record_block()` の loop 後は最終 layer の値が残ります。
- OS や別 backend による条件分岐はこの読み取り・判定箇所にはありません。SYCL 用ベンチのビルドと起動が前提です。

## 実行時の詳細

値はプロセス起動時に `main()` で一度読み、グローバル文字列 `g_dup` に保持します。実行中に環境変数を変更して再評価するコードはありません（`sycl/src/kernels/dflash2_bench.cpp:206,894-901`）。

`DO(name, call)` はまず通常の `call` を一度実行し、条件が合えば同じ `call` を追加実行してから `D.stamp(name)` を一度呼びます。重複分は同じキューに投入されますが、stamp は追加分ごとには作られません（同 `:103,209`）。このため profile の名前付き計測区間には追加 launch の時間が含まれます。対象名と `DF2B_DUPN` の範囲チェックはなく、値が既知の kernel 名でも実行モードが対象経路を通らなければ何も起きません。

この変数専用のログ、警告、終了コード分岐はありません。通常の `dflash2_bench` 出力（bench の wall-time や profile 値など）は追加 launch を含む計測になります（同 `:486-589`）。ソース上で無効値のエラー表示や追加 launch 失敗時の専用処理は確認できません。

## 根拠

- 環境値の読み込み、保持、完全一致と追加実行: `sycl/src/kernels/dflash2_bench.cpp:206-209,894-896`
- `DF2B_DUPN` の `getenv` / `atoi`、未設定・空文字 fallback: `sycl/src/kernels/dflash2_bench.cpp:56,896`
- launch 名と使用箇所: `sycl/src/kernels/dflash2_bench.cpp:210-256`
- profile stamp の位置: `sycl/src/kernels/dflash2_bench.cpp:103,209`
- ベンチ経路とモード分岐: `sycl/src/kernels/dflash2_bench.cpp:259-272,486-589,739-746,825-833,894-901`
- standalone target の定義: `sycl/CMakeLists.txt:437-438`
