# `QSA_BENCH_HASH`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`qsa_select_bench` が計算した高速 scorer の score buffer からハッシュ値を出力する診断用スイッチです。Strata の通常エンジンの QSA 選択や scorer の選択を変更しません。比較対象の scorer 計算と top-k 比較は、この変数の有無にかかわらず実行されます。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未設定 | ハッシュを出力しない |
| 設定あり（空文字を含む） | 高速 scorer の score 値を走査し、`fast scores hash %016llx` を標準出力へ追加する |

値の内容は比較・変換されません。`std::getenv("QSA_BENCH_HASH")` が null かどうかだけを一度確認するため、`1`、`0`、その他の文字列、空文字はすべて同じ有効扱いです。既定値は未設定で、ハッシュ出力なしです。

ハッシュは初期値 `1469598103934665603` から開始し、各 score の 32-bit 表現を `h = (h ^ u) * 1099511628211` で順に畳み込みます。走査対象は各 query の block index `j < nbid` で、末尾 block は含みません。値は `%016llx` 形式の16桁16進数で表示されます。

## 有効になる条件

この変数を読むのは `src/kernels/qsa_select_bench.cpp` の `qsa_select_bench` だけです。通常の Strata 実行ファイルやサーバーはこの名前を読みません。CMake ではテスト関連ビルドで CUDA または HIP が有効な場合にのみベンチマーク実行ファイルを定義します。CUDA は `STRATA_BUILD_TESTS`、HIP は `STRATA_BUILD_TESTS` または `STRATA_PARITY_PROMPT_ATTN` が条件です。

`QSA_BENCH_DECODE` が設定されていると、ベンチマークは decode 用 score 計算を計測して出力した後に return します。その経路は `QSA_BENCH_HASH` の判定位置より前に終了するため、両方が設定されても hash 行は出ません。

## 実行時の詳細

通常の比較経路では、warp scorer と高速 scorer の score 計算、top-k、GPU 同期、score buffer のホストへのコピーを行った後に、この環境変数を確認します。設定時は高速 scorer のホスト側 score buffer `b` を走査して hash 行を出力し、その後も選択結果の比較、FP64 参照との誤差判定、時間計測、最終結果の出力へ進みます。従って変数が変えるのは追加ログのみです。

値は `main()` のこの位置で読み取られ、一度限りの `getenv` 判定です。プロセス中に設定を変更して再評価するコードや、子プロセスへの転送処理はありません。Strata の資料にはこの環境変数の説明や hash 値の測定結果は見当たりません。

## 根拠

- `src/kernels/qsa_select_bench.cpp:35-41`: ベンチマークの引数と既定値。
- `src/kernels/qsa_select_bench.cpp:73-95`: `QSA_BENCH_DECODE` 分岐が hash 判定より先に終了する。
- `src/kernels/qsa_select_bench.cpp:96-118`: scorer の計算、比較準備、score buffer のコピー。
- `src/kernels/qsa_select_bench.cpp:119-130`: 環境変数の有無判定、hash の対象・計算・出力。
- `src/kernels/qsa_select_bench.cpp:131-212`: hash 出力後に比較・精度判定・時間計測を続ける。
- `CMakeLists.txt:470-490`: CUDA/HIP のテスト関連ビルドにおける実行ファイルと CTest 定義。
