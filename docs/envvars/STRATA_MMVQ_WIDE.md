# `STRATA_MMVQ_WIDE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。Strata が所有するソースを対象とし、外部ライブラリの挙動は含めない。

## 役割

SYCL backend の Q6_K 行列ベクトル積（MMVQ）で、16-byte load を使う wide kernel を選ぶかどうかを制御する。既定は有効。Q6_K の呼び出しは推論の native MMVQ dispatcher からも到達するため、ベンチマーク専用の設定ではない。変数が直接制御するのは wide 経路の候補化であり、無効にしても別の条件によって別の専用 kernel が選ばれる場合がある。

## 値と判定

カーネル実装のグローバル変数 `g_q6k_wide` を初期化するとき、`getenv("STRATA_MMVQ_WIDE")` が未設定なら `true`、設定済みなら `atoi(value) != 0` とする（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:1989`）。したがって値は文字列全体の比較ではなく、C の `atoi` による整数変換で判定される。

| 値 | 判定 |
|---|---|
| 未設定 | 有効 |
| `1`、`-1`、`2` | 有効（変換値が 0 以外） |
| `0`、`00`、`0suffix` | 無効 |
| 空文字、数値に変換できない文字列 | 無効（変換値が 0） |
| 先頭に空白や符号があり、その後に非ゼロ整数がある文字列 | 有効 |

`atoi` は数値以降の文字列を検査しないため、たとえば `1suffix` は有効、`0suffix` は無効になる。大文字小文字の比較はない。

## 有効になる条件

- 適用先は SYCL backend の Q6_K MMVQ。通常の `native_mmvq()` は GGML type 14 を `native_q6_k_mmvq()` へ振り分ける。他の量子化形式にはこの変数は使われない（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:3685-3701`）。
- `native_q6_k_mmvq()` は先に packed Q6_K 経路を試し、それが処理した場合は wide 判定へ進まない（同 `:3426-3429`）。
- wide 経路の選択には、さらに `1 <= ncols <= wide_maxc`、`n_in` が 256 の倍数、`n_out >= wide_min` が必要（同 `:3433-3446`）。`wide_min` / `wide_maxc` は別環境変数 `STRATA_MMVQ_WIDE_MIN` / `STRATA_MMVQ_WIDE_MAXC` で上書きできる。未設定時の既定値は `STRATA_MMVQ_A2` の判定にも依存し、A2 が有効ならそれぞれ `0` / `8`、無効なら `4096` / `4`。この2変数は初回評価時に `static const` へ保存される（同 `:1534-1536,3433-3435`）。
- wide 判定を通らなければ、その後の rowwarp 等の候補判定と通常経路へ続く。したがって `STRATA_MMVQ_WIDE=0` は wide kernel を除外するが、単独で特定の代替 kernel を保証しない（同 `:3448` 以降）。
- `sycl/CMakeLists.txt` は `native_mmvq` を GPU engine の kernel 群に含める（`sycl/CMakeLists.txt:205-214`）。推論側では layer の native projection から `native_mmvq()` を呼び出している（`sycl/src/core/layer.cpp:145-157`）。

## 実行時の詳細

エンジン側の `g_q6k_wide` はグローバル初期化時に環境を読み、その後の各 Q6_K 呼び出しで判定結果を参照する。通常の推論経路では起動後に環境を変更しても再読込されない。公開 setter `native_mmvq_set_q6k_wide(bool)` はこの状態を実行時に変更できるが、対象ソース全体で呼び出しがあるのは `mmvq_bench` のみで、そこで比較のため一時的に false/true を設定した後、環境値から再設定する（`sycl/src/kernels/cuda/native_mmvq.dp.cpp:2954-2955`, `sycl/src/kernels/mmvq_bench.cpp:27-35`）。

wide 経路に入ると、`ncols` に対応する `launch_q6k_wide` specialization を選ぶ。内部では `STRATA_MMVQ_WIDE_RPW`、`STRATA_MMVQ_PF`、および `STRATA_MMVQ_A2` に応じて kernel variant が分かれる。これらは wide kernel 内部の分岐であり、`STRATA_MMVQ_WIDE` 自体の判定とは別である（同 `:1693-1741`）。この変数について専用のログ出力や警告は見当たらない。

## 文書との照合

`docs/INTEL.md` は Intel B70 の SYCL port で Q6_K wide kernel の aligned-load 版が対象 shape を広げた経緯と測定を記載している。記載上は 2560→10240 行、1/2/4/6 columns で 160/145/141/101 から 493/432/331/273 GB/s、Coder の greedy decode（2k prompt）で 44.9 から 54 tok/s となっている（`docs/INTEL.md:448-455`）。これは特定構成での wide kernel の測定値であり、`STRATA_MMVQ_WIDE` の ON/OFF 比較値としては記載されていない。実装側では `STRATA_MMVQ_A2` が無効な場合の旧い shape gate も残るため、文書の測定を他の backend・GPU や任意の shape に一般化しない。

## 根拠

- 環境値の既定と変換: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1989`
- Q6_K 用の呼び出し、wide の適用条件と launch: 同 `:3426-3446`
- native MMVQ の type dispatch: 同 `:3685-3701`
- wide kernel の内部 variant: 同 `:1693-1741`
- setter とベンチマーク上の一時切替: 同 `:2954-2955`; `sycl/src/kernels/mmvq_bench.cpp:27-35`
- SYCL build 対象と推論側呼び出し: `sycl/CMakeLists.txt:205-214`; `sycl/src/core/layer.cpp:145-157`
- 設計経緯・測定条件: `docs/INTEL.md:448-455`
