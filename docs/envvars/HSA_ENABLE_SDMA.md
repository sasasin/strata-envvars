# `HSA_ENABLE_SDMA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata はこの値を演算や SDMA の有効・無効判定に使わず、HIP の verifier trace 初期化ログにそのまま表示する。したがって、Strata 内ではこの変数による処理選択・既定値・fallback はない。読み取り箇所は CUDA/HIP 共通の `engine/src/core/verify.cpp` と SYCL 側の `engine/sycl/src/core/verify.cpp` にあり、どちらも `STRATA_USE_HIP` が定義されたビルドでのみ当該値をログへ渡す（`engine/src/core/verify.cpp:1245-1260`; `engine/sycl/src/core/verify.cpp:800-814`）。

## 値と判定

`std::getenv("HSA_ENABLE_SDMA")` の null 判定だけを行い、未設定なら `-`、設定済みなら文字列を `%s` でそのまま出力する。空文字列も「設定済み」なので空欄として出る。数値・真偽値への変換や文字列検証はない。

| 条件 | unset | 表示される値の例 | Strata 内で値として有効になる例 |
|---|---|---|---|
| `STRATA_USE_HIP` 定義かつ verifier trace 初期化ログを出す経路 | `-` | 空文字は空欄、`0` は `0`、`1` は `1`、`true` は `true`、`false` は `false`、`0anything` は `0anything` | 該当なし。いずれもログ表示だけで、値による分岐はない |
| `STRATA_USE_HIP` 非定義 | HSA の値を読まず、このログ行にも出さない | 該当なし | 該当なし |

大文字小文字、空白、数値としての妥当性、境界値は Strata では検査されない。CLI 引数や他の環境変数による値の上書き・優先順位もない。

## 有効になる条件

- HSA 値を読むログは、`STRATA_USE_HIP` 定義時に限られる。非 HIP ビルドでは trace が有効でも `strata verify trace (#649): on` のみを出し、HSA 値は読み取らない（`engine/src/core/verify.cpp:1252-1260`; `engine/sycl/src/core/verify.cpp:806-814`）。
- HIP ビルドでも `g_trace` が真で、かつ `Verifier::init` が `trace_h_ == nullptr` の trace 初期化ブロックに入る必要がある（`engine/src/core/verify.cpp:1245-1257`; `engine/sycl/src/core/verify.cpp:800-811`）。`g_trace` は `STRATA_VERIFY_TRACE` を `env_on` で評価し、未設定・空文字・先頭文字が `0` の値では無効、それ以外の非空文字列では有効になる（`engine/src/core/verify.cpp:336-344`; `engine/sycl/src/core/verify.cpp:151-153,187-191`）。
- この条件は HSA 値を表示するかどうかだけを決める。Strata は `HSA_ENABLE_SDMA` の内容を理由に警告、終了、エラー処理を行わない。

## 実行時の詳細

`STRATA_VERIFY_TRACE` の `g_trace` は namespace-scope の `const bool` としてプロセスの初期化時に評価されるため、起動後に同変数を変更しても trace の有効・無効は切り替わらない（`engine/src/core/verify.cpp:336-344`; `engine/sycl/src/core/verify.cpp:151-153,187-191`）。一方、`HSA_ENABLE_SDMA` は上記初期化ブロックで `getenv` され、関数内 static などへの保存はない。HSA 値を変えても Strata の計算・コピー経路は変わらず、その後に同ブロックが再度実行される場合のログ表示にだけ関係する（`engine/src/core/verify.cpp:1245-1257`; `engine/sycl/src/core/verify.cpp:800-811`）。

Strata ソースには、この名前を使って子プロセスへ転送する処理や、値に応じて待ち時間・timeout・モデル状態を変更する処理は見つからない。外部ライブラリや GPU driver が同名をどう扱うかは、この文書では Strata の挙動として扱わない。

## ログと測定値

HIP ビルドで trace 初期化ブロックに入ると stderr に `strata verify trace (#649): on; coherent words ...; doorbell ..., HIP_HOST_COHERENT=... HSA_ENABLE_SDMA=... GPU_MAX_HW_QUEUES=...` の形式で出る。HSA 部分は未設定なら `-`、設定済みなら実際の文字列であり、空文字は空欄になる。trace が無効、trace 初期化ブロックに入らない、または非 HIP ビルドの場合、この HSA 表示はない（`engine/src/core/verify.cpp:1245-1260`; `engine/sycl/src/core/verify.cpp:800-814`）。

`engine/src/program/generate.cpp:603-607` と `engine/sycl/src/program/generate.cpp:225-229` には `HSA_ENABLE_SDMA=0` に関するコメントがあるが、これらの箇所はコメントのみで、この環境変数を読み取ったり設定したりしない。条件を伴う Strata の測定記録として確認できる根拠ではないため、性能値や外部側の挙動はここでは記載しない。

## 根拠

- `engine/src/core/verify.cpp:1245-1260` — trace 初期化条件、HIP 条件付き stderr 出力、未設定時の `-`。
- `engine/sycl/src/core/verify.cpp:800-814` — SYCL 側の同等処理。
- `engine/src/core/verify.cpp:336-344`、`engine/sycl/src/core/verify.cpp:151-153,187-191` — `STRATA_VERIFY_TRACE` の評価規則と評価時期。
- `engine/src/program/generate.cpp:603-607`、`engine/sycl/src/program/generate.cpp:225-229` — 環境変数を読まないコメント箇所。
