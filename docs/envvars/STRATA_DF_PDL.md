# `STRATA_DF_PDL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の verify window で、条件を満たす kernel-to-kernel の依存辺を programmatic edge にし、後続 kernel が前段の完了を待つ間に定数 weight の読み込みを先行できるようにします。`launch_pdl` は PDL が使えない launch を通常の CUDA kernel launch に戻します。これは launch / graph のスケジューリングを変える設定で、ソースコメントでは PDL 対象 kernel の計算値は通常 launch と同じとされています。設定だけで全 launch が PDL になるわけではありません（`engine/include/strata/kernels/pdl.hpp:3-18,76-101`、`engine/src/core/verify.cpp:1528-1532`）。

実行時の読み取りは `engine/src/kernels/cuda/verify_kernels.cu` の `pdl_supported()` と `pdl_launch_ok()` の 2 箇所です。ほかのヒットは設計コメント、設定 UI の登録データ、PDL parity test、または測定資料で、実行時の読み取り箇所ではありません。

## 値と判定

両方の読み取り箇所で C/C++ の `std::atoi` を使い、文字列全体の妥当性は検査しません。空文字、数値として読めない文字列、数値の先頭に空白があるだけの文字列は `0` になります。先頭に空白や符号があっても後続に数字があれば変換し、数字以降の文字列は無視します（例: `"  +1tail"` は `1`、`"2x"` は `2`）。大文字小文字の扱いはありません。数値の範囲検査や clamp もありません（`engine/src/kernels/cuda/verify_kernels.cu:2079,2124,2136`）。

| 条件 | unset | 設定時に PDL 対応判定を有効にする値 | 設定時に PDL 対応判定を無効にする値 |
|---|---|---|---|
| CUDA 12.3 以降の CUDA build | `pdl_supported()` 側では auto 判定。通常は無効で、compute capability 12.0 かつ `STRATA_SM120_PERF` が 0 でなく、`STRATA_DEFAULTS=026` による旧既定値への切替もない場合に既定で有効。12.1 用の定数 `kGb10DfPdl` は false | `atoi(value) != 0`。例: `1`, `2`, `-1`, `1tail` | `atoi(value) == 0`。例: `0`, 空文字, `false`, `0tail`, 数字で始まらない文字列 |
| `pdl_launch_ok()` の predecessor 制限 | 内部 mode は `1` | mode がちょうど `2` の場合のみ predecessor を 1 個に制限。例: `2`, `2tail` | `2` 以外はこの個数制限なし。これ自体は PDL 対応を有効化しない |

したがって `STRATA_DF_PDL=2` は PDL を有効にし、さらに predecessor が 1 個だけの graph edge を許可します。`3` や `-1` も `pdl_supported()` では有効ですが、predecessor 数は `2` のときの制限を受けません。明示的な `0` や空文字は自動既定値への復帰ではなく、PDL 対応を無効にします（`engine/src/kernels/cuda/verify_kernels.cu:2079,2084,2124,2135-2136`）。

## 有効になる条件

- CUDA build で CUDA Runtime 12.3 以降であること。HIP build、runtime version が未定義、または 12.3 未満では `pdl_supported()` が false を返します（`engine/src/kernels/cuda/verify_kernels.cu:2065-2068`）。
- 現在の device の compute capability が 9.0 以上で、PDL 用 `gpu_stamp_kernel<true>` が `ptxVersion` と `binaryVersion` の両方 90 以上として取得できること。各 launch 対象 kernel にも同じ code-version 条件が必要です。`STRATA_EMULATE_CC` は compute capability の扱いに関係しますが、適合する device code を build していなければ有効にはなりません（`engine/src/kernels/cuda/verify_kernels.cu:2069-2070,2081-2088,2103-2119`）。
- verify window の `G == 1` であること。`STRATA_DF_PDL` が設定されている（空文字を含む）場合は単一 group window で明示 opt-in 経路に入りますが、`pdl_supported()` も true でなければ PDL scope は有効になりません。未設定時は all-resident graph または device-hits 経路で、かつ batch でない window に限って scope を有効にします（`engine/src/core/verify.cpp:1532,1538-1547`）。
- 実際の個々の launch が stream capture 中で、依存 predecessor が 1 個以上あり、依存先がすべて kernel node であること。edge metadata が取得できている場合は、辺の type / port が既定値であることも必要です。`STRATA_DF_PDL=2` では predecessor が 1 個だけの場合に限ります（`engine/src/kernels/cuda/verify_kernels.cu:2121-2145`）。
- `STRATA_DF_PDL` 未設定時の auto 判定は `sm12x_default(major, minor, kGb10DfPdl)` に従います。12.0 は `STRATA_SM120_PERF` が `atoi` で 0 でないとき既定有効となり、`STRATA_DEFAULTS=026` はこの既定を切ります。12.1 / GB10 は `kGb10DfPdl == false` のため、この変数については既定有効になりません（`engine/include/strata/core/sm120_series.hpp:32-38,60-61,75-81,99`、`engine/include/strata/core/defaults_026.hpp:26-28`）。明示的な非 0 値はこの GPU 世代別 default を上書きしますが、上記の build / device / code 条件は引き続き必要です。

