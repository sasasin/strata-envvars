# `HIP_HOST_COHERENT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata はこの名前の環境変数を HIP 条件付きの verify trace 初期化ログに表示するだけで、値を parse したり Strata 内のメモリ確保・同期方式を切り替えたりしない。共通 engine の `Verifier::init` と SYCL 側の同名初期化処理にある `std::getenv` は、いずれも `STRATA_VERIFY_TRACE` が有効で trace 領域が未確保のときに実行される `fprintf(stderr, ...)` の引数である。`HIP_HOST_COHERENT` 自体を Strata の動作設定として扱う根拠はこの checkout にはない。（`engine/src/core/verify.cpp:333-344,1245-1260`; `engine/sycl/src/core/verify.cpp:187-194,800-814`）

## 値と判定

値の真偽判定、文字列比較、数値変換は行わず、存在する値をログへそのまま渡す。ログの条件コンパイルが有効な場合の表示は次のとおり。（`engine/src/core/verify.cpp:1252-1257`; `engine/sycl/src/core/verify.cpp:806-811`）

| 条件（build・実行時） | 未設定 | 設定時の表示 | Strata 内で有効になる値 |
|---|---|---|---|
| `STRATA_USE_HIP` 定義、かつ `STRATA_VERIFY_TRACE` が有効で trace 領域が未確保 | `HIP_HOST_COHERENT=-` | 空文字は `HIP_HOST_COHERENT=` の後が空欄。`0`、`1`、`true`、`false`、前後空白を含む文字列などは内容を変換せず表示 | なし。値に応じた分岐はない |
| `STRATA_USE_HIP` 未定義、または trace 初期化ログの条件外 | 読み取られない | 表示されない | なし |

空文字も `getenv` が非 null を返すため「設定あり」の表示になるが、空文字を有効・無効と分類する Strata の判定はない。値の妥当性検査、大小文字の正規化、clamp、既定値の選択もない。（`engine/src/core/verify.cpp:1255`; `engine/sycl/src/core/verify.cpp:809`）

## 有効になる条件

- ログ出力箇所は `#if defined(STRATA_USE_HIP)` の内側にある。定義がない build では、同じ trace 初期化条件でも `strata verify trace (#649): on` のみを出し、この変数は参照しない。（`engine/src/core/verify.cpp:1252-1260`; `engine/sycl/src/core/verify.cpp:806-814`）
- trace 初期化ログには `g_trace && trace_h_ == nullptr` が必要。`g_trace` は `STRATA_VERIFY_TRACE` を `env_on` で読み、値が未設定・空文字・先頭文字が `0` なら false、それ以外なら true とする。これはログ経路の条件であり、`HIP_HOST_COHERENT` の値判定ではない。（`engine/src/core/verify.cpp:336-344,1245-1260`; `engine/sycl/src/core/verify.cpp:151-155,187-194,800-814`）
- CLI 引数、サーバーモード、モデル状態、別の Strata 設定によって `HIP_HOST_COHERENT` を有効化または上書きするコードは見つからなかった。CUDA/HIP ランタイムなど外部側が同名を読む場合の意味や効果は、この Strata 文書の対象外。

## 実行時の詳細

`HIP_HOST_COHERENT` は `Verifier::init` の trace 初期化ログを組み立てる時点で `std::getenv` により読み取られ、値を保存する cache はない。対してログを出すかどうかの `g_trace` は namespace scope の `const bool` として `env_on("STRATA_VERIFY_TRACE")` の結果を保持するため、実行中に同変数を変えても trace の有効条件は変わらない。trace 条件に入ると Strata は先に breadcrumb 用の mapped 領域を試し、その成否にかかわらず条件ブロック内で HIP 診断行を出す。環境の子プロセスへの継承・上書きはこのコード経路では行わない。（`engine/src/core/verify.cpp:336-344,1245-1260`; `engine/sycl/src/core/verify.cpp:151-155,187-194,800-814`）

この変数が verify 計算結果、doorbell の方式、終了状態、失敗経路を変える処理はない。表示される `coherent words` と `doorbell` の状態はそれぞれ `STRATA_VERIFY_COHERENT` と `STRATA_DOORBELL_STORE` から作る別の Strata フラグであり、`HIP_HOST_COHERENT` の値ではない。（`engine/src/core/verify.cpp:333-344,1252-1257`; `engine/sycl/src/core/verify.cpp:187-194,806-811`）

## ログと測定値

`STRATA_USE_HIP` 定義下では stderr に `strata verify trace (#649): on; coherent words %s, doorbell %s, HIP_HOST_COHERENT=%s HSA_ENABLE_SDMA=%s GPU_MAX_HW_QUEUES=%s\n` の形式で出す。未設定時の対象値は `-`、設定時は環境文字列そのもの。trace 初期化の条件外、または HIP 条件コンパイル外では対象値を含むログは出ない。（`engine/src/core/verify.cpp:1245-1260`; `engine/sycl/src/core/verify.cpp:800-814`）

性能・正確性の測定値は該当しない。`docs/DETAILS.md` にもこの環境変数の動作説明は見つからなかった。

## 根拠

- `engine/src/core/verify.cpp:333-344,1245-1260` — HIP 用 verify フラグ、trace 条件、対象値のログ出力。
- `engine/sycl/src/core/verify.cpp:187-194,800-814` — SYCL 側の同条件・同形式のログ出力。
