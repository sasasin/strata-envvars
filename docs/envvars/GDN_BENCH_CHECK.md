# `GDN_BENCH_CHECK`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

HIP 向けの手動計測プログラム `hip_gdn_stage_bench` を通常の計測経路から比較チェック経路へ切り替えます。GDN の fused / unfused chunked path を FP32 sequential kernels と比較し、fused path が利用できる場合は分割呼び出しも照合します。この変数を読むのはベンチマーク実行ファイルだけであり、Strata の通常の生成・サーバー実行を制御する読み取り箇所は確認できません。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | チェック経路に入らず、各 prompt 長の通常計測と出力・state hash を行う。`GDN_BENCH_SPLIT` が split を有効にしている場合は split-call hash も出す |
| 設定あり | 値の内容に関係なくチェック経路に入る。空文字、`0`、`false` も有効 |

実装は `std::getenv("GDN_BENCH_CHECK")` の null / non-null だけを判定し、文字列の変換や比較はしません。境界値や無効な文字列という区別はありません。CLI 引数は計測対象の prompt 長を指定しますが、この環境変数との優先順位を変える CLI スイッチはありません。

## 有効になる条件

`STRATA_ENABLE_HIP` が有効な CMake 構成で `hip_gdn_stage_bench` をビルドし、その実行ファイルを起動した場合に限られます。CMake はこれを手動実行の計測ツールとして追加しており、CTest の `add_test` には登録していません。CUDA / SYCL の通常実行ファイルや Python サーバーの環境設定としては使われません。

## 実行時の詳細

プログラム起動後、GPU バッファやイベントなどの準備を行った後、`main` 内で一度だけ設定有無を読みます。設定されていれば prompt 長ごとに sequential FP32 reference、unfused recurrence、可能なら fused path の出力・state・history の差を `CHECK ...` 行に表示し、最後に `return 0` します。fused path が取れない場合は `fused path not taken` と表示します。比較値に対する合否閾値や不一致時の非ゼロ終了は、この経路にはありません。CUDA/HIP API 呼び出しが `ck()` で失敗した場合は stderr にエラーを出して終了コード 2 になります。

`GDN_BENCH_REPS` は未設定なら 7、設定時は `atoi` で整数変換した後に最低 1 へ clamp されます。`GDN_BENCH_SPLIT` は未設定または `atoi` の結果が 0 以外なら split 比較を有効にし、空文字・数値でない文字列・`0` は無効にします。どちらも `GDN_BENCH_CHECK` の分岐より前に読み取られますが、チェック経路では使用されません。子プロセスへの転送や起動後の環境変更に関する処理はありません。

## 根拠

- `CMakeLists.txt:1016-1018,1079-1082` — HIP 有効時に手動計測ツールを追加。コメントに `no add_test` とある。
- `tests/hip/gdn_stage_bench.cpp:51-64` — CLI の prompt 長、`GDN_BENCH_REPS` / `GDN_BENCH_SPLIT` の既定値・読み取り、その他 `STRATA_GDN_*` の表示。
- `tests/hip/gdn_stage_bench.cpp:103-153` — `GDN_BENCH_CHECK` の設定有無による比較処理と早期正常終了。
- `tests/hip/gdn_stage_bench.cpp:155-190` — 未設定時の通常計測、hash 表示と split-call 比較。
- `tests/hip/gdn_stage_bench.cpp:25-27` — GPU API エラー時の stderr 出力と終了コード 2。
