# `PA_BENCH_REF`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`PA_BENCH_REF` は、Strata 同梱の手動ベンチマーク `pa_bench` が、現在の prompt attention 出力と別 variant の出力ファイルを比較するための参照ファイル名です。通常の Strata engine や server の設定ではありません。対象コードは `tests/cuda/pa_bench.cpp` にあり、CUDA 版は `STRATA_BUILD_TESTS AND STRATA_ENABLE_CUDA` のとき `pa_bench` としてビルドされます。HIP 側にも同じソースから `hip_pa_bench` が定義されています（`CMakeLists.txt:624-628,1104-1107`）。

## 値と判定

値は文字列として取得され、数値変換や文字列比較はありません。環境変数の値そのものを参照ファイルのパスとして `fopen(..., "rb")` に渡します。

| 状態 | 挙動 |
|---|---|
| 未設定 | 参照ファイルを開かず、比較を行わない。 |
| 設定済みの空文字 | `getenv` は非 null なので比較経路に入るが、空文字をパスとして開けず、エラー表示なしで比較を行わない。 |
| 設定済みの非空文字 | その文字列をパスとして開く。開けなければエラー表示なしで比較を行わない。 |
| ファイルが開け、出力要素数分を読み込めた | 参照値との相対 RMS 差、最大絶対差、参照値の RMS を標準出力に表示する。余分な末尾データは検査しない。 |
| ファイルが開けたが要素数分を読めない | `PA_BENCH_REF <値>: short file` を標準出力に表示し、ベンチマークはその後も続行する。 |

参照ファイルは `float` のバイナリ列として読み、要素数は現在の出力ベクトルと同じ `T * NH * HD` です。比較値は `sqrt(sum((out-ref)^2) / max(sum(ref^2), 1e-30))`、最大絶対差は全要素の `|out-ref|` の最大値です。空白、相対パス、絶対パス、NUL を含まない通常の環境変数文字列について、アプリケーション独自の正規化や妥当性検証はありません（`tests/cuda/pa_bench.cpp:98-99,106-120`）。

## 有効になる条件

この変数を読むのはベンチマーク実行ファイルのみです。`pa_bench` は `STRATA_BUILD_TESTS AND STRATA_ENABLE_CUDA` の CMake 条件内で定義されます。`hip_pa_bench` は HIP 用テスト・診断ターゲットを定義するブロック内にあります。Strata の通常実行ファイルや Python server がこの名前を読み取る箇所はありません（`CMakeLists.txt:624-628,1104-1107`; 名前全体の参照検索では `tests/cuda/pa_bench.cpp` のみ）。

ベンチマーク起動時に `main` が出力を計算した後で読み取ります。CLI の dump 引数や任意の反復回数は参照パスを上書きしません。対になる `PA_BENCH_OUT` が設定されていて正常に開けた場合、現在の出力を別ファイルへ書きますが、`PA_BENCH_REF` の値との優先順位はありません（`tests/cuda/pa_bench.cpp:22-26,98-106,123-125`）。

## 実行時の詳細

`pa_bench` は dump に記録された選択で prompt attention kernel を反復実行し、出力をホストへコピーした後に `PA_BENCH_REF` を調べます。参照ファイルを開けて全要素を読めた場合は比較結果を `printf` で標準出力へ表示します。ファイルを開けない場合は何も表示せず、短い場合も診断後に `return 0` まで進みます。したがって、この比較失敗だけを理由とする非ゼロ終了経路はありません。環境変数を static cache する処理はなく、`main` 内のこの位置で一度だけ読み取ります（`tests/cuda/pa_bench.cpp:22-26,98-126`）。

## 根拠

- 直接の環境変数読み取り、比較処理、短いファイルの表示: `tests/cuda/pa_bench.cpp:106-120`。
- ベンチマークの CLI と参照読み取り前の出力計算: `tests/cuda/pa_bench.cpp:22-26,98-105`。
- 比較対象の出力ファイルを書き出す `PA_BENCH_OUT`: `tests/cuda/pa_bench.cpp:123-125`。
- CUDA/HIP ベンチマークターゲット定義: `CMakeLists.txt:624-628,1104-1107`。
