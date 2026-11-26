# `STRATA_LFUSE_PAIR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

shared expert の gate / up 射影を `native_mmvq_pair` で一度に発行する経路を許可するフラグ。無効にしても gate と up の計算は省かれず、通常の `native_mmvq` を各々呼ぶ。CUDA/HIP と SYCL の verifier から共通の `shared_expert_multi` にフラグが渡される（`engine/src/core/verify.cpp:2746-2751`、`engine/sycl/src/core/verify.cpp:1667-1672`）。

## 値と判定

両 verifier の `g_lfuse_pair()` は `std::getenv` の結果を関数内 `static const bool` に保存し、未設定なら on、設定されていれば先頭文字が `'0'` 以外なら on とする。文字列全体の parse、数値判定、大文字小文字変換はしない（`engine/src/core/verify.cpp:189`、`engine/sycl/src/core/verify.cpp:132`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 共通 verifier（CUDA/HIP。Metal build もこのソースを含む）、SYCL verifier | on | 空文字、`1`、`true`、`false`、`anything`、先頭が空白の ` 0` | `0`、`0anything`、`00`（先頭文字が `0`） |

この値だけでペア kernel の実行が保証されるわけではない。pair flag が渡されても、`native_mmvq_pair` が対応条件を満たさない場合は gate と up に通常の `native_mmvq` を個別に呼ぶ（`engine/src/kernels/cuda/shared_expert.cu:239-244`、`engine/sycl/src/kernels/cuda/shared_expert.dp.cpp:328-332`）。

## 有効になる条件

- 上位の融合経路 `lfuse_on(n)` が真であること。これは `STRATA_LFUSE` が先頭文字 `'1'`、all-resident (`ar_on()`)、native MoE combine 有効、`STRATA_DEC_BATCH` が有効、対象 window が 2〜8 token、native BF16 shared-expert 経路有効、を要求する（`engine/src/core/verify.cpp:1521-1525`、`engine/sycl/src/core/verify.cpp:1059-1063`）。`STRATA_LFUSE_PAIR` はこの上位条件を代替しない。
- shared-expert の重みが存在し native 形式へ変換でき、`shared_expert_multi` に到達すること（`engine/src/core/verify.cpp:2725-2734`、`engine/sycl/src/core/verify.cpp:1647-1655`）。
- pair kernel 自体は両重み型が同じで、型 ID が 8 (Q8_0)、multi exact が有効、token 数 2〜8、正の寸法、入力寸法が 32 の倍数などを要求する。Q8 packed registry に登録された重みも pair kernel の対象外。いずれかを満たさなければ関数は `false` を返し、個別射影に fallback する（`engine/src/kernels/cuda/native_mmvq.cu:3673-3682`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4112-4121`）。
- `engine/src/core/verify.cpp` は Metal build にも含まれるため、上位条件が成立すれば Metal でも getter 自体は評価され得る。しかし Metal の `shared_expert_multi` は `missing("strata::kernels::shared_expert_multi")` を呼ぶ stub で、pair flag を使う実装はない（`engine/metal/CMakeLists.txt:135-146`、`engine/metal/src/engine/stubs.cpp:324`）。

## 実行時の詳細

値はプロセス起動時に必ず読むのではなく、`g_lfuse_pair()` が初めて呼ばれた時に読み、static に保持する。呼び出し箇所は `lfuse_on(n)` の短絡条件の右側なので、上位の融合条件が成立しなければ読み取りも起きない。最初の読み取り後にプロセス環境を変えても、このキャッシュ値は変わらない（`engine/src/core/verify.cpp:189,2750`、`engine/sycl/src/core/verify.cpp:132,1671`）。

有効時、shared expert の gate と up の型が一致し pair kernel の条件も満たせば、それらを一つの `native_mmvq_pair` 呼び出しへまとめる。条件不成立または pair 不対応なら 2 回の `native_mmvq` 呼び出しへ戻る。無効時も同じ個別呼び出しとなる。後続の SwiGLU、down 射影、および shared gate の扱いはこのフラグが直接選び分けず、別の `lfuse` bit や verifier の分岐で決まる（`engine/src/kernels/cuda/shared_expert.cu:239-258`、`engine/sycl/src/kernels/cuda/shared_expert.dp.cpp:328-355`、`engine/src/core/verify.cpp:2747-2751,2944-2959`）。

## ログと測定値

この変数の値や pair kernel の採用可否を直接示すログは見当たらない。CUDA/HIP verifier の `combine layer: kind ...` は combine の種類を記録するが、pair flag の値は区別しない（`engine/src/core/verify.cpp:2944-2949`）。対象変数について条件付き測定値を記した Strata 資料は確認できなかった。

## 根拠

- `engine/src/core/verify.cpp:189,1521-1525,2725-2754,2944-2959`
- `engine/sycl/src/core/verify.cpp:132,1059-1063,1647-1675,1810-1818`
- `engine/src/kernels/cuda/shared_expert.cu:216-244,258-283`
- `engine/sycl/src/kernels/cuda/shared_expert.dp.cpp:315-355`
- `engine/src/kernels/cuda/native_mmvq.cu:3673-3696`
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4112-4135`
- `engine/metal/src/engine/stubs.cpp:324`
