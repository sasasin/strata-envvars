# `STRATA_DISPATCH_REPORT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

dispatch 統計が有効なプロセスの正常終了時に、カーネル選択や graph launch など Strata が集めたカウンターを JSON ファイルへ書きます。変数の値は出力先パスとして使われ、生成処理の選択や計算方法そのものは変えません。統計収集を有効にする別変数は `STRATA_DISPATCH_STATS` です。

## 値と判定

`write_report()` は `std::getenv("STRATA_DISPATCH_REPORT")` の値を読みます。未設定 (`nullptr`) または空文字 (`p[0] == '\0'`) なら書き込みません。空でない値は文字列全体を検証・変換せず、そのまま `fopen(path, "wb")` のパスとして使います。相対パスの基準は実行プロセスの作業ディレクトリです。

| 状態 | 結果 |
|---|---|
| 未設定 | レポートを書かない |
| 空文字 | レポートを書かない |
| 空でない値 | その値を出力パスにして JSON を書く |
| パスを開けない | `fopen` が失敗し、Strata はログを出さずに終了する |

出力は `"wb"` で開くため、同名ファイルがあれば切り詰めます。親ディレクトリの作成、書き込み量の検査、失敗時の警告・エラー表示は実装されていません（`include/strata/core/dispatch_stats.hpp:107-112`）。

## 有効になる条件

- `STRATA_DISPATCH_STATS` が未設定、空文字、または先頭文字が `0` 以外なら統計収集が有効です。先頭文字が `0` の値（`0`, `0anything` など）では無効です。文字列全体の parse はせず、空文字は有効側です（`include/strata/core/dispatch_stats.hpp:115-120`）。
- `Stats` が初めて取得された時点で `STRATA_DISPATCH_STATS` を評価し、その結果を `on_` に保持します。有効ならその場で `atexit` handler を登録します。したがって `STRATA_DISPATCH_REPORT` を設定しても、統計が無効で handler が登録されなければレポートは出ません。
- `STRATA_DISPATCH_REPORT` の読み取りコード自体に OS / backend / build macro による条件分岐はありません。ただし実行ファイルで統計コードがコンパイルされ、`Stats::get()` が呼ばれる必要があります。確認した呼び出し箇所は共通の verify 実装と CUDA kernel 実装にあります（`src/core/verify.cpp:1391-1395,3211`; `src/kernels/cuda/native_mmvq.cu:3569`; `src/kernels/cuda/iq_kernels.cu:6273`; `src/kernels/cuda/fused_gr.cu:1623`）。
- CLI の `--stats` は別機能です。引数は `o.stats` を設定し、該当出力箇所は token / pool 等の時間・処理量を stdout に表示します。`STRATA_DISPATCH_REPORT` の JSON 出力を有効にする処理ではありません（`src/program/generate.cpp:3674,20569-20592`）。

## 実行時の詳細

`STRATA_DISPATCH_REPORT` はプロセス起動時ではなく、`atexit` handler から呼ばれる `write_report()` の実行時に読みます。そのため、統計が有効で handler 登録後でも、終了前に環境値を変更すれば handler が参照するパスは変更後の値になります。対して `STRATA_DISPATCH_STATS` は `Stats` の初回構築時に一度だけ評価され、後から変更しても `on_` や handler 登録は変わりません（`include/strata/core/dispatch_stats.hpp:107-120`）。

レポート本体は `json()` が作る `launches` と `counts` の JSON です。`launches` は graph launch 回数、`counts` は kernel / 状態メモの集計です（`include/strata/core/dispatch_stats.hpp:77-105`）。verify window の統計 scope と状態メモは `src/core/verify.cpp:1391-1396`、集計対象の kernel 呼び出し例は `src/kernels/cuda/native_mmvq.cu:3569` にあります。統計が有効でも対象処理が実行されなければ、その項目は集計されません。

この変数について Strata が出す警告・エラー・終了ステータス変更は確認できません。出力ファイルを開けない場合も `fopen` の戻り値を無視しており、JSON は残らず、Strata 独自のログもありません（`include/strata/core/dispatch_stats.hpp:111`）。

## 根拠

- `include/strata/core/dispatch_stats.hpp:107-112` — レポート用変数の読み取り、未設定・空値判定、JSON生成、パスへの書き込み。
- `include/strata/core/dispatch_stats.hpp:115-120` — `STRATA_DISPATCH_STATS` の初回評価、統計の既定有効、終了時 handler 登録。
- `include/strata/core/dispatch_stats.hpp:77-105` — JSON の内容。
- `src/core/verify.cpp:1391-1396,3211` — verify window の集計 scope / 状態記録と graph launch 集計。
- `src/kernels/cuda/native_mmvq.cu:3569`, `src/kernels/cuda/iq_kernels.cu:6273`, `src/kernels/cuda/fused_gr.cu:1623` — CUDA kernel 経路での kernel 集計呼び出し例。
- `src/program/generate.cpp:3674,20569-20592` — CLI `--stats` の設定と別の stdout 統計表示。
