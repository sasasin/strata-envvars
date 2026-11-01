# `STRATA_EXPERT_SPLIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更は表示されていなかった。

## 役割

SYCL エンジンの i-quant 等の expert gate/up と down の計算で、既定の lane kernel ではなく、複数の入力列をまとめて処理する multi-entry kernel を選ぶ opt-in スイッチです。適用される型では、値が有効で、かつ `STRATA_OLD_IQ_MMVQ` が無効のときに切り替わります。CUDA/HIP 側の同名変数読み取りは、この commit のソース全体検索では見つかりませんでした。

## 値と判定

`env_on()` は `std::getenv()` の結果が null でなく、先頭文字が NUL と `'0'` のどちらでもない場合に true を返します。文字列全体の parse や数値変換はしません。

| 設定値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（先頭文字が NUL） |
| `0` または `0...` | 無効 |
| `1`、`2`、`true`、`false`、空白で始まる非空文字列など | 有効（先頭文字が NUL / `'0'` 以外） |

大文字小文字、後続文字、数値としての妥当性は検査しません。したがって `false` も有効扱いです。既定値は無効です。読み取り箇所には CLI 引数や設定ファイルによる上書きはありません。別変数 `STRATA_OLD_IQ_MMVQ` が有効なら、このスイッチが有効でも旧 kernel を選びます（同変数も同じ `env_on()` 判定です）。

## 有効になる条件

- SYCL エンジンをビルドして実行する経路であること。カーネルソースは `sycl/CMakeLists.txt` の SYCL kernel source リストから `strata_kernels` に入り、エンジンからリンクされます。
- 対象の型の compile-time `kSplit<T>` が true であること。現在 true なのは IQ2_XXS、IQ2_XS、IQ2_S、IQ3_XXS、IQ3_S、IQ1_M、IQ4_NL、IQ4_XS、Q2_0、および TQ 型 144–146 です。`kSplit<T>` が false の型は環境変数が有効でも lane kernel を使います。
- `STRATA_OLD_IQ_MMVQ` が有効でないこと。これが有効なら対象型も lane kernel 経路を選択します。

CUDA/HIP backend、OS、server mode、CLI 引数、モデル全体の状態による別の環境変数判定は、この変数の読み取り・分岐箇所にはありません。実際に切り替わるのは、対象型が SYCL カーネルの gate/up または down の該当 launcher に渡された場合です。

## 実行時の詳細

値は `sycl/src/kernels/cuda/iq_kernels.dp.cpp` の namespace-scope `g_split_multi` 初期化時に一度読み込まれます。以降の kernel launch はその bool を参照します。プロセス起動後に環境を変更しても再読込されません。SYCL server wrapper は `STRATA_` 変数をコンテナへ転送しますが、値が空文字またはちょうど `0` の場合は転送を省きます。どちらも engine では無効になるため判定結果は同じです。この変数の値を加工する処理はありません（`sycl/serve/strata-sycl.sh:28-48`）。

対象型の `launch_gu()` と `launch_down()` は、`g_old_kernels || !g_split_multi` なら lane kernel を起動し、それ以外なら multi kernel を起動します。gate/up の multi kernel は自身の grid で `native_gu_multi_kernel` を起動し、down は `native_down_multi_kernel` を起動します。IQ2_XXS、IQ2_XS、IQ2_S、IQ1_M では別の `STRATA_IQ_STAGE_GRID` の状態により multi kernel 内の grid staging の有無も変わりますが、これは `STRATA_EXPERT_SPLIT` 自体の判定とは別の設定です。

この環境変数の読み取りや分岐に対応する専用ログ、警告、終了処理はありません。設定有無を標準出力・標準エラーに報告するコードもありません。既存の `docs/INTEL.md` はこの設定を Off と記載し、`=1` の説明に decode の低下を記していますが、ここではその資料の測定値を独立に検証したものとして扱いません。

## 根拠

- 読み取り helper、環境変数の namespace-scope 初期化、旧 kernel との関係: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3200-3211`。
- `kSplit<T>` の既定と true になる型: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:957-964,1018,1050,1087,1126,1171,1219,1244,1272,1309-1311`。
- gate/up と down の選択分岐および multi kernel 起動: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4571-4634`。
- staging 設定の追加条件: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3212-3223,4598-4605`。
- SYCL kernel のソース登録とライブラリ構成: `sycl/CMakeLists.txt:237-251,253-263`。
- SYCL server wrapper の環境変数転送: `sycl/serve/strata-sycl.sh:28-48`。
- Intel 向け資料上の既定値と測定記述: `docs/INTEL.md:1-9,400`。
