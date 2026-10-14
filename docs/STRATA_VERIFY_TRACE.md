# `STRATA_VERIFY_TRACE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Verifier のハンドシェイクを調べる診断用トレースを有効にします。ホスト側では GPU の到達通知、CPU による応答、plan/copy のフラグなどを記録し、GPU 側では各 layer の処理地点に時刻印（breadcrumb）を書きます。通常の推論設定を切り替える変数ではなく、Verifier のエラー診断に情報を追加するためのフックです。

## 値と判定

CUDA/HIP 実装と SYCL 実装の共通 helper `env_on()` は `std::getenv()` の結果を次のように判定します。

| 値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF |
| 先頭文字が `0` | OFF（例: `0`, `0abc`） |
| その他 | ON（例: `1`, `true`, `false`, `2`, ` 1`） |

文字列全体の parse、数値変換、大文字小文字の正規化はありません。名前空間スコープの `const bool g_trace` 初期化時に一度読みます。したがって、プロセス起動後に環境を書き換えても判定は変わりません。

## 有効になる条件

このフックが使われるのは Strata の CUDA/HIP 用 verifier（`src/core/verify.cpp`）または SYCL 用 verifier（`sycl/src/core/verify.cpp`）を含むビルドで、Verifier が初期化される経路です。変数が ON でも、Verifier を使わない実行経路ではトレースは記録されません。

GPU breadcrumb 用の mapped memory の確保に失敗した場合、その領域は無効化されます。その場合もホストイベントの記録・ダンプは可能ですが、GPU breadcrumb は出ません。初期化時の `on` ログは領域確保の成否にかかわらず出力されます。

## 実行時の詳細

Verifier 初期化時、stderr に `strata verify trace (#649): on` を出します。HIP ビルドでは加えて coherent words、doorbell の方式と、`HIP_HOST_COHERENT`、`HSA_ENABLE_SDMA`、`GPU_MAX_HW_QUEUES` の現在値も表示します。これはそれらの変数をこの機能が設定するという意味ではなく、診断ログへの併記です。

ホストイベントは全 verifier で共有する 4096 件の ring buffer に記録され、ダンプ時には末尾最大160件を出します。各イベントには経過時刻、window、step/layer、補助値、seq/flag/A/B の値を含みます。GPU breadcrumb 領域は verifier ごとに確保され、window ごとにゼロクリアされます。ダンプ時は GPU が到達した layer と、その近辺の記録済み処理地点を出します。

出力は常時の逐次ログではありません。`trace_dump()` は `NEVER-RANG` のエラー経路や、通常の verifier の timeout 診断で呼ばれ、timeout 時は GPU wait を解放する前後の状態も記録します。pipelined verifier の一部の `service()` エラー経路はイベントを記録しても、その場で `trace_dump()` を呼びません。したがって、ON にしただけで各 window の詳細が stdout/stderr に流れるわけではありません。出力先は診断呼び出し元が渡す `stderr` 等です。

## 根拠

- `src/core/verify.cpp:192-200`, `sycl/src/core/verify.cpp:92-100` — 値判定と起動時の `g_trace` 初期化。
- `src/core/verify.cpp:367-376,419-475`, `sycl/src/core/verify.cpp:288-297,343-399` — 共有 ring buffer、イベント形式、最大160件のダンプ、GPU breadcrumb 表示。
- `src/core/verify.cpp:716-731`, `sycl/src/core/verify.cpp:612-626` — breadcrumb 領域の確保と初期化ログ。
- `src/core/verify.cpp:2267-2269,2333-2355`, `sycl/src/core/verify.cpp:2217-2246` — window の記録、never-rang / timeout の診断経路。
- `src/core/verify.cpp:3445-3450,3503-3515`, `sycl/src/core/verify.cpp:3664-3669,3744-3765` — pipelined 経路では記録箇所とダンプ箇所が異なること。
- `docs/DETAILS.md` には `STRATA_VERIFY_TRACE` の利用者向け説明や測定値は見つかりませんでした。
