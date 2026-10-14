# `STRATA_Q36_BLAS_F32`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Qwen3.6-35B-A3B 用エンジンの FP32 行列積で、プロンプトのバッチ計算に使う実装を選びます。設定すると hipBLAS / cuBLAS の SGEMM を使います。未設定時は、入力幅 `n_in` が4の倍数なら Strata の split-K CUDA/HIP カーネルを優先し、4の倍数でなければ SGEMM を使います。

対象は `src/qwen35/q36_engine.cu` の `f32mm()` です。通常の Qwen3.8 engine ではなく、モデルヘッダーが `qwen35moe` のとき `strata` から切り替わる Qwen3.6 経路と、同じエンジンを呼ぶ `strata-q36` に適用されます。

## 値と判定

| 環境変数 | 判定 | `T > 8` かつ `n_in % 4 == 0` の場合 |
|---|---|---|
| unset | `getenv()` が null | Strata の split-K カーネルを使う |
| 任意の設定値 | `getenv()` が non-null | hipBLAS / cuBLAS SGEMM を使う |

値の文字列や数値は parse しません。`1` 以外の値、空文字、`0` も「設定あり」として有効です。`n_in` が4の倍数でない場合は、未設定でも SGEMM に進むため、この変数による選択差はありません。`T <= 8` の呼び出しは `f32mm()` の先頭で別カーネルへ戻るため、この変数の判定・適用対象外です。

根拠: `src/qwen35/q36_engine.cu:1276-1310,1314`。

## 有効になる条件

- Qwen3.6-35B-A3B（GGUF architecture `qwen35moe`）のエンジン経路を実行していること。`strata` はモデルメタデータから family を判定して `strata::qwen35::run()` に切り替えます。`strata-q36` も同じ `run()` を呼びます。
- FP32 の `f32mm()` が `T > 8` で呼ばれること。実際の呼び出しは、プロンプトなど複数行の GDN alpha / beta、router、shared-expert gate の積です。decode の1 token router は `T == 1` なので対象外です。
- `n_in % 4 == 0` のときだけ、未設定時の split-K カーネルと設定時の SGEMM の選択差が生じます。

モデル切り替えの根拠: `src/program/generate.cpp:1866-1880`。`f32mm()` の呼び出しと行数条件: `src/qwen35/q36_engine.cu:1353-1359,1440-1444,1490-1501`。

## 実行時の詳細

`f32mm()` は `T <= 8` なら `k_gemv_f32` を起動して戻ります。`T > 8` では関数内の `static const bool` が初めて評価され、その時点の `getenv("STRATA_Q36_BLAS_F32") != nullptr` の結果をプロセス内に保持します。したがって、初回の `T > 8` 呼び出し以降に環境を書き換えても選択は変わりません。

変数が未設定で `n_in` が4の倍数なら、Strata は `n_out` と `T` から tile / split 数を決めて `k_sgemm_nt` を起動し、複数 split の場合は固定順で部分和を加算します。それ以外の `T > 8` 経路では SGEMM に進みます。SGEMM が成功以外を返すと stderr に `strata-q36: cublasSgemm failed` を出してプロセスを `exit(1)` で終了します。別のエラー経路では初期化時に cuBLAS handle / stream の設定が失敗すると `strata-q36: cuBLAS handle failed` を出して終了します。

根拠: `src/qwen35/q36_engine.cu:1158-1161,1283-1309`。

## 根拠

- `src/qwen35/q36_engine.cu:1281-1314` — FP32 行列積、8行以下の早期 return、環境変数判定、split-K と SGEMM の分岐、SGEMM エラー処理。
- `src/qwen35/q36_engine.cu:1353-1359,1440-1444,1490-1501` — GDN alpha / beta、router、shared-expert gate からの呼び出し。
- `src/program/generate.cpp:1866-1880`、`src/qwen35/q36_main.cpp:1-5` — `strata` の family switch と standalone engine entry point。
- `docs/DETAILS.md` には `STRATA_Q36_BLAS_F32` の記載は見つかりませんでした。
