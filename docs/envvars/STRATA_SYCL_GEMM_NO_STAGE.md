# `STRATA_SYCL_GEMM_NO_STAGE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

SYCL prefill の BF16/FP16 GEMM にある、4 GiB を超える位置の入力を一時 device buffer にコピーしてから GEMM する経路を止めます。これは全 GEMM や全コピーを切る設定ではなく、`staged_gemm()` 内の安全対策用 staging だけを無効にします。設定すると、該当 operand が4 GiBを超えていても呼び出し元が通常の直接 GEMM に進みます。

この環境変数を読む実装は `sycl/src/prefill/gemm.dp.cpp` のみです。SYCL build は CMake の source resolver が `src/prefill/gemm.cu` に代えてこの移行済みファイルを `strata_prefill` に含めます。CUDA/HIP 側の同名 GEMM 実装を制御する変数ではありません（`sycl/CMakeLists.txt:3-7,232-239`）。

## 値と判定

`staged_gemm()` 内の関数ローカル `static const bool` が初期化されるとき、`std::getenv("STRATA_SYCL_GEMM_NO_STAGE") != nullptr` を判定します。値の parse はありません。

| `STRATA_SYCL_GEMM_NO_STAGE` | 結果 |
|---|---|
| unset | それ自体では staging を止めない。Battlemage では下記の `STRATA_SYCL_GEMM_STAGE` 判定へ進む |
| 任意の値が設定済み | staging を止める。`1`、`0`、`false`、空文字のいずれも同じ |

設定済みかどうかが条件なので、先頭文字、大文字小文字、空白、数値としての妥当性は関係しません。設定時は `||` の短絡評価により GPU 世代と `STRATA_SYCL_GEMM_STAGE` の判定を行いません。

未設定の場合の既定動作は GPU 世代により異なります。

| SYCL device | `STRATA_SYCL_GEMM_STAGE` | `no_stage` |
|---|---|---|
| Battlemage | unset、空文字、先頭文字が `1` 以外 | true（staging を止める） |
| Battlemage | 先頭文字が `1`（例: `1`, `10`, `1abc`） | false（4 GiB 条件を満たせば staging を許す） |
| Battlemage 以外 | 任意 | false（この変数は既定 staging を止めない） |

`STRATA_SYCL_GEMM_STAGE` は文字列全体や数値として parse されず、先頭文字だけを比較します。`STRATA_SYCL_GEMM_NO_STAGE` が設定されていれば常に優先し、`STRATA_SYCL_GEMM_STAGE=1` でも覆りません（`sycl/src/prefill/gemm.dp.cpp:712-716`）。

## 有効になる条件

- 変数を読むのは SYCL build の prefill GEMM です。BF16 の `Gemm::bf16()` と FP16 の `Gemm::f16()` が `staged_gemm()` を呼びます。HIP 専用の hipBLASLt 分岐など、`staged_gemm()` より前に処理を完了する経路には影響しません（`sycl/src/prefill/gemm.dp.cpp:746-830,833-869`）。
- `no_stage` が false でも、staging は W または X の device allocation 内終端 offset が `4ull << 30` より大きい場合に限ります。どちらも4 GiB以下なら通常の GEMM に進みます（`sycl/src/prefill/gemm.dp.cpp:717-724`）。
- offset 判定は Strata が登録した allocation の範囲で行います。該当 allocation を特定できないポインターは `device_offset_end()` が 0 を返すため、4 GiB 超としては扱われません（`sycl/include/strata/sycl_queue.hpp:218-255`）。
- Battlemage 判定は `sycl::device` の architecture 情報、またはデバイス名等から `IntelGpuGen::Battlemage` を識別します。コード上の対象例は Arc B-series / Arc Pro B-series です（`sycl/include/strata/sycl_queue.hpp:120-158`）。

## 実行時の詳細

初回の `staged_gemm()` 呼び出しで設定有無と（必要な場合は）GPU 世代、`STRATA_SYCL_GEMM_STAGE` を評価し、その結果を関数ローカル static に保持します。同一プロセスで後から環境を書き換えても再評価されません。

staging を許可し、W または X の終端 offset が4 GiBを超える場合は、必要サイズ `w_bytes + x_bytes` の thread-local device buffer を確保し、該当 operand だけを queue にコピーして GEMM を行います。確保に失敗すると stderr に `strata: WARNING: a GEMM operand lies past 4 GiB and the %zu MiB staging buffer could not be allocated; the GEMM runs directly and may be wrong on this card` を出して `false` を返します。呼び出し元はそのまま直接 GEMM に進みます。`STRATA_SYCL_GEMM_NO_STAGE` が有効な場合も helper は `false` を返し、同じ直接 GEMM 経路になります（`sycl/src/prefill/gemm.dp.cpp:696-742,818-830,859-869`）。

## 文書との照合

`docs/INTEL.md` は B70 の borrowed region にある GEMM operand が4 GiB超となる状況で、Battlemage では staging を既定で止め、`STRATA_SYCL_GEMM_STAGE=1` で再度有効化すると説明しています。これは上記の分岐と一致します。同資料は、A770 で確認された oneMKL の4 GiB超 operand 問題には staging 対策があると記していますが、外部 oneMKL 自体の挙動はここでは Strata の効果として扱っていません（`docs/INTEL.md:718-726,818-823`）。

## 根拠

- `sycl/src/prefill/gemm.dp.cpp:696-742` — staging buffer、環境変数判定、4 GiB offset 条件、allocation 失敗時の警告と直接実行への fallback。
- `sycl/src/prefill/gemm.dp.cpp:746-830,833-869` — BF16/FP16 GEMM から helper を呼ぶ位置と直接 GEMM への fallback。
- `sycl/include/strata/sycl_queue.hpp:120-158,218-255` — Battlemage 識別と device allocation offset 判定。
- `sycl/CMakeLists.txt:3-7,232-239` — SYCL build での移行済み prefill 実装の選択。
- `docs/INTEL.md:718-726,818-823` — 4 GiB 対応と Battlemage の既定動作に関するプロジェクト資料。
