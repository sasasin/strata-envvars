# `PA_BENCH_OUT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`pa_bench` / `hip_pa_bench` が prompt attention の実行結果を、比較用の生バイナリファイルとして保存する出力先です。Strata 本体のサーバーや通常の推論経路を設定する環境変数ではありません。CUDA 版ターゲットは `STRATA_BUILD_TESTS` と `STRATA_ENABLE_CUDA` が有効なときに定義され、HIP 版もテスト用ターゲットとして定義されます（`CMakeLists.txt:333-334,624-628,1104-1107`）。ソース冒頭の説明では、記録済み QSA 選択を使った kernel variant の A/B 比較用ベンチマークとされています（`tests/cuda/pa_bench.cpp:1-4`）。

## 値と判定

この変数は文字列や数値として parse されません。`std::getenv("PA_BENCH_OUT")` の結果が null かどうかだけを判定します（`tests/cuda/pa_bench.cpp:123-125`）。

| 値 | Strata 側の処理 |
|---|---|
| 未設定 | 出力ファイルを開かず、保存処理をスキップする。 |
| 空文字を含む設定値 | 非 null なので、その文字列をそのまま `std::fopen(o, "wb")` に渡す。 |
| その他の設定値 | 値を変換・検証せず、その文字列を `std::fopen(o, "wb")` に渡す。 |

CLI 引数との優先順位はありません。CLI の `DUMP` と任意の `reps` は入力データと反復回数を指定し、`PA_BENCH_OUT` は計算後の出力保存先を指定します（`tests/cuda/pa_bench.cpp:22-25,98-125`）。別の設定値による fallback や clamp はありません。

## 有効になる条件

- `pa_bench` または `hip_pa_bench` をビルドして実行する必要があります。少なくとも CUDA 版はテストビルドかつ CUDA 有効時にのみ CMake ターゲットとして追加されます（`CMakeLists.txt:624-628`）。HIP 版は CMake のテスト用ターゲット群に `hip_pa_bench` として追加されます（`CMakeLists.txt:333-334,1104-1107`）。
- 実行時に入力 dump の読み込みと `qsa_prompt_attn_batch` の呼び出しが成功し、出力処理まで到達した場合にのみ保存を試みます。kernel が処理を辞退した場合は stderr に `qsa_prompt_attn_batch declined` と出して終了コード 1 になり、出力保存には進みません（`tests/cuda/pa_bench.cpp:85-90,122-126`）。
- OS/backend/build macro、サーバーモード、モデル状態や他の環境変数による追加判定は、この変数の読み取り箇所にはありません。ビルド対象と実行環境は前述の CMake 条件に従います。

## 実行時の詳細

ベンチマーク反復と出力統計の表示後に、環境変数を一度読みます。読み取り結果は static cache されません（`tests/cuda/pa_bench.cpp:84-105,123-125`）。値が設定されていて出力ファイルを開けた場合、計算済み `out` 配列を `float` の生バイト列として書き込み、ファイルを閉じます。配列長は `T * NH * HD` 要素です（`tests/cuda/pa_bench.cpp:36-40,98-101,123-125`）。

出力先を開けなかった場合、`fopen` の失敗は無視されます。`fwrite` / `fclose` の戻り値も検査されないため、保存失敗を示す Strata のログや終了コード変更はありません。空文字も同じ経路で `fopen` に渡されます。ベンチマーク自体が正常に終われば、この保存処理の失敗だけで非 0 終了にはなりません（`tests/cuda/pa_bench.cpp:123-126`）。成功時も保存先の表示ログはありません。標準出力には保存処理より前に median/min 時間、反復数、出力 hash、RMS が表示されます（`tests/cuda/pa_bench.cpp:104-105`）。

## 根拠

- 変数の直接読み取りと `fopen` / `fwrite` / `fclose`: `tests/cuda/pa_bench.cpp:123-125`。
- ベンチマーク入力、kernel 呼び出し、失敗時の stderr と終了: `tests/cuda/pa_bench.cpp:22-35,84-96,105-126`。
- 結果配列と出力統計: `tests/cuda/pa_bench.cpp:36-40,98-105`。
- CUDA / HIP ベンチマークターゲット: `CMakeLists.txt:624-628,1104-1107`。
