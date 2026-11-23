# `STRATA_CPUEXP_PF`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash の CPU expert fast kernel が重み行を処理するとき、現在行より先の重み行に software prefetch hint を出す距離を「行数」で指定する。これは CPU expert の gate/up/down 行計算に使う重みを対象にした読み込みヒントで、変数自体が計算式やルーティングを選ぶ分岐はない。コード上の用途は `hy4_cpu_experts.cpp` の AVX2/AVX-VNNI と NEON の行ループ、および `hy4_cpu_k512.cpp` の AVX-512 行ループに限られる（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:582-595, 802-815, 1064-1076, 1195-1200`; `engine/src/hy4flash/run/hy4_cpu_k512.cpp:212-223`）。

この実装は `strata-hy4` のソースに含まれる。Strata の CMake では `STRATA_BUILD_HY4` が有効なときに同実行ファイルを作り、GPU translation unit は CUDA または HIP として構成する。したがって通常の他エンジンの実行経路に対する設定ではない（`engine/CMakeLists.txt:846-848, 884-891`）。

## 値と判定

読み取りは CPU expert pool の `start_threads()` で行う。環境変数が存在すれば `std::atoi` の戻り値をそのまま使い、なければ fast kernel のとき 2 を設定する。`g_pf_rows` の初期値は 0（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:315, 2054-2064`）。

| 条件 | 未設定 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 初回 pool 起動時、fast kernel が選ばれている | 2 行 | `1`, `2`, `-1` など、`atoi` が 0 以外を返す整数 | `0`, 空文字, `true`, `false`, `0anything`, 数字で始まらない文字列（いずれも 0） |
| 初回 pool 起動時、fast kernel ではない | 初期値 0 | `1`, `2` など 0 以外の整数。ただし実際の fast 行 loop が使われなければ prefetch には使われない | `0`, 空文字, `true`, `false`, `0anything`, 数字で始まらない文字列（いずれも 0） |

`atoi` は文字列全体の厳密な検証ではない。先頭の空白と符号の後の数字列を整数にし、後続文字は無視する。そのため `2abc` は 2、`0anything` は 0、`1.5` は 1 になる。空文字や数字で始まらない値は 0 となり、警告や fallback はない。正負の範囲制限や clamp もコードにない。`atoi` で `int` に表せない値を与えた場合の結果は、このコードでは定義していない（同ファイル `:2062-2063`）。

未設定と空文字は異なる。未設定なら fast kernel の既定値 2 が適用される一方、空文字は「設定あり」として `atoi("") == 0` になり、既定値を上書きする。設定の有無は `getenv` の null 判定であり、`1` や `true` との文字列比較ではない（同ファイル `:2062-2063`）。

## 有効になる条件

- `strata-hy4` の実行経路で CPU expert pool が初期化され、`start_threads()` が呼ばれる必要がある。初期化時に一度読み、pool 起動ログに値を表示する（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1863-1867, 2054-2064, 2087-2094`）。
- 値が非 0 でも、対応する fast kernel の行計算を通る必要がある。ソースは x86 fast kernel（AVX2/AVX-VNNI および AVX-512）と AArch64 NEON kernel のコンパイル分岐を持ち、AVX-512 実装にも `g_pf_rows` を渡す。CPU / OS 能力検出と `STRATA_CPUEXP_KERNEL`、x86 の `STRATA_FORCE_ISA` が選ぶ kernel に影響する（同ファイル `:53-78, 112-120, 1131-1185, 1195-1200, 1202-1221`; `engine/src/hy4flash/run/hy4_cpu_k512.cpp:212-223`）。
- fast kernel を使わない行列形式はライブラリ GEMM へ fallback する経路があり、その経路の計算ループではこの距離を参照しない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1264-1278`）。
- `STRATA_CPUEXP_PF` を読む別の Strata ソース箇所、helper 経由の読み取り、CLI 引数による同値設定は確認できなかった。候補名の設定 UI 登録は `terminal/data/settings-register.json:4336-4344` にあるが、そこは実行時の値読み取りではない。

## 実行時の詳細

`std::getenv("STRATA_CPUEXP_PF")` の評価は CPU expert pool の `start_threads()` ごとに行われる。起動後に環境を変更しても、既に起動済み pool の `g_pf_rows` は再読込されない。値は関数ローカル cache ではなくファイル内 static 変数に保存されるため、同一プロセス内で複数 pool を順に起動する場合は共有状態となる。未設定かつ fast でない場合、代入がなく static の初期値（または同一プロセスで先に設定された値）が残る（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:315, 2054-2064`）。

AVX2 / AVX-VNNI と AVX-512 の行ループは、`pf` が 0 でなく、`r + pf < nrows` のとき、`r + pf` 行の重みを 64-byte 刻みで prefetch してから現在行を計算する。ここでは負値も弾かれず、負の距離では現在行より前を指すアドレスを組み立て得る（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:582-595, 802-815`; `engine/src/hy4flash/run/hy4_cpu_k512.cpp:212-223`）。NEON の行ループは `pf != 0` のみを条件にし、同じく `r + pf` 行の位置を prefetch するが、行数に対する上限チェックはない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1064-1076`）。コードに値の検査・補正・範囲外の明示的なエラー処理はない。

## ログと測定値

pool 起動時に stderr へ `[cpuexp] %d pool threads%s, spin %d us, sched=%d, pf=%d rows, l3_pf=%s` を出力し、`pf` に読み取った整数を表示する（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2092-2094`）。このログは距離が実際の fast row loop で使われたことを示すものではない。無効文字列を理由にした警告、値の範囲エラー、prefetch の実行結果ログはこの変数の処理にはない。`docs/DETAILS.md` にこの変数固有の設定説明・測定値は見当たらなかった。

## 根拠

- `engine/src/hy4flash/run/hy4_cpu_experts.cpp:315, 582-595, 802-815, 1064-1076, 1195-1200, 1264-1278, 2054-2064, 2092-2094`
- `engine/src/hy4flash/run/hy4_cpu_k512.cpp:212-223`
- `engine/CMakeLists.txt:846-848, 884-891`
- `terminal/data/settings-register.json:4336-4344`（設定 UI 登録。実行時読み取り箇所ではない）
