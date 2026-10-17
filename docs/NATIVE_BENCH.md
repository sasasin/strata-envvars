# `NATIVE_BENCH`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。Strata 所有ソースのみを対象とし、外部ライブラリの環境変数動作は対象外。

## 役割

SYCL 版の開発・診断用プログラム `native_expert_parity` で、GPU の `native_expert_grouped` カーネルを追加計測します。通常の Strata エンジンの推論経路が読む設定ではありません。`sycl/CMakeLists.txt` では `STRATA_NATIVE_EXPERTS` が有効な場合にこのプログラムをビルドします。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | 追加計測を行わない |
| 空文字を含む設定済みの値 | 追加計測を行う |

判定は `std::getenv("NATIVE_BENCH") != nullptr` のみです。値を文字列や数値として parse せず、`1` 以外の値、`0`、空文字も設定されていれば同じ扱いです。CLI 引数や設定ファイルによる上書きはありません。判定は各レイヤーの処理中に行われ、結果を static cache しません。

## 有効になる条件

- SYCL の `native_expert_parity` 実行ファイルが `STRATA_NATIVE_EXPERTS` を有効にしてビルドされていること。
- 有効な GGUF shard を渡し、対象レイヤーに gate/up/down expert tensor があり、`native_fmt()` が対応形式として受理すること。
- SYCL GPU 処理まで正常に到達すること。

ビルド時に設定される `STRATA_NATIVE_EXPERTS` はビルド条件であり、`NATIVE_BENCH` とは別の環境変数です。通常の Strata エンジンや、同名の CUDA/HIP 側 parity 実行ファイルがこの環境変数を読む実装は、この HEAD のソース検索では確認できませんでした。

## 実行時の詳細

プログラムはまずそのレイヤーの通常の GPU parity 計算を行います。`NATIVE_BENCH` が設定されている場合、同じ重み blob を 10 個の device allocation に複製し、4 entry ずつ、合計 40 expert 計算となる grouped call を構成します。ウォームアップとして一度呼び出して完了を待った後、20 回呼び出し、完了を待ちます。表示する時間はその経過時間を20で割った1レイヤー分の host-wall 時間で、`GPU grouped: 10 experts x 4 entries: ... ms per layer call  (... GB/s of expert bytes)` の形式で stdout に出ます。計測後に追加 allocation を解放します。

変数は各レイヤーの GPU 計算後に読み直されます。プログラム自身が環境を書き換える処理は見つかりませんでした。計測ブロックは parity の合否判定を変更しません。最後の失敗数と終了コードは、通常経路の計算結果で決まります。

`docs/A770_SPEED_SPEC.md` は Coder IQ1_M、A770 での記載例としてレイヤー別の計測値（例: layer 0 は 0.328 ms、layer 47 は 1.205 ms）を記録しています。これは当該文書に記載された条件での測定値であり、他の GPU・モデル・実行条件の性能を示すものではありません。

## 根拠

- `sycl/CMakeLists.txt:386-391` — `STRATA_NATIVE_EXPERTS` による診断実行ファイルのビルド条件。
- `sycl/src/kernels/native_expert_parity.cpp:38-60` — 引数、GGUF とレイヤーの処理開始条件。
- `sycl/src/kernels/native_expert_parity.cpp:219-249` — SYCL GPU parity 計算後に環境変数を判定。
- `sycl/src/kernels/native_expert_parity.cpp:250-289` — 追加の grouped-call 構成、ウォームアップ、20回計測、出力、解放。
- `sycl/src/kernels/native_expert_parity.cpp:291-299` — 環境変数の計測ブロックとは独立した parity 判定と終了コード。
- `docs/INTEL.md:268-271`, `docs/A770_SPEED_SPEC.md:630-645` — 開発用 profiling の説明と A770 の記載値。計測仕様の説明はソース実装を根拠とした。
