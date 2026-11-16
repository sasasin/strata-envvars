# `DF2B_SKIP`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`DF2B_SKIP` は通常の Strata 推論エンジン、サーバー、セットアップでは参照されず、Metal の DFlash2 ベンチ `metal/tests/df2_bench.cpp` の行列積 dispatch を省くためのベンチ専用スイッチである。値が正確に `mm` のとき、ベンチ内の `mm` lambda は dispatch を追加せずに戻る。それ以外の値では通常どおり dispatch を作る。コードのコメントはこの経路を “the small kernels alone” と説明している（`metal/tests/df2_bench.cpp:285-289`）。

## 値と判定

関数内 static bool の初回初期化時に `std::getenv("DF2B_SKIP")` を確認し、設定されていれば文字列全体を `"mm"` と比較する（`metal/tests/df2_bench.cpp:285-288`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Metal `df2_bench` の `mm` lambda | 行列積を省かない | `mm`（大文字小文字を区別する完全一致） | 空文字、`0`、`1`、`true`、`MM`、`mm `、`0anything` など、完全一致しない値 |

数値変換、空白除去、真偽値解釈はない。設定有無だけでも判定しない。`mm` 以外の設定値は、未設定と同じく skip を有効にしない（`metal/tests/df2_bench.cpp:287-289`）。

## 有効になる条件

- `metal/tests/df2_bench.cpp` を実行する Metal ベンチ経路であること。参照箇所はこのファイル内の一か所だけで、通常の Strata engine / CLI / server の読み取りは確認できない（`metal/tests/df2_bench.cpp:1-3,285-289`）。
- 値が `mm` と完全一致すること。
- `mm` lambda を通る行列積 dispatch にだけ作用する。`build_ctx`、`build_block`、通常の `build_head`、stand-in graph の行列積はこの lambda を通る（`metal/tests/df2_bench.cpp:342-389,391-416,423-425`）。ただし `DF2B_HEAD=mma` の `build_head` は head の MMA dispatch を直接追加する分岐なので、このスイッチによる省略対象ではない（`metal/tests/df2_bench.cpp:395-405`）。

## 実行時の詳細

判定は `mm` lambda 内の `static const bool skipmm` として保持される。環境を読むのはプロセス起動直後ではなく、そのプロセスで最初に `mm` が呼ばれたときであり、その後の環境変更は反映されない（`metal/tests/df2_bench.cpp:285-289`）。

skip が有効なら各 `mm` 呼び出しは行列積用 dispatch をベクトル `ds` に追加せずに戻る。lambda を使う他の非行列積処理（正規化、畳み込み、attention、top-k、selector 等）は個別に dispatch を追加し続けるため、このスイッチはベンチ全体を終了したり全 GPU 処理を止めたりはしない（`metal/tests/df2_bench.cpp:285-325,342-415`）。各グラフはそのまま `time_it` に渡され、warm-up と計測で実行される（`metal/tests/df2_bench.cpp:426-439`）。結果の正確性や推論 token への影響を測る機能ではなく、ベンチ内の行列積を外した dispatch 群の時間を測るコードである。

## ログと測定値

この変数専用の警告・エラー・ログ文言はない。通常の `time_it` 出力にはグラフの dispatch 数、GPU 時間、wall time が表示されるため、行列積 dispatch が省かれたグラフでは dispatch 数と計測対象が変わる（`metal/tests/df2_bench.cpp:426-439`）。ソース内に `DF2B_SKIP` の有効値による測定結果は記載されていない。

## 根拠

- `metal/tests/df2_bench.cpp:1-9` — `df2_bench` が Metal 上の DFlash2 ベンチであること、および “the small kernels alone” の目的。
- `metal/tests/df2_bench.cpp:285-325` — `DF2B_SKIP` の唯一の読み取り、完全一致判定、dispatch 省略の位置。
- `metal/tests/df2_bench.cpp:342-416,423-439` — ベンチの stage が lambda を呼び、作成した dispatch 群を計測する流れ。
- `metal/tests/df2_bench.cpp:395-405` — `DF2B_HEAD=mma` の直接 dispatch 分岐。
