# `ONEAPI_DEVICE_SELECTOR`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Strata 本体の C++/Python は、この名前を `getenv` や `os.environ` で読み取って値を解釈しない。Strata がこの値に関与するのは Intel SYCL セットアップと起動経路である。Intel GPU が複数あるとき、`sycl/setup_intel.py` は選択 GPU に応じた値を設定ファイルの `env` に既定値として書き、既存の同キー設定があれば保持する。サーバーは設定ファイルの `env` を engine 子プロセスの環境へ反映し、SYCL 起動ラッパーは `ONEAPI_*` を Docker コンテナへ渡す。したがって Strata 側の動作は値の生成・設定・転送であり、セレクターの書式やデバイス選択結果を Strata が検証・決定する処理ではない（`sycl/setup_intel.py:479-498`, `serve/server.py:4428-4441`, `sycl/serve/strata-sycl.sh:13-16,33-43`）。

## 値と判定

Strata による文字列の parse、大小文字変換、数値変換、値域検証はない。既存設定値はセットアップが上書きせず、サーバーが文字列化して子環境へ設定する。SYCL ラッパーは値が `0` または空文字なら Docker に渡さず、それ以外はそのまま渡す。この `0` は文字列との完全一致であり、`00` や `0anything` はこのフィルターでは除外されない（`setup_intel.py:494-498`, `server.py:4440-4441`, `strata-sycl.sh:39-43`）。

| 条件 | 未設定 | Strata が設定・転送する値 | Strata の値判定 |
|---|---|---|---|
| Intel SYCL セットアップ、検出カードが 2 枚以上、設定 `gpu` が単一 index | `cfg["env"]` に同キーがなければ `level_zero:<index>` を追加 | 既存 `cfg["env"]["ONEAPI_DEVICE_SELECTOR"]` があればその値を保持。生成値では `index` は選択 index（範囲外なら 0） | セレクターを parse しない |
| 同じく `gpu` が list の split 設定 | 同キーがなければ `level_zero:*` を追加 | 既存設定があれば保持 | セレクターを parse しない |
| 1 枚の Intel GPU、または通常の非 SYCL 実行 | このセットアップ箇所からは設定しない | server の親環境またはプロファイル `env` に値があれば、SYCL ラッパー経由では空文字と正確な `0` 以外を転送 | Strata は意味を判定しない |

セットアップ時に「ユーザーが設定した値」として保持されるのは設定ファイル `cfg["env"]` の値であり、セットアッププロセスの環境変数を読み取って保持する処理ではない（`sycl/setup_intel.py:479-498`）。

## 有効になる条件

- セットアップによる既定値の生成は、Linux の Intel SYCL セットアップで `len(intel) > 1` の場合だけ行われる。Windows では SYCL セットアップ自体が拒否され、単一カードではこの箇所は既定値を追加しない（`setup.py:8323-8325`, `sycl/setup_intel.py:494-498`）。
- 単一 GPU 用の既定値は選択された `cfg["gpu"]` index、split 用は `level_zero:*`。設定の選択 GPU はコマンドラインや config から `cfg["gpu"]` に反映された後で使われる（`sycl/setup_intel.py:481-491,494-498`）。
- 実行時の設定ファイル `env` は親プロセス環境に重ねられるため、同じキーが両方にあれば設定ファイル値が優先される（`serve/server.py:4431-4441`）。
- `strata-sycl.sh` が使われる SYCL 実行では `ONEAPI_*` をコンテナへ渡す。ただし値が空文字または正確な `0` の場合はラッパーが渡さない（`sycl/serve/strata-sycl.sh:33-43`）。
- CUDA/HIP/CPU 実行に対して、この変数を解釈する Strata 本体の分岐は確認できない。

## 実行時の詳細

Intel セットアップの `write_run_script` は設定 JSON を読み、複数カード時に必要なら `env` の既定値を追加して同じ JSON を書き戻す。その後の通常 server 起動スクリプト自体は設定値を export せず、`serve/server.py` が `child_env` で親環境を複製し、config の `env` を上書き適用する。engine 実行ファイルとして `strata-sycl.sh` を使う構成では、ラッパーが環境中の `ONEAPI_*` を列挙して `docker run -e` に渡す（`sycl/setup_intel.py:479-498,530-533`, `setup.py:8253-8266`, `serve/server.py:4428-4441,10175-10183`, `sycl/serve/strata-sycl.sh:33-52`）。

セットアップ時の値生成は run script 作成時に行われる。実行中に Strata がこの変数を再読込または cache する箇所はない。サーバーの子プロセス環境は engine 起動時に構築される。ラッパーを通る値の `0` / 空文字フィルターもコンテナ起動時に適用される。

## ログと測定値

この変数自体について Strata の警告・成功ログ・エラー文言はない。Strata 所有の `tools/vision/own/vit_sycl.cpp:254-268` は GPU を列挙し選ぶコードと、セレクターが一覧を filter するとのコメントを含むが、当該ファイルにこの環境変数を読むコードはない。ggml-SYCL 内部には `getenv("ONEAPI_DEVICE_SELECTOR")` があるが、これは `third_party/strata-llama/...` の依存コードであり、本書ではその内部動作を Strata の挙動として説明しない（`third_party/strata-llama/ggml/src/ggml-sycl/dpct/helper.hpp:915`, `ggml-sycl.cpp:184`）。

## 根拠

- `sycl/setup_intel.py:479-498,530-545` — config の読み込み、複数カード時の既定 selector、config 保存と SYCL 起動。
- `serve/server.py:4428-4441,10175-10183` — config `env` を engine 子環境へ重ねる処理と engine 起動経路。
- `setup.py:8253-8266` — run script は server を起動する。
- `sycl/serve/strata-sycl.sh:13-16,33-52` — `ONEAPI_*` のコンテナ転送と空文字・`0` の除外。
- `tools/vision/own/vit_sycl.cpp:254-268` — Strata 所有 SYCL vision reader の GPU 列挙（対象変数の読み取りはない）。
- `third_party/strata-llama/ggml/src/ggml-sycl/dpct/helper.hpp:915`, `third_party/strata-llama/ggml/src/ggml-sycl/ggml-sycl.cpp:184` — 候補名の依存コード内参照。依存コードの動作は対象外。
