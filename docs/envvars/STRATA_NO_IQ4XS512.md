# `STRATA_NO_IQ4XS512`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

CPU native expert の IQ4_XS gate/up 行に使う、AVX-512 基準の行カーネルを無効にする設定です。`src/kernels/cpu/native_expert.cpp` の環境変数読み取りは1箇所です。この分岐に到達するのは native expert CPU 行処理であり、通常の GPU 側 IQ4_XS カーネルを直接切り替える設定ではありません。CPU pool の mode 5 では native gate/up 行の dispatch から呼び出されます（`src/kernels/cpu/pool.cpp:1231-1237`）。

## 値と判定

| 環境値 | 判定 |
|---|---|
| 未設定 | 他の条件も満たせば AVX-512 基準の IQ4_XS 行カーネルを候補にする |
| 設定あり（空文字を含む） | 無効化する。値の文字列・数値・先頭文字は検査しない |

実装は `std::getenv(...) == nullptr` で設定有無だけを見ます。したがって `=0`、`=false`、空文字も設定済みとして無効化します。無効な値という区分や parse、clamp はありません（`src/kernels/cpu/native_expert.cpp:517-520`）。

## 有効になる条件

変数が未設定でも、次の条件を満たさなければこの AVX-512 基準カーネルは使われません。

- CPU が `cpu_vnni_ok()` を満たし、`STRATA_NO_IQ512` も未設定である。共通の `avx512` 判定は関数内 static に保存されます（`src/kernels/cpu/native_expert.cpp:459-463`）。
- 対象の gate/up 型が IQ4_XS（`f.gu_type == 23`）、token 数が `STRATA_IQ4XS512_MIN` 以上、形式に tail がなく、リンク中の ggml-cpu との初回照合が一致する（同:517-522）。
- native expert CPU の gate/up 行処理に入る。CPU pool では mode 5 の native 行処理が該当します（`src/kernels/cpu/pool.cpp:1231-1237`）。native expert 自体のビルド機能は CMake の `STRATA_NATIVE_EXPERTS` オプション（既定 ON）で登録されます（`CMakeLists.txt:176,2184-2189`）。

無効化したとき、または上記条件に届かないときは後続 dispatch に進みます。token 数が `STRATA_IQ_MT_MIN`（既定 2）以上で、`STRATA_NO_IQ256` が未設定なら IQ4_XS 対応の AVX2 行カーネルが候補になります。そうでなければ ggml-cpu の `vec_dot` を token ごとに gate/up 行へ適用する経路です（`src/kernels/cpu/native_expert.cpp:435-441,567-597,620-631`）。よって、この変数を設定すること自体が常に ggml-cpu の dot へ固定するわけではありません。

## 実行時の詳細

`STRATA_NO_IQ4XS512` は `native_gu_rows_impl` の関数内 `static const bool` 初期化時に一度だけ読み取られます。初期化はそのコード位置に初めて到達したときです。テンプレート実装には `Default` と `WindowInvariant` の別インスタンスがあります。各インスタンスで初期化された後にプロセス環境を書き換えても、そのインスタンスの判定は更新されません（`src/kernels/cpu/native_expert.cpp:454-455,517-520,707-719`）。CLI 引数による上書きや、この変数を子プロセスへ転送する処理は見つかりませんでした。

カーネル候補の追加適用条件として `STRATA_IQ4XS512_MIN` は `atoi` で読み取られ、未設定時は 1 です。`STRATA_NO_IQ4XS512` とは別の設定であり、`nt >= iq4xs512_min` を判定します。文字列末尾や変換不能値を別途検証せず、`atoi` の結果を使います（`src/kernels/cpu/native_expert.cpp:519-520`）。AVX-512 経路と AVX2 経路の切り替えには `STRATA_NO_IQ512`、`STRATA_NO_IQ256`、token 数に応じた `STRATA_IQ_MT_MIN` も関係します（同:435-441,459-471,567-597）。

IQ4_XS の AVX-512 基準行処理は ggml-cpu の dot と合うか合成データで初回照合し、結果を型ごとに cache します。一致すれば gate/up の行を処理して戻ります。不一致なら stderr に `strata: the window-invariant 512-bit rows of type 23 differ from this ggml-cpu's dot: its dot runs per token instead` と出し、後続 dispatch に進みます（`src/kernels/cpu/native_expert.cpp:79-114,520-522`）。`STRATA_NO_IQ4XS512` の設定有無そのものに対するログや終了・失敗経路はありません。

## 根拠

- 読み取りと IQ4_XS / token 数 / tail / ggml 照合の条件: `src/kernels/cpu/native_expert.cpp:517-522`
- CPU ISA、AVX2 fallback、および ggml-cpu dot fallback: `src/kernels/cpu/native_expert.cpp:459-471,567-597,620-631`
- `STRATA_IQ_MT_MIN` の既定値と読み取り: `src/kernels/cpu/native_expert.cpp:435-441`
- native expert CPU pool から gate/up 行 dispatch への呼び出し: `src/kernels/cpu/pool.cpp:1231-1237`
- ビルド時の native expert 機能: `CMakeLists.txt:176,2184-2189`
