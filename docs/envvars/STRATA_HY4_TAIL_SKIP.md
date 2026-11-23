# `STRATA_HY4_TAIL_SKIP`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`strata-hy4` の CUDA/HIP runner で、decode/verify 時に CPU または cold tier にある未常駐 expert を、ルーティング順位が指定順位以上の場合に計算対象から外す opt-in 設定です。runner の既定値は 0 で、環境変数を有効にすると一部の expert 寄与を省くため、通常時と出力の数値的同一性は保証されません。実装は `Runner::init` と `Runner::run_hybrid_miss_layer`（`engine/src/hy4flash/run/hy4_graph.hip.h`）です。`strata-hy4 --serve` と通常の `strata-hy4` 実行の双方がこの runner を使います（`engine/src/hy4flash/run/hy4_main.hip.cpp:692-704`、`engine/src/hy4flash/run/hy4_serve.hip.h:307-316`）。

## 値と判定

runner の `tail_skip` は 0 で初期化されます。`Runner::init` はこの値が 0 以下のときだけ環境変数を調べ、値が存在して空文字でなければ `std::atoi` で変換し、結果が `1..15` の場合だけ採用します。それ以外は 0 のままで、無効値に対する警告やエラーはありません（`engine/src/hy4flash/run/hy4_graph.hip.h:230-232,1585-1594`）。

| ビルド・入力経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `strata-hy4` CUDA/HIP runner、CLI の正の `--tail-skip` なし | 0（無効） | `atoi` の結果が 1..15。例: `1`, `15`, `7x`, ` 7` | 空文字、`0`, `0anything`, `16`, `-1`, `true`, `junk`。これらは 0 扱い |
| `strata-hy4` CUDA/HIP runner、正の `--tail-skip N` あり | 環境変数を参照せず CLI 値 | CLI の `atoi` 結果が正なら、その値 | CLI の `atoi` 結果が 0 以下なら環境変数へフォールバック |

文字列全体の数値検証はありません。先頭の空白や符号は `atoi` の規則で処理され、数値の後ろの文字列は無視されます。したがって `7x` は 7、`0anything` は 0 です。環境変数は変換後の範囲が 1..15 に制限されます。一方、CLI 値には同じ上限チェックがありません。たとえば `--tail-skip 99` は正の値として環境変数より優先されますが、router の順位は 0..15 なので条件に合う expert はなく、実質的に skip しません（CLI 解析 `engine/src/hy4flash/run/hy4_main.hip.cpp:366,415`、順位判定 `engine/src/hy4flash/run/hy4_graph.hip.h:2194-2204,2211-2217`）。

## 有効になる条件

- この読み取りを含む `strata-hy4` は `STRATA_BUILD_HY4` の CUDA または HIP ビルドです。CMake はどちらも同じ `hy4_main.hip.cpp` をコンパイルし、Metal/SYCL は専用実装として別扱いです（`engine/CMakeLists.txt:846-852,884-908`）。この変数を Metal/SYCL runner が読む実装は見つかりません。
- 値が有効でも、`run_hybrid_miss_layer` の処理対象は `T <= 16` のときだけです（`engine/src/hy4flash/run/hy4_graph.hip.h:2186-2194`）。
- 対象となるのは、その層でルーティングされた expert のうち tier が 2 以上で、GPU cache に常駐していないものです。resident expert や tier 2 未満の expert はこの skip 条件に入りません（`engine/src/hy4flash/run/hy4_graph.hip.h:2211-2217,2303-2315`）。
- 各 expert について、処理 window 内の全 token・16 route slot を調べた最小 slot index `minr` が閾値以上なら、その expert の CPU/cold-tier 寄与を除外します。閾値未満の順位で一度でも選ばれた expert は除外されません（`engine/src/hy4flash/run/hy4_graph.hip.h:2194-2204,2211-2217,2305-2315`）。
- 関連する CLI 引数は `--tail-skip` です。正の値が環境変数に優先し、0 または負値なら環境変数を評価します。別の環境変数による上書き条件は、この変数の読み取り経路では見つかりません（`engine/src/hy4flash/run/hy4_main.hip.cpp:366,415,568,699`、`engine/src/hy4flash/run/hy4_serve.hip.h:307-316`）。

## 実行時の詳細

環境変数は `Runner::init` 中に読み取られます。読み取りは `static` cache ではなく、runner インスタンスの `tail_skip` に値を格納します。初期化後にプロセス環境を変更しても、その runner には反映されません。新しい runner の初期化では再評価されます（`engine/src/hy4flash/run/hy4_graph.hip.h:1585-1594`）。通常実行では `hy4_main` が `--tail-skip` の値を runner に渡してから `init` し、serve 実行では `ServeOpts` に渡した値を `Runner` にコピーしてから `init` します（`engine/src/hy4flash/run/hy4_main.hip.cpp:555-569,692-704`、`engine/src/hy4flash/run/hy4_serve.hip.h:307-316`）。

有効時には各 decode/verify window で route rank を集計し、閾値以上だけで選ばれた CPU/cold-tier expert の pair を CPU pool に渡さないようにします。GPU 常駐 expert の計算経路や、閾値より上位で選ばれた同じ expert はこの判定で除外されません。除外 pair 数は `tail_skipped_pairs` に加算されますが、このカウンタを出力するログは該当コード内にありません（`engine/src/hy4flash/run/hy4_graph.hip.h:2194-2204,2303-2315`）。

## ログと測定値

採用値が正の場合、runner 初期化時に stderr へ次の形式で出力します（`engine/src/hy4flash/run/hy4_graph.hip.h:1593-1594`）。

```text
[runner] STRATA_HY4_TAIL_SKIP=<値> is ON (opt-in): missed CPU/cold-tier experts routed only at rank >= <値> in decode/verify are skipped
```

未設定、空文字、無効値、`--tail-skip` が 0 以下で環境変数も有効値でない場合には、このログは出ません。変数に起因する専用の警告・終了コード・失敗経路は見つかりません。`docs/DETAILS.md` の tail-skip 節は別名の `STRATA_ROUTE_TAIL_SKIP` を扱っており、この HY4 変数の測定値や効果の資料としては扱っていません（`docs/DETAILS.md:1199`）。

## 根拠

- `engine/src/hy4flash/run/hy4_graph.hip.h:230-232,1585-1594` — 既定値、環境変数の読み取りと変換、採用範囲、有効時ログ。
- `engine/src/hy4flash/run/hy4_graph.hip.h:2186-2217,2303-2315` — window 条件、tier/cache 条件、rank 判定、CPU pair 除外とカウンタ。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:366,415,555-569,692-704` — CLI 値の解析・伝搬と通常 runner の初期化。
- `engine/src/hy4flash/run/hy4_serve.hip.h:43-54,307-316` — serve 経路の設定伝搬と runner 初期化。
- `engine/CMakeLists.txt:846-852,884-908` — HY4 target の CUDA/HIP 条件とコンパイル対象。
