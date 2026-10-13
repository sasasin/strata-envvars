# `STRATA_SYCL_GEMM_STAGE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの内部動作は対象外。

## 役割

SYCL の BF16/FP16 prefill GEMM で、Battlemage GPU 上でも大きな device allocation の先頭から 4 GiB を超える入力を scratch buffer にコピーしてから oneMKL GEMM に渡すよう要求します。oneMKL が allocation 内の遠い位置にある operand を誤読する問題への回避策です。通常の GEMM 結果バッファ `Y` はコピー対象ではありません。

この変数が判定されるのは `sycl/src/prefill/gemm.dp.cpp` の `staged_gemm()` です。同関数は BF16 GEMM (`Gemm::bf16`) と FP16 GEMM (`Gemm::f16`) の経路から呼ばれます。ほかの backend の GEMM をこの変数が直接制御するコードは確認できません。

## 値と判定

判定は文字列全体の parse ではなく、変数の設定有無と先頭文字によります。

| 状態 | Battlemage | Battlemage 以外 |
|---|---|---|
| `STRATA_SYCL_GEMM_NO_STAGE` が設定されている | staging しない | staging しない |
| `STRATA_SYCL_GEMM_NO_STAGE` が未設定で、この変数が未設定 | staging しない | 入力 operand が 4 GiB 条件を満たせば staging |
| `STRATA_SYCL_GEMM_NO_STAGE` が未設定で、この変数の先頭文字が `1` | 入力 operand が 4 GiB 条件を満たせば staging | 既定どおり。4 GiB 条件を満たせば staging |
| `STRATA_SYCL_GEMM_NO_STAGE` が未設定で、この変数の先頭文字が `1` 以外、または空文字 | staging しない | 既定どおり。4 GiB 条件を満たせば staging |

したがって Battlemage で `1`, `10`, `1anything` は有効ですが、空文字、`0`, `true`, ` 1` は有効になりません。Battlemage 以外ではこの変数は staging の opt-in にはならず、staging を無効にするには `STRATA_SYCL_GEMM_NO_STAGE` を設定します。`STRATA_SYCL_GEMM_NO_STAGE` は値を parse せず、空文字や `0` を含め設定されているだけで staging を禁止します。

## 有効になる条件

- GEMM が SYCL 実装の `staged_gemm()` に到達すること。BF16/FP16 の GEMM 経路が対象です。
- `STRATA_SYCL_GEMM_NO_STAGE` が未設定であること。
- 少なくとも一方の入力 operand の範囲末尾が、登録済み device allocation の先頭から 4 GiB を超えること。`device_offset_end()` は入力範囲全体が登録 allocation 内に収まらない場合や allocation を特定できない場合に 0 を返すため、その場合はこの条件で staging されません。
- Battlemage ではさらに `STRATA_SYCL_GEMM_STAGE` の先頭文字が `1` であること。

`STRATA_SYCL_GEMM_STAGE=1` を設定しても、Battlemage 以外で 4 GiB 条件を満たさない operand はコピーされません。また、`STRATA_SYCL_GEMM_NO_STAGE` が設定されていれば、GPU 世代や `STRATA_SYCL_GEMM_STAGE` の値にかかわらず無効です。

## 実行時の詳細

有効時は、4 GiB 条件に該当する W と X だけを queue 用の device scratch buffer にコピーし、コピーが不要な operand は元のポインタをそのまま使って oneMKL GEMM を実行します。scratch buffer は呼び出し元ホストスレッドごとに保持され、必要容量が増える場合は queue を待ってから以前の buffer を解放して再確保します。

設定値を使った `no_stage` 判定は関数内の `static const bool` に保存され、最初の `staged_gemm()` 呼び出しで一度評価されます。その後にプロセス環境を変更しても判定は更新されません。成功時にこの変数専用のログは出ません。必要な staging buffer を確保できない場合は stderr に警告を出し、直接 GEMM に fallback するため、そのカードでは結果が誤る可能性があると実装が明示しています。

## 文書との照合

`docs/INTEL.md` は B70 ではこの oneMKL 問題が再現せず、既定で staging を無効にし、`STRATA_SYCL_GEMM_STAGE=1` で再び有効にできると記載しています。これは Battlemage を既定 off にするコードと一致します。ソースコメントには Arc A770 の oneMKL 2026.1 で 4 GiB より後ろに置かれた operand の末尾タイルが誤読された事例が記されています。本調査では GPU 実行や再測定をしていません。

## 根拠

- `sycl/src/prefill/gemm.dp.cpp:689-707` — staging scratch の確保と再利用。
- `sycl/src/prefill/gemm.dp.cpp:709-743` — 環境変数判定、4 GiB 条件、選択コピー、確保失敗時の警告と直接 GEMM fallback。
- `sycl/src/prefill/gemm.dp.cpp:818-829,859-869` — BF16/FP16 経路から `staged_gemm()` を呼び、staging されなければ通常の GEMM を行う箇所。
- `sycl/include/strata/sycl_queue.hpp:240-255` — device allocation 内の operand 範囲末尾を求める helper と、範囲外・未登録時の戻り値。
- `docs/INTEL.md:818-823` — B70 での既定 off と `STRATA_SYCL_GEMM_STAGE=1` の説明。
