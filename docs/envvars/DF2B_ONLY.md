# `DF2B_ONLY`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Metal 同梱の DFlash2 ベンチマーク `df2_bench` で、計測する stage を一つに絞ります。通常の Strata 推論エンジンが読む変数ではありません。対象プログラムはランダムデータを使うベンチマークで、context update、8-row block、head/top-k/selector、または stand-in graph の soak を計測します（`metal/tests/df2_bench.cpp:1-9,62-80,419-475`）。

`metal/CMakeLists.txt` は macOS 専用の独立プロジェクトで、`metal/tests/*.cpp` を個別 executable として作ります。このファイルから生成されるターゲット名は `df2_bench` です。通常の CUDA/HIP/SYCL ビルドには含まれません（`metal/CMakeLists.txt:1-5,31-39`）。

## 値と判定

値は `std::getenv` から文字列として読み、文字列全体を大文字小文字を区別して比較します。数値変換、trim、範囲検査はありません。unset は空文字列に置き換えられます。空文字は設定済みですが、どの stage 名にも一致しません。

| 値 | 動作 |
|---|---|
| unset、空文字、`ctx` / `block` / `head` / `soak` 以外 | 全 stage を計測する通常のベンチマーク経路 |
| `ctx` | context update の 1、3、8 rows を計測して終了 |
| `block` | 8 rows・5 layers の block を計測して終了 |
| `head` | head + top-16 + selector を計測して終了 |
| `soak` | stand-in graph を連続実行し、指定秒数の GPU 時間を 5 秒ごとに出力して終了 |

文字列は完全一致です。たとえば `CTX`、`ctx `、`1` は特別扱いされず、全 stage の経路になります。`DF2B_ONLY` の無効値を警告する処理や fallback はありません（`metal/tests/df2_bench.cpp:79,442-475`）。

## 有効になる条件

- macOS の Metal 用 `df2_bench` を実行した場合に限り参照されます。CUDA/HIP/SYCL 本体や `strata` / `strata_ds4` の実行には影響しません（`metal/CMakeLists.txt:1-5,31-39`）。
- 他の `DF2B_*` 変数との優先順位はありません。stage 選択に使うのはこの値の完全一致のみです。
- `DF2B_ONLY` の分岐に入る前に、Metal context/device の初期化、kernel compile、各種ベンチマーク用データや dispatch の準備を行います。標準の Q4 経路では mm4 の CPU 照合も先に実行し、誤差条件を満たさない場合は終了コード 1 で終了します。したがって stage を絞っても、これらの初期化・照合は省略されません（`metal/tests/df2_bench.cpp:62-80,135-164,419-454`）。

## 実行時の詳細

`main()` が `DF2B_ONLY` を一度読み、`only` 文字列に保存します。実行中に環境を変更しても再評価されません。`ctx` は `build_ctx()` を 1、3、8 行で各計測し、`block` は `build_block()`、`head` は `build_head()` を計測します。これらの分岐は計測後に `return 0` します。`soak` は `DF2B_SECS`（別変数、既定 60 秒）で指定した間 stand-in graph を回し、5 秒ごとに GPU 時間 median を stdout に出して `return 0` します。`DF2B_ONLY` がそれ以外なら stage 別計測に続いて full round と taps の計測も行います（`metal/tests/df2_bench.cpp:419-475`）。

stage 計測は 30 回の warm-up 後、`DF2B_ITERS`（既定 200）回の GPU median / p10 / p90 と encode・submit・wait を含む wall time を stdout に出します。各経路で最初に device 名と config を出力します。ここに示した計測はベンチマークプログラムの出力仕様であり、性能値そのものを示すものではありません（`metal/tests/df2_bench.cpp:426-441`）。

## 根拠

- `metal/tests/df2_bench.cpp:1-9` — ベンチマークの目的、stage 名の記載。
- `metal/tests/df2_bench.cpp:62-80` — 起動時の初期化と `DF2B_ONLY` の読み取り。
- `metal/tests/df2_bench.cpp:135-164` — 標準経路で stage 選択前に行う mm4 CPU 照合と失敗終了。
- `metal/tests/df2_bench.cpp:419-475` — 計測方法、stage 分岐、soak、通常経路。
- `metal/CMakeLists.txt:1-5,31-39` — Metal 用独立 CMake プロジェクトと各 test executable の生成。
