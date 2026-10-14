# `STRATA_PREFILL_FIRST`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL backend の prompt prefill で、条件を満たすと最初の chunk だけを指定 token 数に短縮します。目的は、prompt の PLE（位置情報用 n-gram embedding）行をホスト側で読み込んでいる間に GPU が先頭 chunk の計算を始められるようにすることです。短い初回 chunk は、その後の chunk と別の GEMM 行数になるため、結果の丸めや生成 token が変わる可能性があります。

この環境変数を読む実装は `sycl/src/prefill/prefill.cpp` にあります。通常の CUDA/HIP 用 `src/prefill/prefill.cpp` にはこの名前の読み取りがなく、CMake でも SYCL は独立した backend として選択されます。

## 値と判定

`std::getenv("STRATA_PREFILL_FIRST")` の値を `std::atoll` に渡します。文字列全体の検証や範囲チェックはありません。`atoll` が数値として読める先頭部分を整数化し、数値が始まらない文字列は 0 として扱われます。したがって `256tokens` は 256、`  +256x` は 256、`true` と空文字は 0 です。負数・0 も明示値として読み取られますが、chunk 短縮条件を満たしません。

| 状態・値 | `first_chunk` | 結果 |
|---|---:|---|
| unset | 全 expert が cache に入る場合は 256、それ以外は 0 | 下記の長さ条件を満たす場合だけ既定の短縮 |
| 0、負数、または数値に変換できない文字列 | 0 | 短縮しない |
| 正の値 `k` | `k` | `k < m.T` かつ prefill 呼び出し長 `n > 2*k` のとき、最初の chunk を `k` tokens にする |
| 正の値だが `k >= m.T` または `n <= 2*k` | `k` | その呼び出しでは短縮しない |

`m.T` はその prefill 実装の chunk 容量です。明示値は容量や prompt 長に合わせて clamp されません。短縮条件に合わない場合、chunk 長は通常どおり `min(m.T, n-c0)` になります。最初の chunk の後は、この環境変数による追加短縮は行わず、通常の chunk 長に戻ります。

根拠: `sycl/src/prefill/prefill.cpp:2193-2198`。

## 有効になる条件

- SYCL backend の prompt prefill 経路であること（`STRATA_ENABLE_SYCL` は独立 backend として `sycl/` を追加して CMake の通常経路を終了する）。
- その `Prefill::run_impl` 呼び出しにおいて、`first_chunk > 0`、`first_chunk < m.T`、`n > 2 * first_chunk` のすべてを満たすこと。
- unset 時に既定 256 を使うのは、`m.cache` と model geometry が存在し、cache slots 数が `n_layers * n_expert` 以上、すなわち全層の expert 数以上あるときだけです。cache が全 expert を保持しないときの既定値は 0 です。環境変数を明示すると、この既定判定を上書きします。

この短縮は prompt 全体の chunking 設定（CLI の `--prefill` など）を変更しません。`n` は現在の `run_impl` 呼び出しに渡された token 数で判定されるため、prompt 全体ではなく小さく分割済みの呼び出しでは条件を満たさないことがあります。layer-split では後段の `run_impl` に各 chunk が渡されるため、条件判定の単位もその呼び出しごとです。

PLE 行読み込みとの重なりが起きるのは、ソース上で `ss.ple.ready()`、`LB <= 1`、`1 < LE` の条件を満たして `ple_on` が true の場合です。これらの条件を満たさなくても、上記の chunk 長条件に従って最初の chunk は短くなります。

根拠: `CMakeLists.txt:12-21`, `sycl/src/prefill/prefill.cpp:2101-2107,2175,2193-2198`。

## 実行時の詳細

`run_impl` の中で `STRATA_PREFILL_FIRST` の `getenv` 結果ポインタを `static` に保持します。環境変数を読むのはプロセス内で最初にこのコードを通るときだけです。各 `run_impl` 呼び出しでは、その保持した文字列を `atoll` で数値化し、unset の場合はその呼び出し時点の cache 状態から既定値を決めます。実行開始後に環境変数を変更しても再度 `getenv` はされず、設定変更を反映する運用はコード上サポートされていません。

各 `run_impl` の最初の chunk の長さを短くすることで、次の chunk の PLE 行を別バッファへ読み込む処理と、GPU の先頭 chunk 計算を重ねられる構造です。`STRATA_TRACE` が有効な場合、通常の chunk ループから `strata trace: prompt chunk ...` を stderr に出しますが、このログは `STRATA_PREFILL_FIRST` が有効になったことを個別には示しません。値自体の診断ログや警告はありません。

根拠: `sycl/src/prefill/prefill.cpp:2172-2198,2217-2229,4450-4459`。

## 文書・測定との照合

`docs/INTEL.md` は B70 での報告として、短い先頭 chunk を使ったとき 2,184-token prompt が 711 から 765 tok/s、8,000-token prompt が 857 から 986 tok/s になり、time to first token が約150 ms短くなったと記載しています。同文書は測定条件をこの箇所で詳細化しておらず、これらは記載された環境での報告値です。コードから性能向上を一般化することはできません。

同文書は、chunk 境界の変化が expert GEMM の丸めに影響し、テストした長い greedy continuation で token 45/64 から出力が分岐した例も記しています。したがって、この設定を使ったときに生成 token が既定 chunking と常に一致するとは言えません。

根拠: `docs/INTEL.md:285-291,786-793`。
