# `DS4_ENC_TIMES`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek の Metal runtime が dispatch をエンコードする CPU 側の時間を3区間に分けて累積する診断用スイッチです。pipeline state の設定、dispatch 引数の設定、threadgroup memory 設定と dispatch 呼び出しの各区間を計測し、終了時の `mtl:` レポートに合計を出します。GPU 上の実行時間をこの変数で計測するものではありません。

## 値と判定

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 無効。区間時間の加算をしない |
| 空文字を含む任意の設定値 | 有効 |

`std::getenv("DS4_ENC_TIMES") != nullptr` だけで判定し、値の parse、文字列比較、数値変換はありません。したがって `0`、`false`、空文字も有効です。`encode()` 内の関数ローカル `static const bool` に初回評価結果を保存するため、その後プロセス内で環境を変更しても再評価されません。根拠: `metal/src/mtl_rt.mm:709-714`。

## 有効になる条件

- `STRATA_DS4_RUNTIME` が定義された `metal/src/mtl_rt.mm` のビルドであること。
- `encode()` が呼ばれる dispatch 経路を実行すること。
- `DS4_ENC_TIMES` が `encode()` の初回評価時に設定されていること。

Metal の CMake 定義では `ds4_rt_mm` を `STRATA_DS4_RUNTIME=1` でコンパイルし、そのオブジェクトを `strata_ds4` にリンクします。同じ CMake コメントは Qwen engine の `strata` などではこの macro が無効で、同じファイルの DeepSeek runtime 用コードは入らないと説明しています。従って通常の Qwen Metal 実行では、この読み取り・計測経路は有効になりません。根拠: `metal/CMakeLists.txt:151-165`。

## 実行時の詳細

`encode()` は pipeline state を設定する直前に `steady_clock` を読み、pipeline 設定後、引数設定後、dispatch 設定・呼び出し後にも時刻を読みます。有効時には差分をナノ秒に変換し、`g_t_pipe`、`g_t_args`、`g_t_disp` の atomic counter に加算します。引数区間は全引数についての buffer/offset 解決と `setBuffer` または `setBytes` を含みます。dispatch 区間は threadgroup memory の設定（該当する場合）と direct/indirect dispatch 呼び出しを含みます。カウンターはdispatchごとの記録ではなく、プロセス内の累積値です。根拠: `metal/src/mtl_rt.mm:702-750`。

`Context::flush_runs()` が最初に呼ばれると `ds4_report_counts()` を `atexit` に登録します。終了時レポートは stderr に出力され、いずれかの3カウンターが非ゼロなら `mtl: of the encoding: pipeline ... ms, arguments ... ms, dispatch ... ms` の行を追加します。計測カウンターがすべてゼロなら内訳行は出ません。dispatch 実行そのものの分岐や引数は変更せず、追加のホスト時刻読み取りと累積を行います。根拠: `metal/src/mtl_rt.mm:767-774,855-870`。

`docs/DEEPSEEK_MAC.md` は `DS4_ENC_TIMES=1` を他の診断用設定と並べ、「Diagnostics, all off by default」と記載しています（`docs/DEEPSEEK_MAC.md:97-98`）。実装上は `=1` に限定されず、設定有無だけが条件です。

## 根拠

- 環境変数の読み取りと区間計測: `metal/src/mtl_rt.mm:702-750`
- 終了時レポート: `metal/src/mtl_rt.mm:767-774,855-870`
- DeepSeek runtime 専用ビルド条件: `metal/CMakeLists.txt:151-165`
- 診断設定としての文書記載: `docs/DEEPSEEK_MAC.md:97-98`
