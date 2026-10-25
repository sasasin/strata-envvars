# `STRATA_NO_TQ_KERNELS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

CPU の native expert 経路で使う Strata 独自の trellis 量子化（TQ2_T / TQK6 / TQK7、ggml type 144–146）行カーネルを抑止し、対応する `ggml-cpu` の `vec_dot` がある場合にそちらへ切り替えるための設定です。GPU 側の TQ カーネルを切り替える変数ではありません。

通常、CPU pool は native expert の gate/up と down 行を `native_gu_rows()` / `native_down_rows()` に渡します。TQ 型で独自カーネルを選ぶ分岐では、CPU が選んだ scalar / AVX2 / AVX-512 実装で積和を行います（`src/kernels/cpu/pool.cpp:1231-1245`, `src/kernels/cpu/native_expert.cpp:224-228,297-299`, `src/kernels/cpu/tq_cpu.cpp:108-115,183-213`）。

## 値と判定

読み取りは `std::getenv()` と `std::atoi()` です。文字列全体の検証や許容値の一覧はありません。`atoi` の結果が 0 なら独自カーネルは有効、0 以外なら無効要求になります。

| 環境変数の状態・値 | 判定 |
|---|---|
| 未設定 | `atoi` を呼ばず、独自カーネルを有効 |
| 空文字 | `atoi("") == 0` となり、有効 |
| `0`、`00`、`abc` など数値変換結果が 0 | 有効 |
| `1`、`-1`、`2`、`1abc`、` 1` など変換結果が 0 以外 | 無効要求 |

したがって「設定されているか」ではなく、10進整数として `atoi` が返す値で判定します。たとえば `1abc` は先頭の数値部分から 1 となり、無効要求です。無効な数値文字列はエラーにならず、変換結果 0 として扱われます。

## 有効になる条件

- CPU の native expert gate/up または down 行処理が TQ2_T / TQK6 / TQK7 を処理するときに判定されます。ほかの量子化型には影響しません（`src/kernels/cpu/native_expert.cpp:31-37,224-228,297-299`; TQ 型判定は `src/kernels/cpu/tq_cpu.cpp:92-94`）。
- 値が 0 以外でも、`ggml-cpu` がその TQ 型の `vec_dot` を提供していない場合は独自カーネルを使い続けます。型が `GGML_TYPE_COUNT` 以上、trait がない、または `vec_dot` がない場合に fallback が不可能と判定されるためです（`src/kernels/cpu/native_expert.cpp:33-37`）。この条件は upstream ggml のように trellis 型がないビルドでも独自カーネルを維持するためのものです。
- `ggml-cpu` が該当型の `vec_dot` を持つビルドでは、0 以外の値により独自 TQ 行カーネルを通らず、`native_gu_rows()` / `native_down_rows()` 内の `vec_dot` 処理へ進みます（gate/up: `src/kernels/cpu/native_expert.cpp:248-283`、down: `src/kernels/cpu/native_expert.cpp:315-335`）。
- 独自カーネルが有効な場合の ISA 選択は別の `STRATA_TQ_ISA` と実行 CPU 機能で決まり、この変数自体は ISA を選びません（`src/kernels/cpu/tq_cpu.cpp:42-49,96-115`）。AVX 実装が使えない CPU では scalar が選ばれます。

## 実行時の詳細

設定判定は `tq_kernels_enabled()` 内の関数ローカル `static const bool` に保存されます。初回呼び出し時の結果がプロセス内で使われ続け、以後の環境変更は再評価されません（`src/kernels/cpu/tq_cpu.cpp:118-126`）。この関数は TQ 型に対する CPU 行カーネル選択から呼ばれます（`src/kernels/cpu/native_expert.cpp:33-37`）。

変数名や値に対応するログ出力は、読み取り箇所とその呼び出し経路では見つかりません。設定値に関わる処理結果は、独自 TQ カーネルを使うか、利用可能なら `ggml-cpu` の `vec_dot` に進むかです。

## 文書との照合

`docs/GYRO.md:305-309` は、独自 CPU trellis kernels が導入される前は `ggml-cpu` の `vec_dot` を使い、この変数でその経路に戻せると説明しています。現行コードでは `vec_dot` が存在するときはその説明どおりです。ただし、`vec_dot` を提供しない ggml ビルドでは環境変数を指定しても fallback せず、独自カーネルを維持する条件があります。

## 根拠

- 値の読み取りと static cache: `src/kernels/cpu/tq_cpu.cpp:118-126`
- TQ 型の gate/up と down 分岐、および fallback 条件: `src/kernels/cpu/native_expert.cpp:31-37,224-228,248-283,287-299,315-335`
- TQ 型識別、ISA 選択と kernel 実行: `src/kernels/cpu/tq_cpu.cpp:92-115,183-213`
- CPU pool から native expert 行処理への呼び出し: `src/kernels/cpu/pool.cpp:1218-1245`
- 設計資料との照合: `docs/GYRO.md:305-309`
