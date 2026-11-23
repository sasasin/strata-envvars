# `STRATA_CONVERT_THREADS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の opt-in split engine にある GGUF ローダーのロード時テンソル変換を、何本の worker thread で並行処理するか指定する。1 は旧来の逐次ループ、それ以外の正の数は指定数を上限として変換 job を並列に処理する。対象は `Gguf::convert_small_tensors()` が必要と判断した変換だけで、通常のモデル読み込み全般や推論中の thread 数を変える設定ではない（`engine/src/split/src/gguf.cpp:110-117,139-167,187-197`）。

## 値と判定

`std::getenv` で設定有無を見て、設定値は `std::atoi` で変換する。未設定、空文字、数値として先頭を読めない文字列、0、負数はいずれも `n <= 0` となり、hardware concurrency に基づく既定値へフォールバックする。`atoi` のため、先頭の空白と符号は許容され、先頭の10進整数の後ろは検査されない（例: `"  +3tail"` は 3）。全体の数値妥当性、大文字小文字、上限超過のエラーは検査しない。`atoi` の int 範囲外入力はコードで検証されず、結果を移植可能に定められない。

| 条件 | unset | 有効になる値（例） | フォールバックになる値（例） |
|---|---|---|---|
| `convert_small_tensors()` が変換処理へ進む場合 | `min(8, max(1, hardware_concurrency()))` 本を基準に、job 数以下へ制限 | 正の `atoi` 結果を job 数以下に制限（`1` は逐次、`3` は最大3本、`100` も job 数が上限） | `""`、`"0"`、`"-2"`、`"words"` は既定値へ。`"3tail"` は3として扱う |

最終的な本数は `max(1, min(n, jobs))`。ただし変換 job が0件なら結果は0となり、`n_threads <= 1` の分岐で空の worker loop が一度実行されるだけで、thread は生成されない（`engine/src/split/src/gguf.cpp:112-117,167-188`）。

## 有効になる条件

- `STRATA_BUILD_SPLIT` で有効化する split engine のビルドが必要。CMake はこれを既定で OFF とし、split engine は CUDA または HIP の構成でビルドされる（`engine/src/split/CMakeLists.txt:1-5,20-27`）。
- `Gguf` のロード時に、テンソル型のいずれかが `T_IQ2_S`、`T_IQ3_XXS`、`T_IQ3_S`、`T_Q2_0` である必要がある。この判定に該当しない GGUF は変換処理を即時に抜け、環境変数も読み取らない（`engine/src/split/src/gguf.cpp:139-144`）。
- 該当型があれば、変換 job は `T_Q2_0` の Q4_0 への詰め替え、または `wanted_type()` が指定する Q8_0/F32 への変換から作られる。同じ型のままのテンソルと `wanted_type()` が対象外にするテンソルは job にならない（`engine/src/split/src/gguf.cpp:154-166`; `engine/src/split/src/tensor_convert.hpp:242-257`）。
- この名前を読むのは split engine の `gguf.cpp` だけで、CUDA/HIP 間に別の判定はない。通常 engine、他の GGUF loader、CLI 引数や別環境変数による優先・上書きはこの読み取り箇所にはない（`engine/src/split/src/gguf.cpp:112-117`; `engine/src/split/CMakeLists.txt:1-7`）。

## 実行時の詳細

`Gguf` コンストラクターは shard を読み込んだ後、`convert_small_tensors()` を呼ぶ（`engine/src/split/src/gguf.cpp:119-133`）。変換対象がある場合に限り、job と個別の出力 vector を map 順に先に作ってから `convert_threads()` が環境を読み取る。各 worker は atomic な job index を取得して別々の job/output を処理し、全 thread の join 後に例外を再送出する。値は関数内に cache されず、変換を行う `Gguf` の構築ごとに読み取る。実行中に環境を変更した場合の再評価はなく、次の `Gguf` 構築で読み直される（`engine/src/split/src/gguf.cpp:112-117,119-133,139-194`）。

変換後の tensor はファイル shard ではなくメモリ上の出力を指す。job の処理順と格納先は thread 数にかかわらず先に決まり、実装コメントは出力 bytes が thread 数に依存しないと記している（`engine/src/split/src/gguf.cpp:145-167`; `engine/src/split/src/tensor_convert.hpp:259-282`）。

## ログと測定値

変換が成功し、変換 job がある場合、stderr に `gguf: %d dense/small tensors converted to Q8_0/F32 at load (the file's routed experts keep their types)` を出す。対象外の GGUF、job がない場合、変換例外の場合はこの成功ログに到達しない（`engine/src/split/src/gguf.cpp:139-144,194-197`）。

変換処理の例外は `Gguf` 構築元へ再送出される。`sfnx` はロード失敗時に stdout へ `ERR <理由>`、stderr へ `sfnx: failed: <理由>` を出して終了コード1で終了する（`engine/src/split/tools/sfnx.cpp:1097-1102,1123-1135`）。`fnx_run` は stderr に `fnx_run: <理由>` を出し終了コード1を返す（`engine/src/split/tools/fnx_run.cpp:1364-1373`）。

ソースコメントには、ISTA IQ3_S set の cold load 122秒中、変換1 thread が62秒だったという例があるが、同じ箇所に記録された例であり、一般的な速度差を示す測定としては扱わない（`engine/src/split/src/gguf.cpp:145-147`）。

## 根拠

- 読み取り、値の既定値・clamp、変換 job と thread 処理: `engine/src/split/src/gguf.cpp:110-117,139-197`
- GGUF コンストラクターからロード時変換への呼び出し: `engine/src/split/src/gguf.cpp:119-133`
- 変換対象形式と出力先型: `engine/src/split/src/tensor_convert.hpp:242-282`
- split engine のビルド条件: `engine/src/split/CMakeLists.txt:1-27`
- ロード失敗の表示と終了: `engine/src/split/tools/sfnx.cpp:1097-1102,1123-1135`; `engine/src/split/tools/fnx_run.cpp:1364-1373`
