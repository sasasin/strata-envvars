# `HIP_HOST_COHERENT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリ・GPU ドライバー（HIP/ROCm runtime）が読む環境変数の動作は説明対象外。

## 役割

Strata のソースは `HIP_HOST_COHERENT` を**表示のためにだけ**読む。値を解釈し、分岐・設定・転送に使う箇所はない。この変数自体の実際の効果（host memory の coherent 挙動）は HIP/ROCm runtime 側のもので、Strata の挙動ではない。

読み取りは `src/core/verify.cpp` の verify trace ログ 1 箇所（SYCL に同一ロジックのミラー `sycl/src/core/verify.cpp:629`）。

## 値と判定

Strata 側は値を parse しない。`std::getenv("HIP_HOST_COHERENT")` が非 null ならその文字列をそのまま、null（未設定）なら `-` を print する。

| 状態 | ログに出る表示 |
|---|---|
| 未設定（`nullptr`） | `-` |
| 空文字 `""` | 空（`getenv` は非 null を返すので `-` ではなく空文字列を表示） |
| `1`, `0`, `true` など | 設定された文字列をそのまま |

判定は「設定されているかどうか」だけで、内容・数値・大文字小文字は検査しない。Strata はこの値で何もしない。

根拠: `src/core/verify.cpp:704`（`std::getenv("HIP_HOST_COHERENT") ? std::getenv("HIP_HOST_COHERENT") : "-"`）。

## 有効になる条件（ログが出る条件）

この表示が出るのは、次の両方のときだけ。

- ビルドが HIP（`#if defined(STRATA_USE_HIP)`）。CUDA ビルドではこの行そのものが無く、`strata verify trace (#649): on` だけを出す（`src/core/verify.cpp:707-708`）。
- verify trace が有効。`g_trace = env_on("STRATA_VERIFY_TRACE")`（`src/core/verify.cpp:180`）が true で、trace breadcrumbs の初期化時（`src/core/verify.cpp:691-706`）に stderr へ 1 行 print される。

## 実行時の詳細

print される行（`src/core/verify.cpp:702-706`）:

```
strata verify trace (#649): on; coherent words <explicit|default>, doorbell <stored|incremented>, HIP_HOST_COHERENT=<value or -> HSA_ENABLE_SDMA=<value or -> GPU_MAX_HW_QUEUES=<value or ->
```

- `coherent words` の `explicit`/`default` は Strata 自身の設定 `g_coherent = env_on("STRATA_VERIFY_COHERENT")`（`src/core/verify.cpp:177`）で、`HIP_HOST_COHERENT` とは別。
- `HIP_HOST_COHERENT`・`HSA_ENABLE_SDMA`・`GPU_MAX_HW_QUEUES` は外部 runtime が読む変数で、Strata はそれらの値をこの行に echo するだけ。Strata 側でこれらの値に基づく分岐はない。
- 読み取りは trace 初期化の 1 回だけ。static cache ではなく、その時点で環境の現在値を表示する。

## 観測できる結果

stderr への 1 行の trace ログ。値の有無・内容を変えても Strata の計算・I/O・API 動作は変わらない（表示のみ）。

## 根拠

- 読み取り（表示のみ）: `src/core/verify.cpp:704`。
- ログ行と gate: `src/core/verify.cpp:691-706`、`g_trace` `180`、`g_coherent` `177`。
- SYCL ミラー: `sycl/src/core/verify.cpp:627-629`。
- 外部変数であることの区別: Strata は `HIP_HOST_COHERENT` を解釈せず echo するだけ。ROCm/HIP runtime 側の意味は本調査の対象外。
