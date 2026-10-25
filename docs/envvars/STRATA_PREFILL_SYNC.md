# `STRATA_PREFILL_SYNC`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数は対象外。

## 役割

SYCL の prompt prefill 中、prefill の各 phase mark で計算 queue を同期し、完了した phase 名と待ち時間を stderr に記録する診断用スイッチです。phase の境目で GPU を待つため、通常の非同期実行を変えます。ソースコメントと `docs/INTEL.md` では hang の調査用 debug switch とされています。

## 値と判定

値の内容は parse されず、`std::getenv("STRATA_PREFILL_SYNC") != nullptr` だけで判定します。

| 状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 設定あり（空文字を含む） | 有効 |
| `0`、`false`、その他の文字列 | いずれも有効（値の比較・数値変換なし） |

`PfTimer` の生成時に読む通常のメンバー初期化であり、static cache ではありません。`run_impl()` の呼び出しごとに作られる `PfTimer` がその時点の値を保持します。呼び出し途中で環境を書き換えても、その timer の判定は変わりません。

## 有効になる条件

- 対象は `sycl/src/prefill/prefill.cpp` に実装された SYCL prefill 経路です。CUDA/HIP 側でこの名前を読む実装は見つかりませんでした。
- `Prefill::run()` が `run_impl()` を呼び、呼び出しごとに `PfTimer` が1つ生成されます。その呼び出し内の chunk 処理で `pt.mark(...)` が実行されるたびに同期・ログが起きます。
- `STRATA_PREFILL_TIMING` とは独立です。タイミング計測が無効でも、この変数だけで同期と mark ログが有効になります。

## 実行時の詳細

各 mark で `sync` が true の場合、実装は `s->wait()` で渡された SYCL queue の作業完了を待ち、その後 stderr に次の形式で出力します（`phase` は `kPfNames` に対応する名前です）。

```text
strata prefill sync: mark <連番> phase <phase名> done (waited <ミリ秒> ms)
```

連番は `PfTimer` ごとに 0 から始まります。待機時間は `steady_clock` による実測値を小数第1位まで出力します。mark は埋め込み、GDN、QSA、router、expert gather/copy wait、GEMM、combine などの区切りに置かれています。待ちが戻らない問題の調査では、最後に出た phase が同期できた地点を示します。

同期後、`STRATA_PREFILL_TIMING` が有効な場合に限って同じ mark の SYCL event を記録します。`STRATA_PREFILL_SYNC` 自体が追加の通常ログや測定値を出すのは mark ごとの stderr 行です。環境変数を子プロセスへ転送・上書きする処理は見つかりませんでした。

`docs/INTEL.md` は過去の prompt-slot borrowing hang の調査で「各 phase の後の同期」を使ったことを記しています。また同資料は hang の原因修正も記述しています。したがって、現在のコード上でこの変数が行うのは診断用同期とログであり、過去の deadlock 回避策として機能するとの記載ではありません。

## 根拠

- `sycl/src/prefill/prefill.cpp:1982-2000`: `PfTimer` の生成時判定、queue wait、stderr ログ、timing event 記録との独立性。
- `sycl/src/prefill/prefill.cpp:1975-1981`: phase 列挙と表示名。
- `sycl/src/prefill/prefill.cpp:2101-2108,2165-2168,2217-2224`: `run_impl()` ごとの timer 生成と、その内部の chunk ループ。
- `sycl/src/prefill/prefill.cpp:4701-4712`: `Prefill::run()` から `run_impl()` を呼ぶ経路。
- `sycl/src/program/generate.cpp:11911`: generate 側からの prefill 呼び出し。
- `docs/INTEL.md:577-587`: 過去の hang 調査時に `STRATA_PREFILL_SYNC=1` で phase ごとに同期した記録と、その後の修正。

