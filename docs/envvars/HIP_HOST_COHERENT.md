# `HIP_HOST_COHERENT`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリや HIP runtime がこの変数をどう使うかは対象外。

## 役割

Strata 自身はこの環境変数を動作設定として解釈していません。HIP の verifier trace が有効なとき、stderr の起動ログに環境変数の現在値をそのまま載せ、診断時に環境を記録します。コード上、値によって verifier のメモリ割り当て、同期、計算、結果は変わりません。

## 値と判定

この変数の読み取り箇所では真偽値や数値への変換をせず、`std::getenv("HIP_HOST_COHERENT")` の結果を `%s` に渡します。

| 環境変数の状態 | ログ上の表示 |
|---|---|
| 未設定 | `HIP_HOST_COHERENT=-` |
| 空文字で設定 | `HIP_HOST_COHERENT=`（値部分は空） |
| その他の値（例: `0`, `1`, `false`） | 設定された文字列をそのまま表示 |

大文字小文字、空白、値全体の形式は検査されません。`0` や `false` も、Strata のこのログ処理では特別な意味を持ちません。

## 有効になる条件

- 通常の HIP ビルドでは `STRATA_USE_HIP` が定義されます（`cmake/hip_backend.cmake:94-98`）。
- HIP verifier の trace が有効である必要があります。`STRATA_VERIFY_TRACE` は `src/core/verify.cpp` の `env_on()` で一度だけ評価され、未設定・空文字・先頭文字が `0` の文字列は無効、それ以外は有効です（同ファイル `220-231`）。
- trace の初期化ブロックに入ると、trace 用 mapped memory の確保を試みた後、HIP ビルドだけがこの環境変数を含むログを出します。CUDA ビルドは `strata verify trace (#649): on` のみを出し、この変数を読みません。
- SYCL の verifier ソースにも同じ診断行がありますが、そこも `#if defined(STRATA_USE_HIP)` 内です。通常の SYCL ビルドでこの条件が成立するかは、この調査で確認したビルド定義からは断定しません。

## 実行時の詳細

`src/core/verify.cpp` と `sycl/src/core/verify.cpp` に読み取りが各1箇所あり、いずれも `g_trace && trace_h_ == nullptr` の初期化ブロック内です。trace 用領域の割り当てが失敗しても、そのブロックに入った後なら診断行は出ます。各読み取り時点の環境値をログに反映し、`HIP_HOST_COHERENT` の値を保持したり、子プロセスへ設定したりする Strata の処理はありません。trace を有効にする `g_trace` は静的な定数として初期化されるため、プロセス起動後に `STRATA_VERIFY_TRACE` を変えても trace の有効条件は変わりません。一方、このログの `HIP_HOST_COHERENT` はログ出力時に `getenv()` で取得されます。

実装上のログ形式は次のとおりです。

```text
strata verify trace (#649): on; coherent words ..., doorbell ..., HIP_HOST_COHERENT=... HSA_ENABLE_SDMA=... GPU_MAX_HW_QUEUES=...
```

この行に併記される他の環境変数は、この文書の対象外です。

## 根拠

- `src/core/verify.cpp:220-231`: `env_on()` と `g_trace` の初期化。
- `src/core/verify.cpp:918-934`: trace 初期化ブロックと HIP 条件付きログでの値の読み取り。
- `sycl/src/core/verify.cpp:90-101,621-636`: SYCL verifier 側の同型実装。
- `cmake/hip_backend.cmake:94-98`: HIP runtime target が `STRATA_USE_HIP=1` を定義。
