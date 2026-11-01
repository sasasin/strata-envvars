# `S20_ROWDIAG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`S20_ROWDIAG` は、CUDA/HIP の fused MoE native-format 比較テスト `prefill_fused_iq_test` にある診断用環境変数です。テストのタイミング処理で fused 結果と MMQ 結果の差が大きい上位 12 pair について、token、expert、fused row、および相対誤差を stdout に表示します。Strata の通常実行ファイルが読む設定ではありません。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | 追加の行診断を出さない |
| 設定あり（空文字を含む） | 行診断を実行する |

実装は `std::getenv("S20_ROWDIAG")` の null 判定だけを行います。文字列の内容、数値、先頭文字は調べません。`static` 変数への保存はなく、`timing_part()` が呼ばれるたびに環境を読み直します。CLI 引数や他の環境変数による値の上書きはありません。

## 有効になる条件

- `prefill_fused_iq_test` がビルドされて実行されること。CMake では GPU backend の設定範囲内かつ `STRATA_BUILD_TESTS` が有効な場合にこのテスト実行ファイルを追加します。
- テストが GPU の有無や対応 kernel の検査を通過すること。GPU がない場合や必要な kernel がない場合はテストが skip され、診断箇所に到達しません。
- timing part が実行されること。`--no-timing` を指定した場合は呼ばれません。`--only=NAME` や `--chunks=A,B` は処理する pair / chunk を変えるため、診断対象もその実行範囲に限られます。

この変数はテスト診断の表示だけを制御します。誤差値に対する追加の合否判定はありません。

## 実行時の詳細

`timing_part()` は fused path と MMQ path の計測・比較を行い、grouping の異常があれば先に例外を投げます。grouping が正常で `S20_ROWDIAG` が設定されている場合、各 routed pair の出力行ごとに最大絶対差 `me` と MMQ 側の最大絶対値 `mr` を計算し、`mr > 0` なら `me / mr`、そうでなければ `me` を誤差として降順に並べます。上位 12 件を stdout に出力します。診断ブロックには誤差値による追加の失敗判定はありません。ただし、行データの GPU からのコピーは通常の `ck(cudaMemcpy, ...)` を通るため、そのコピー自体が失敗すれば例外経路（parity failed と例外文を stderr に出し、終了コード 1）に入ります。テストが最後まで完了すれば parity passed を stdout に出します。

## 根拠

- `tests/cuda/prefill_fused_iq_test.cpp:582-603`: 環境変数の存在判定、誤差計算、上位 12 件の表示。
- `tests/cuda/prefill_fused_iq_test.cpp:307-310`: 診断用 row source データの GPU からのコピーとエラー伝播。
- `tests/cuda/prefill_fused_iq_test.cpp:433-435`: 診断ブロックを含む `timing_part()` の定義。
- `tests/cuda/prefill_fused_iq_test.cpp:649-687,700-740,743-745`: GPU / kernel による skip、CLI による実行範囲、タイミング処理の呼び出し、テストの終了・失敗表示。
- `CMakeLists.txt:2305-2315`: `STRATA_BUILD_TESTS` 条件での `prefill_fused_iq_test` の追加と登録。
- `docs/envvars/000_envvers.md:553` は候補名の一覧であり、通常実行時の環境変数であることを示す根拠ではありません。この commit で `S20_ROWDIAG` の完全一致参照は上記テストファイルの 1 箇所だけです。
