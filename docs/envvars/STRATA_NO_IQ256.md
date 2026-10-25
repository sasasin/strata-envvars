# `STRATA_NO_IQ256`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

native pack の CPU expert 計算で、i-quant の gate/up 行に使う AVX2 multi-token kernel を無効にします。無効化すると、その経路の代わりに ggml-cpu の `vec_dot` が各 token の行を計算します。CUDA/HIP/SYCL の GPU kernel を切り替える変数ではなく、native pack を処理する CPU 側の経路に作用します。

## 値と判定

実装は `std::getenv("STRATA_NO_IQ256") != nullptr` で設定有無だけを判定し、値を parse しません。

| 環境の状態 | AVX2 i-quant gate/up 経路 |
|---|---|
| 未設定 | 他の条件を満たせば利用可能 |
| 設定済み（`1`、`0`、空文字、その他の文字列を含む） | 無効。対象の行は ggml-cpu の `vec_dot` に fallback |

`native_gu_rows()` 内の判定は関数内 `static const bool` に保存されるため、その判定が初めて実行された後にプロセス環境を変更しても dispatch は変わりません。起動時の診断ログ側は別に `getenv()` を確認します。

## 有効になる条件

変数が未設定でも、AVX2 が使える CPU であることが必要です。さらに AVX-512 対応 CPU ではこの dispatch の条件上 AVX2 経路を選ばず、対象形式の AVX-512 kernel が優先されます。AVX2 kernel が対象とする gate/up 型（`iq256_supported()` が列挙する GGML type 16, 17, 18, 21, 22, 23）であること、multi-token 数 `nt` が `STRATA_IQ_MT_MIN` の閾値以上であることも必要です。同閾値は未設定時 2、設定時は `atoi` の結果で、空文字や数値に変換できない文字列は 0、負数もそのまま使われます。したがって、たとえば 0 以下なら正の `nt` は閾値を満たします。これらの条件を満たさない行は、別に有効な AVX1 kernel か ggml-cpu 経路に進みます。

相互作用として、`STRATA_IQ_MT_MIN` が未設定で `STRATA_IQ3S_MT1` が設定されている場合の IQ3_S 用 one-token 条件も、本変数が未設定であることを要求します。本変数を設定するとその特例も無効になります。

この変数は `native_down_rows()` の選択には使われません。down 行の IQ4_NL multi-token kernel は `STRATA_NO_IQ4NL`、Q5_1/Q8_0 の KQ kernel は `STRATA_KQ256` など、別の条件で選択されます。

## 実行時の詳細

native pack は `--native` 経路で expert を CPU 側の native layout として扱います。CPU pool が native expert の gate/up 行を処理するとき `native_gu_rows()` を呼びます。そこで AVX-512 条件、AVX2 条件、AVX1 条件を順に調べ、対象形式かつ token 数が閾値以上なら対応する multi-token kernel に渡します。`STRATA_NO_IQ256` が設定済みの場合は AVX2 条件が偽になり、最後の ggml-cpu `vec_dot` のループで token ごとに dot product を行い、SwiGLU の値を出力します。

AVX-512 非対応 CPU で native pack を起動すると stderr に `this CPU has no AVX-512: the expert kernels run on ...` という診断が出ます。AVX2 対応 CPU では、変数未設定時の分岐名は `AVX-2`、設定時は `ggml-cpu vec_dot (STRATA_NO_IQ256 set)` です。AVX2 自体に非対応の CPU では no-AVX2 側のメッセージになり、この変数だけで AVX2 を使えるようにはなりません。

## 根拠

- `src/kernels/cpu/native_expert.cpp:143-158` — AVX2 条件と値の判定、AVX2 kernel の dispatch。
- `src/kernels/cpu/native_expert.cpp:179-194,218-229` — CPU 世代、対応形式、multi-token 閾値の条件と ggml-cpu fallback。
- `src/kernels/cpu/native_expert.cpp:124-140` — `STRATA_IQ_MT_MIN` の既定値と `atoi` 判定、および IQ3_S の追加条件にも本変数の設定有無を使用。
- `src/kernels/cpu/native_expert.cpp:44-46` — AVX2 kernel が対象とする GGML type。
- `src/kernels/cpu/pool.cpp:705-718` — CPU pool から gate/up と down の native row 関数を呼び分け。
- `src/program/generate.cpp:2898-2907` — native pack の AVX-512 非対応 CPU 向け診断と本変数による表示分岐。SYCL 側にも同じ診断がある（`sycl/src/program/generate.cpp:2628-2634`）。
- `src/program/generate.cpp:2803-2818` — native pack の初期化と native expert 形式チェック。
