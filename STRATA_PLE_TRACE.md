# `STRATA_PLE_TRACE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版の PLE（per-layer embedding）reader が、読み取り ticket ごとの I/O 時間を stderr に出す診断用スイッチです。PLE の読み取り方法、行データ、待ち合わせの動作そのものは切り替えません。CUDA 等の通常版 `src/ngram/ple_reader.cpp` にはこの環境変数の読み取り実装がなく、判定は `sycl/src/ngram/ple_reader.cpp` にだけあります。

## 値と判定

数値や文字列を parse せず、`std::getenv("STRATA_PLE_TRACE") != nullptr` で設定の有無だけを判定します。

| 状態 | trace 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む、何らかの値が設定済み | 有効（例: `1`, `0`, `false`, 空文字） |

`ple_trace()` の結果は関数内の `static const bool` に保存されます。reader がこの関数を初めて呼んだ後にプロセス環境を変更しても判定は更新されません。

## 有効になる条件

- SYCL ビルドで `sycl/src/ngram/ple_reader.cpp` がカーネルライブラリに含まれること（`sycl/CMakeLists.txt`）。
- PLE の direct I/O 経路で `PleReader::collect()` が呼ばれること。mmap の PLE 経路ではこの reader のログは出ません。
- ログ出力には reader の worker-thread mode が必要です。`collect()` の worker-thread 分岐だけがログを出し、ticket の read job 数が 1〜199 のときに限ります。0 件または 200 件以上では出力しません。

## 実行時の詳細

設定が有効な場合、reader は ticket の発行時刻、最初の job を submit する直前、最後の job の完了処理後の時刻を記録します。worker-thread mode の `collect()` は ticket が完了した後、次の形式の1行を stderr に出します。

```text
ple trace: %3u jobs  issue->submit %8.1f  submit->last %8.1f  last->return %8.1f  collect wait %8.1f us
```

値は順に job 数、issue から最初の submit まで、最初の submit から最後の完了処理まで、最後の完了処理から `collect()` のログ生成時点まで、`collect()` 呼び出しから戻るまでのマイクロ秒です。これは経過時間の診断ログで、ticket が I/O エラーになったときは成功後のログ出力箇所に到達しません。設定を外したときにはログを出しません。

`docs/INTEL.md` は、`STRATA_PLE_TRACE=1` を使った特定の SYCL 調査で、遅い run の最初の decode round に一度 226 ms の PLE read stall が見えたと報告しています。これはその記録にある観測であり、この環境変数が stall を解消する、または常に性能を改善することを示すものではありません。

## 根拠

- `sycl/src/ngram/ple_reader.cpp:96-99` — 設定有無だけを判定し、結果を static cache。
- `sycl/src/ngram/ple_reader.cpp:162-167,258-260` — trace 有効時に ticket の最初の submit 時刻と最後の完了時刻を記録。
- `sycl/src/ngram/ple_reader.cpp:481-484` — ticket の job 数と発行時刻を保存。
- `sycl/src/ngram/ple_reader.cpp:500-523` — worker-thread mode の `collect()` で job 数が 1〜199 の場合に stderr へログ出力。
- `src/kernels/ngram.cpp:446-457,467-475,493-499` — direct PLE 読み取りで reader の issue/collect を呼び、読んだ行を decode する経路。
- `sycl/CMakeLists.txt:214-218` — SYCL kernel library に `src/ngram/ple_reader.cpp` を含める。
- `docs/INTEL.md:484-489` — PLE trace による特定の遅延調査の記録。
