# `HSA_ENABLE_SDMA`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリや GPU ドライバーが読む環境変数の動作は対象外。

## 役割

Strata がこの変数を使って行うのは、HIP verifier の診断トレース行に現在の環境値を表示することだけです。Strata のソースには値を解析して SDMA の使用やコピー経路を変更する処理はありません。ROCm/HSA 側での意味や効果は、この調査の対象外です。

## 値と判定

| 状態 | Strata の診断出力 |
|---|---|
| 未設定 | `HSA_ENABLE_SDMA=-` と表示 |
| 設定済み（空文字を含む） | `HSA_ENABLE_SDMA=` の後に環境値をそのまま表示 |

値の真偽判定、数値変換、大文字小文字の正規化は行われません。文字列を設定内容のまま `%s` で出力します。Strata 内でこの値に既定値を設定したり、他の設定より優先させたりする処理はありません。

## 有効になる条件

表示は verifier の診断トレースが有効で、HIP ビルドである場合に限られます。トレースは `STRATA_VERIFY_TRACE` を `env_on()` で判定して有効化します。この helper は、未設定・空文字・先頭が `0` の値を無効、それ以外を有効とします。したがって、`HSA_ENABLE_SDMA` を設定しただけでは、この値は出力されません。

CUDA ビルドでは同じトレース分岐が `strata verify trace (#649): on` のみを出し、`HSA_ENABLE_SDMA` は表示しません。SYCL 側も同じ条件・表示構造です。

## 実行時の詳細

`Verifier` の初期化で、GPU trace 用の mapped buffer がまだない場合に `g_trace` を確認します。トレースが有効なら buffer を確保し、その箇所で HIP ビルドだけ stderr に `HIP_HOST_COHERENT`、`HSA_ENABLE_SDMA`、`GPU_MAX_HW_QUEUES` の値を出します。`HSA_ENABLE_SDMA` の取得は `std::getenv()` による診断出力時の読み取りで、結果を保存して後続処理に使うコードはありません。環境値をプロセス起動後に変更した場合にログへ反映されるかは、診断行が出る初期化タイミングによります。

この変数を文字列として参照する箇所は CUDA と SYCL の verifier に各1箇所です。HIP adaptive copy に関するソースコメントにも名前が登場しますが、そこでは外部設定の性能影響について言及するだけであり、Strata が `HSA_ENABLE_SDMA` を読み取る実装ではありません。

## 根拠

- `src/core/verify.cpp:172-180` — `STRATA_VERIFY_TRACE` の判定。未設定・空文字・先頭文字 `0` を無効にする `env_on()` と、静的な `g_trace`。
- `src/core/verify.cpp:694-709` — CUDA/HIP verifier 初期化時のトレース設定。HIP 分岐でのみ `HSA_ENABLE_SDMA` を取得して診断文字列へ渡す。
- `sycl/src/core/verify.cpp:620-634` — SYCL verifier の対応箇所。
- `src/program/generate.cpp:173-196`、`sycl/src/program/generate.cpp:193-215` — adaptive swap のコピー経路に関するコメント。`HSA_ENABLE_SDMA` はコメント中の参照で、環境読み取りではない。
