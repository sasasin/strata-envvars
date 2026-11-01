# `DS4_LAUNCH_CHECK`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `main...origin/main` で、未コミット変更はなかった。

## 役割

DeepSeek-V4.1 エンジンの CUDA/HIP カーネル launch 直後に、`cudaGetLastError()` で取得したエラー状態を stderr に記録する診断用スイッチです。設定しても launch の選択や引数は変えず、エラー確認と報告を追加します。対象は `src/dsv41/ds4_launch.h` の共通 launch helper を使うデバイス launch です。

## 値と判定

値の文字列や数値は parse せず、`std::getenv("DS4_LAUNCH_CHECK") != nullptr` で設定有無だけを判定します。

| 環境変数の状態 | 判定 | 動作 |
|---|---|---|
| 未設定 | 無効 | launch error をこの helper では確認・報告しない |
| 設定あり（空文字を含む） | 有効 | launch 直後に `cudaGetLastError()` を呼び、成功以外なら stderr に記録 |

`1`、`0`、`false`、任意の文字列はいずれも設定されていれば同じ扱いです。CLI 引数や別環境変数による値の上書き、無効値時の fallback はこの実装にありません。

## 有効になる条件

- `src/dsv41/ds4_launch.h` の実装は `__CUDACC__`、`__HIPCC__` または `__HIP__` のいずれかが定義され、かつ `STRATA_METAL` が未定義の場合に限ってコンパイルされます。Metal ではこの変数を読まず、CPU-only のコードパスにもこの launch checker はありません。
- CMake の `STRATA_BUILD_DSV41` は既定で `OFF` です。オプションを有効にし、`STRATA_HIP_GFX906` による除外条件に当たらない場合に `strata-dsv41` がビルド対象になります。したがって通常ビルドに必ず入る設定ではなく、DSV41 CUDA/HIP エンジンを含むビルドで対象 launch が実行される場合の診断です。
- 設定値は各 `strata_ds4_launch_at` 関数テンプレート特殊化の最初の呼び出し後に、その特殊化の `static const bool` に cache されます。その特殊化ではプロセス実行中に環境を書き換えても再評価されません。

## 実行時の詳細

`strata_ds4_launch(...)` マクロは呼び出し元の `__FILE__` と `__LINE__` を共通 helper に渡し、helper はカーネルを launch した直後に設定有無を判定します。チェックが有効なら `cudaGetLastError()` の結果を確認し、成功以外の場合に次の情報を stderr に出します: `ds4 launch failed at <file>:<line>: <error string> (grid ... block ... shared ...)`。grid、block、shared memory サイズも記録されます。

この分岐にはエラー後の明示的な throw、return、abort はありません。確認したエラーを表示した後も helper は呼び出し元へ戻るため、この環境変数自体は失敗を停止・回復させる機能ではありません。値が未設定の場合、helper は追加のエラー確認や診断ログを行いません。

## 根拠

- `src/dsv41/ds4_launch.h:5-21` — CUDA/HIP と非 Metal のコンパイル条件、launch の直後に行う設定有無判定、cache、`cudaGetLastError()`、stderr の文言・launch 情報。
- `src/dsv41/ds4_gguf.cu:4-5,206-212`、`src/dsv41/ds4_kernels.cu:5-6,2128-2130` — 共通ヘッダーを含み、複数の GPU launch が `strata_ds4_launch` を使う例。
- `CMakeLists.txt:906-920` — DSV41 専用エンジンのビルド設定、既定 OFF、HIP GFX906 の除外条件、および実行ファイルのソース一覧。
- `setup.py:8391-8396` — セットアップ側の DSV41 engine 環境構築は `os.environ` を複製し、ライブラリ検索パスを追加する実装。`DS4_LAUNCH_CHECK` 専用の変換・上書きはない。
