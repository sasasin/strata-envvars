# `STRATA_POOL_SPIN_US`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU expert pool の worker が、仕事を待つ間に spin してから sleep に移るまでの時間をマイクロ秒単位で指定する。未設定時は 20 ms。短くすると worker は早く condition variable で待つ。ソースコメントはこの値を test knob と呼んでいる。これは worker 数や実行する仕事を変更する設定ではない。読み取りは `ExpertPool` のコンストラクターだけで行う（`engine/src/kernels/cpu/pool.cpp:803-809`）。

## 値と判定

環境変数が未設定なら初期値の `kSpinBeforeSleep`（20 ms）が使われる。設定されていれば値全体の検証やエラー報告をせず `std::atoi` に渡し、変換後の整数と 0 の大きい方をマイクロ秒数として保存する。したがって空文字や数字で始まらない文字列（`true`、`false` を含む）は `atoi` の結果 0、`0anything` も 0、`12abc` は 12、`-5` は 0 になる。先頭の空白と符号は `atoi` の変換規則に従う。数値として `int` に収まらない文字列の結果はこの実装から保証できない。大文字小文字の区別はない（文字列比較はしない）。

| 条件 | unset | 有効になる値（例） | 無効・丸められる値（例） |
|---|---|---|---|
| `ExpertPool` が生成される build | 20 ms | `1` → 1 µs、`20000` → 20 ms | 空文字、`abc`、`true`、`false`、`0anything` → 0 µs、`-5` → 0 µs |

根拠: `engine/include/strata/kernels/cpu/pool.hpp:297-304`、`engine/src/kernels/cpu/pool.cpp:803-809`。

## 有効になる条件

- 通常の `strata` / `strata-q36` 実行ファイルで Qwen 3.6 の経路を使い、CPU expert pool が build に含まれる必要がある。CMake は `STRATA_NATIVE_EXPERTS` が有効なとき `strata_qwen35` に CPU pool をリンクし、`STRATA_Q36_CPU_POOL=1` を定義する（`engine/cmake/strata_gpu_engine.cmake:565-583`）。
- モデルの routed experts が VRAM に収まらず hybrid pool が必要な場合、または MTP block の experts が CPU pool に置かれる場合に、その pool が生成される。全 routed experts が VRAM に収まる経路では pool を作らない（`engine/src/qwen35/q36_engine.cu:4330-4345, 4528-4539`）。
- `STRATA_NATIVE_EXPERTS=OFF` の build ではこの pool を利用できず、必要な experts が VRAM に収まらない場合は `the routed experts (...) do not fit in VRAM, and this build has no CPU expert pool (STRATA_NATIVE_EXPERTS=OFF)` のエラー経路になる（`engine/src/qwen35/q36_engine.cu:4337-4343`）。
- この pool の生成時に CLI 引数や別の環境変数が spin 時間を上書きするコードはない。`--pool-workers` は pool の worker 数を渡すが、spin 時間には作用しない（`engine/src/qwen35/q36_engine.cu:4528`、`engine/src/kernels/cpu/pool.cpp:803-809`）。

## 実行時の詳細

`ExpertPool` の各インスタンスのコンストラクターが環境を一度読み、インスタンスの `spin_before_sleep_` に保存する。関数内 static やプロセス共有 cache はなく、その pool の存続中に環境を変更しても保存値は変わらない。新しい pool を作れば、その時点の環境値を読み直す（`engine/src/kernels/cpu/pool.cpp:803-809`、`engine/include/strata/kernels/cpu/pool.hpp:378-384`）。

worker は仕事がない間 pause を続ける。通常の経路は 1024 回ごと、MSVC x64 の対応経路は UMWAIT を使い 16 回ごとに経過時間を確認する。設定時間を経過すると `sleep_cv_` で待ち、`publish()` が epoch を進めて sleeper がいることを確認した場合に通知する。このため移行は設定時間ちょうどではなく、時間確認の周期に依存する。0 µs でも最初の pause / UMWAIT と時刻確認を経て sleep 判定に進む。値が変えるのは worker の待機方法であり、ここで生成 token や expert の選択を変える処理はない（`engine/src/kernels/cpu/pool.cpp:1049-1059, 1062-1113`）。

## ログと測定値

この設定値を表示するログ、無効値の警告、専用のエラー経路は読み取り箇所にない。実測の速度・CPU 使用率の数値は、現行 Strata の資料にこの変数について示されていないため記載しない。worker の状態を出す pool 診断は別の診断経路であり、設定値そのものを記録しない（`engine/src/kernels/cpu/pool.cpp:783-800, 803-809`）。

## 根拠

- `engine/src/kernels/cpu/pool.cpp:803-809` — 環境変数の唯一の読み取り、変換、0 未満の clamp。
- `engine/include/strata/kernels/cpu/pool.hpp:297-304, 378-384` — 既定 20 ms、設定値の用途と保存先。
- `engine/src/kernels/cpu/pool.cpp:1049-1059, 1062-1113` — publish による wake と worker の spin / sleep。
- `engine/cmake/strata_gpu_engine.cmake:565-583` — Qwen 3.6 CPU pool の build 条件。
- `engine/src/qwen35/q36_engine.cu:4330-4345, 4528-4539` — hybrid 条件、pool 生成、および pool がない build の失敗経路。
