# `STRATA_FILL_SERIAL`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL エンジンで、expert cache を expert profile から事前充填するときの GGUF 読み込みパイプラインを無効にし、従来の逐次充填を選びます。主な対象は `--stream-experts` を使った経路です。この変数は読み込み・コピー順序を切り替えます。expert profile の選択や cache slot の数は変えません。

この名前を値として読む実装は `sycl/src/program/generate.cpp` にあります。CUDA/HIP の `src/` および `include/`、Python サーバーやセットアップに同名の読み取り箇所はありませんでした。

## 値と判定

数値や文字列を parse せず、`std::getenv("STRATA_FILL_SERIAL") != nullptr` の設定有無だけで判定します。

| 値 | 判定 |
|---|---|
| 未設定 | 他の条件を満たせばパイプラインを使う |
| 空文字、`0`、`1`、`false`、その他の文字列 | 設定済みとして扱い、パイプラインを使わない |

大文字小文字、空白、数値の妥当性、値の範囲は調べません。したがって `STRATA_FILL_SERIAL=0` もシリアル経路を選びます。根拠: `sycl/src/program/generate.cpp:4607-4613`。

## 有効になる条件

profile が空でなく、expert source が存在するときに profile fill が実行されます。パイプラインを選ぶ条件は、次のすべてです。

- `srcp` が `GgufExpertSource`（`gguf_src`）を指す。通常は `--stream-experts` が有効で `--mmap-experts` が無効な経路。
- per-layer admission が無効。
- `STRATA_FILL_SERIAL` が未設定。

このため、変数が未設定でも、profile fill がない場合、source が GGUF 直読みではない場合、または per-layer admission が有効な場合は、この変数に関係なくパイプラインを使いません。`--stream-experts` の経路は native (IQ) pack と `--native SHARD1` を要求します。根拠: `sycl/src/program/generate.cpp:4151-4167,4593-4613`。

## 実行時の詳細

判定は profile fill の箇所で行われ、関数内 static cache には保存されません。profile fill 自体はモデル起動中に一度実行されると実装コメントにあります。そのため、環境変数の変更が判定に影響し得るのはこの判定より前です。充填後に値を変えても、完了済みの充填方法は変わりません。根拠: `sycl/src/program/generate.cpp:4593-4605,4612`。

変数が未設定で条件を満たす既定経路では、まず profile 順に slot を確保し、その後 layer/expert 順に並べた expert を最大 64 個ずつ、page-locked host memory の二つの batch に読み込みます。読み込み worker 数は `hardware_concurrency()` を基に 2〜8 に制限されます。ある batch の GPU へのコピーを進めている間に、別の batch を読み込みます。

変数が設定されていると、このパイプライン分岐を通らず、profile 順に各 expert の blob を得て `fill_slot_blocking()` で slot へ充填します。両経路とも充填後に `profile fill: ... (pipelined|serial)` の stderr ログを出します。パイプライン経路では pinned memory の確保失敗や GGUF 読み込み失敗で stderr にエラーを出して終了します。逐次経路の充填失敗は pair 番号とエラー内容を stderr に出します。根拠: `sycl/src/program/generate.cpp:4614-4667,4726-4751`。

## ログと測定値

`docs/INTEL.md:605-611` は、2026-10-02 の起動時間の記録として、expert cache fill が GGUF からの読み込みの大部分を占め、Coder の 23.4 GiB と IQ2_XS の 24.9 GiB で測定したと説明しています。冷えた page cache で fill は 76.2 秒から 18.8 秒（0.33 から 1.34 GB/s）、engine 起動から最初の token までは Coder で 82 秒から 26 秒、IQ2_XS で 120 秒から 41 秒となり、出力は同一だったと記載されています。同資料は `STRATA_FILL_SERIAL=1` を旧方式としています。これらは同資料にある測定記録であり、他の環境での所要時間や速度を保証するものではありません。

実装上、環境変数の設定有無はパイプラインを選ぶかどうかだけに使われます。性能・出力への影響は上記の資料上の記録であり、この調査では新たな測定をしていません。

## 根拠

- `sycl/src/program/generate.cpp:4151-4167` — `--stream-experts` 時の GGUF expert source 選択。
- `sycl/src/program/generate.cpp:4593-4613` — profile fill の一度限りの実行とパイプライン判定。
- `sycl/src/program/generate.cpp:4614-4667` — slot admission、pinned batch、並列読み込みとコピー。
- `sycl/src/program/generate.cpp:4726-4751` — シリアル充填と経路別の所要時間ログ。
- `docs/INTEL.md:605-611` — 旧方式と新方式の起動時間測定記録。