## 実行時の詳細

`pdl_supported()` は `env_mode` を関数内 `static` に一度読み、device ごとの対応結果も `state[dev]` に保存します。`pdl_launch_ok()` は別の関数内 `static` に mode を一度保存し、kernel と device ごとに kernel code 判定を cache します。`verify.cpp` の scope 判定にある `getenv(...) != nullptr` は各 window で設定有無を見ますが、上記 cache は更新されません。そのため、実行中に環境を書き換えても、初回評価後の対応判定や predecessor mode は更新されません（`engine/src/kernels/cuda/verify_kernels.cu:2071-2092,2104-2118,2124`、`engine/src/core/verify.cpp:1542,1547`）。

PDL scope が有効なとき `launch_pdl` は `pdl_launch_ok()` が true を返す kernel に `cudaLaunchAttributeProgrammaticStreamSerialization` を付けて launch します。stream capture 情報を取得できない、capture 外である、kernel code が条件を満たさない、または predecessor が memcpy / memset / host / event 等の場合は、対象 launch を通常の `<<<...>>>` にします。PDL 用の launch 判定に失敗したこと自体は Strata の fatal error ではありません。`cudaLaunchKernelEx` の戻り値はその場で処理せず、CUDA launch error として後続の呼び出し元が確認できるようにしています（`engine/include/strata/kernels/pdl.hpp:76-101`、`engine/src/kernels/cuda/verify_kernels.cu:2098-2145`）。

## ログと測定値

dispatch 統計が有効な場合、PDL scope 中の各 launch について `pdl: launch with a programmatic edge` または `pdl: ordinary launch inside a PDL window (kernel not sm_90 code, or a predecessor is not a kernel)` が記録されます。また window ごとに `win pdl=%ld side_mixer=%ld side_proj=%ld` が記録され、`pdl` は scope 判定の 0 / 1 を表します。これらは即時の stderr ログではなく dispatch 統計の note です。統計は既定で有効で、`STRATA_DISPATCH_STATS` が `0` で始まる場合は無効です。`STRATA_DISPATCH_REPORT=<path>` が設定されていれば終了時に JSON report を書きます（`engine/include/strata/kernels/pdl.hpp:82-99`、`engine/src/core/verify.cpp:1543-1548`、`engine/include/strata/core/dispatch_stats.hpp:107-119,145-152`）。

この文書では性能値を記載しません。コメントと `docs/DGX_SPARK_LINUX.md` は GB10 でこの switch を既定 off とする判断に触れていますが、文書にある測定条件の範囲を超えて一般化できる測定根拠は確認できません（`engine/include/strata/core/sm120_series.hpp:83-100`、`docs/DGX_SPARK_LINUX.md:119-126`）。

## 根拠

- 直接読み取りと値の分岐: `engine/src/kernels/cuda/verify_kernels.cu:2065-2093,2121-2145`
- window scope と dispatch note: `engine/src/core/verify.cpp:1528-1547`
- PDL launch / ordinary fallback: `engine/include/strata/kernels/pdl.hpp:76-101`
- GPU 世代別 default と相互作用: `engine/include/strata/core/sm120_series.hpp:32-38,60-81,93-100`、`engine/include/strata/core/defaults_026.hpp:26-28`
- dispatch 統計 note / report 条件: `engine/include/strata/core/dispatch_stats.hpp:107-119,145-152`
