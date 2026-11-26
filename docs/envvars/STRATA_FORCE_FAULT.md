# `STRATA_FORCE_FAULT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_FORCE_FAULT=<m>:<bias>` は、検証ウィンドウの FP32 head logits からログ確率を計算する直前に、token ID が `m` の倍数である要素へ `bias` を加えるテスト用 fault injection です。対象は `window_logprobs` のローカルなホスト側コピー `h` であり、GPU 上の logits や生成・採択する token を書き換えません。CUDA/HIP 共通ソースと Metal 共通ホストソースでこの処理を含みます（`engine/src/core/verify.cpp:4435-4481`、`engine/cmake/strata_gpu_engine.cmake:305-316`、`engine/metal/CMakeLists.txt:31,90-94,135-140`）。

## 値と判定

関数内の `static` 初期化で `std::getenv` を一度呼び、`std::sscanf(v, "%lld:%f", &m, &b) == 2` かつ `m > 0` の場合だけ有効にします。`%lld` と `%f` の2変換が成功すればよく、文字列末尾まで消費したかは検査しません。したがって、例えば `7:0.3tail` も受理されます。`m` は正の `long long` として読み、`int64_t` にし、正値の上限 clamp はありません。`bias` は `%f` で読み、追加の範囲・有限値検査はありません（`engine/src/core/verify.cpp:4471-4477`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 読み取り箇所に到達するビルド | `(m,bias)=(0,0)` として処理し、加算なし | `7:0.3`、`1:-2`、`7:0.3tail` | 空文字、`7`、`7:x`、`0:0.3`、`-7:0.3` |

変換はロケールに従う C の `scanf` 形式です。`%lld` は数値変換前の空白と符号を受け付け、`%f` も変換前の空白を受け付けます。一方、書式中の `:` は直後に一致する必要があるため `7 :0.3` は失敗します。大文字小文字のフラグ判定はなく、真偽値文字列としても読みません。空文字は未設定とは異なりますが、2変換に失敗して無効値と同じく無効化されます。無効値でも警告やエラーは出さず、`(0,0)` に fallback します（`engine/src/core/verify.cpp:4472-4477`）。

## 有効になる条件

- この読み取りコードを含む CUDA/HIP または Metal ビルドであること。Metal は macOS 専用の別 CMake プロジェクトです。SYCL の `engine/sycl/src/core/verify.cpp` の対応関数にはこの fault 処理がありません（`engine/cmake/strata_gpu_engine.cmake:310-316`、`engine/metal/CMakeLists.txt:18-19,135-140`、`engine/sycl/src/core/verify.cpp:3105-3159`）。
- 値が有効であることに加え、`Verifier::window_logprobs` が呼ばれること。通常のプロンプト採点経路では `STRATA_LOGPOS` のファイルが開けた場合に呼ばれます。decode 採点経路では `STRATA_FOLLOW` による強制継続があり、`STRATA_FOLLOW_LOGPOS` の出力ファイルが開けた場合に呼ばれます（`engine/src/program/generate.cpp:20453-20466,21681-21708,23018-23040`）。これらのログ確率出力を使わない通常の生成では、この変数を読まず、効果もありません。
- 対応する呼び出しは `--serve` の生成ループ内にあります。エンジン自身にこの変数専用の CLI 引数はなく、別の環境変数による上書き規則もありません（`engine/src/program/generate.cpp:4069,20415-20418,21681-21703`）。
- `terminal/tools/force_check.py` は `--env K=V` をエンジン子プロセスへ渡せます。ツールは親環境の `STRATA_*` を除いた後、設定ファイルの `env`、続いて `--env` を適用するため、同名なら `--env` が設定ファイルより優先します。ツールはエンジンを `--serve` で起動します（`terminal/tools/force_check.py:72-84,145-150,187-208`）。

## 実行時の詳細

`window_logprobs` は Metal では Metal ウィンドウから、それ以外のこの共通ソースの経路では CUDA head buffer から logits をホストの `h` にコピーします。その後、関数内 `static` の初期化式が `STRATA_FORCE_FAULT` を読みます。`next_` がある場合は先に次段へ委譲するため、実際の読み取りは委譲先で行われます。環境値はそのプロセスで最初に読み取りブロックへ到達した時に一度だけ解析され、以後の環境変更は反映されません（`engine/src/core/verify.cpp:4435-4481`）。

有効時は各行について `v = 0, m, 2m, ...`（`v < n_vocab_`）の `h[t*n_vocab_+v]` に `bias` を加えます。token ID 0 も常に対象です。`m=1` なら語彙内の全 ID、`m >= n_vocab_` なら ID 0 だけが対象になります。変更後の `h` から argmax、log-sum-exp、対象 token の log probability、追加 token の確率、および有効な場合の top-k を計算して出力します（`engine/src/core/verify.cpp:4478-4521`）。

この操作は採点値だけを変えます。プロンプト経路では採点の後に verifier の commit が行われ、decode 経路では `outv` と採択数 `a` を決めた後に採点関数を呼びます。したがって、この fault によって生成 token、強制継続 token、decode の採択判定が変わる経路ではありません（`engine/src/program/generate.cpp:20445-20467,23018-23040,23042-23070`）。

## ログと測定値

有効値・無効値のどちらでも、この変数専用のログ、警告、終了経路はありません。`window_logprobs` の出力先が開いていれば、変更後のスコアがその既存の TSV 行へ書かれます。無効値は無言で無効化されます（`engine/src/core/verify.cpp:4471-4481,4501-4521`）。採点関数自体が失敗した場合、decode 側は `strata serve: STRATA_FOLLOW_LOGPOS: <error>` を stderr に出します。これは fault 値の検査結果ではなく、ログ確率取得の失敗経路です（`engine/src/program/generate.cpp:23038-23040`）。Strata の資料にこの変数の測定値はありません。

## 根拠

- `engine/src/core/verify.cpp:4435-4481` — logits の取得、環境変数の解析、加算対象。
- `engine/src/core/verify.cpp:4482-4521` — 加算後の argmax・確率計算と出力。
- `engine/src/program/generate.cpp:20453-20467,21681-21708,23018-23040` — ログ確率の有効化条件と呼び出し側。
- `engine/cmake/strata_gpu_engine.cmake:305-316`、`engine/metal/CMakeLists.txt:18-19,31,90-94,135-140`、`engine/sycl/src/core/verify.cpp:3105-3159` — backend ごとのビルド／対応実装。
- `terminal/tools/force_check.py:72-84,145-150,187-208` — テストツールからの子プロセス環境設定と優先順位。
