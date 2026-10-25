# `STRATA_IQ3S_MT1`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。作業開始時の Strata リポジトリは `main` で、作業ツリーに変更はありませんでした。

## 役割

CPU 上の native expert 実行で、IQ3_S の gate/up 行を1 tokenだけ処理するときにも Strata の AVX2 multi-token kernel を使うための opt-in です。通常の最小 token 数は2で、1 token の場合は ggml-cpu の dot product に進みます。この変数を有効にすると、対象条件下で IQ3_S の最小数を1にします。GPU kernel や native expert 以外の経路を切り替える変数ではありません。

## 値と判定

この変数は数値や文字列を parse せず、`std::getenv("STRATA_IQ3S_MT1") != nullptr`、つまり設定の有無だけで判定されます。

| 状態 | 判定 |
|---|---|
| 未設定 | この変数による変更なし。通常の最小数（既定2）を使う |
| 空文字を含む任意の値 | 設定済みとして有効候補。`1` 以外でも値の内容は問わない |
| `STRATA_IQ_MT_MIN` も設定済み | `STRATA_IQ3S_MT1` は無視される。`STRATA_IQ_MT_MIN` の `atoi` 結果が使われる |

`STRATA_IQ_MT_MIN` は値が空文字・不正文字列でも「設定済み」なら `atoi` され、結果の `0` が使われます。これが設定されていれば `STRATA_IQ3S_MT1` の有無は見ません。どちらの環境変数の判定結果も helper 内の `static` に保存されるため、初回判定後にプロセス環境を変更しても反映されません。

## 有効になる条件

`STRATA_IQ3S_MT1` が設定されていても、次の条件をすべて満たす場合に限り IQ3_S (`gu_type == 21`) の最小 token 数を1にします。

- `STRATA_IQ_MT_MIN` が未設定。
- 実行 CPU が `cpu_avx2_ok()` を満たす。
- `STRATA_NO_IQ256` が未設定。
- AVX-512 が使えない（`cpu_avx512_ok()` が false）。
- `iq256_gather_setting() != 0` かつ `cpu_gather_fast()` が true。

`cpu_gather_fast()` は AVX2 以上の ISA 判定に加え、Intel CPU の vendor ID、CPUID による AVX-VNNI、特定の E-core 専用 CPU 型でないことを確認します。`STRATA_IQ256_GATHER=0` なら gather 条件が不成立です。`STRATA_IQ256_GATHER` が未設定または空文字なら自動判定値 `-1` となり、`cpu_gather_fast()` の判定が使われます。

CPU が AVX-512 対応の場合、この設定で最小数は下がりません。`STRATA_NO_IQ256` が設定されている場合も、値が `0` や空文字であっても設定有無によって対象外になります。CPU native expert 経路自体が使われなければ効果はありません。

## 実行時の詳細

native expert CPU pool の gate/up 行処理から `native_gu_rows()` が呼ばれ、その関数が `native_gu_mt_min()` の返す閾値を使って multi-token kernel の分岐を選びます。条件成立時は `gu_type == 21` について閾値が1になり、1 token の IQ3_S も AVX2 IQ multi-token kernel に入ります。条件が外れる場合や対象外の format では元の閾値（通常2）で、1 token は ggml-cpu の `vec_dot` 経路になります。

この設定によって1 token 時の IQ3_S 丸めが変わるため、結果の token 選択が変わる可能性があります。Strata の `docs/DETAILS.md` は、AVX-512 のない Alder Lake 以降で AVX2 kernel が IQ3_S grid を gather する場合にこの opt-in を案内しています。また同資料は `STRATA_IQ_MT_MIN=1` について、drafting への依存をなくす代わりに Ryzen 7600 (AVX-512) の IQ3_S decode が1〜3%遅くなった測定を記しています。この測定は別変数の設定に関するものであり、`STRATA_IQ3S_MT1` の速度値としては扱えません。`STRATA_IQ3S_MT1` 自体について、同資料には数値測定条件・結果はありません。

この変数について専用のログ出力は実装されていません。

## 根拠

- `src/kernels/cpu/native_expert.cpp:124-141` — 既定閾値、`STRATA_IQ_MT_MIN` の優先、対象変数の presence 判定、IQ3_S の閾値上書き。
- `src/kernels/cpu/native_expert.cpp:143-190` — AVX2/AVX-512 条件、閾値と形式による multi-token kernel 選択、ggml-cpu への fallback。
- `src/kernels/cpu/pool.cpp:684-709` — native expert CPU pool の gate/up 行から `native_gu_rows()` を呼ぶ箇所。
- `src/kernels/cpu/expert_layout.cpp:210-239` — `STRATA_IQ256_GATHER` の parse と `cpu_gather_fast()` の CPU 判定。
- `docs/DETAILS.md:97-112` — 再現可能な greedy 出力に関する説明と `STRATA_IQ3S_MT1` の案内。測定値は `STRATA_IQ_MT_MIN` の説明に属する。
