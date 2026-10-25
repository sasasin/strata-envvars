# `STRATA_VERIFY_ASYNC_LAUNCH`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの内部動作は対象外。

## 役割

CUDA の `Verifier::run` が CUDA graph を launch する処理を、必要に応じて専用のホストスレッドへ移します。Compute Sanitizer などの計測下で `cudaGraphLaunch` が graph 完了までブロックする場合も、呼び出し元スレッドが GPU の CPU-expert doorbell を処理できるようにする診断向けスイッチです。値を設定しても graph の内容や expert の割り当ては変えず、launch を行うスレッドと、その launch 待ち・エラー確認の方法を変えます。

## 値と判定

| 環境変数 | 判定 | 動作 |
|---|---|---|
| 未設定 | `getenv()` が null | 同期 launch（既定） |
| 空文字 | 設定ありだが先頭文字は `\0` | 同期 launch |
| 先頭文字が `1` | 例: `1`, `10`, `1anything` | launch を別ホストスレッドへ移す |
| その他 | 例: `0`, `true`, ` 1`, `01` | 同期 launch |

文字列全体の parse、数値変換、大文字小文字変換はありません。判定値は `Verifier::run` 内の関数ローカル `static const bool` に保存されます。したがって、最初にこのコードへ到達した後でプロセス環境を変更しても再評価されません。

## 有効になる条件

- `Verifier::run` の graph launch 経路を通ること。直接のバッチ入口 `run_slots` / `run_slot_rows` はそれぞれ `cudaGraphLaunch` を直接呼ぶため、この変数を読みません。
- `STRATA_GPU_METAL` では `run` 冒頭で Metal の `window_run` に戻るため、この launch 設定へ到達しません。
- `STRATA_USE_HIP` または `STRATA_HIP_GFX906` のビルドでは、この変数の判定と `HostGraphLaunch` を使う分岐が除外され、従来の `cudaGraphLaunch` / `cudaStreamQuery` 経路になります。文書上もこのスイッチは CUDA 用で、HIP/SYCL の scheduling は変えないとされています。
- `run` 内で範囲検査、capture、staging などが失敗した場合や、先行する all-resident adaptive gate wait が失敗した場合は、launch 設定の読み取り箇所に到達しません。

## 実行時の詳細

通常の同期モードでは呼び出し元が `cudaGraphLaunch` を実行します。有効時は `HostGraphLaunch` が worker thread を作成し、そこで `cudaSetDevice(device)` を行ってから graph を launch します。呼び出し元は `status()` を確認し、graph の layer doorbell を待ちながら CPU expert を処理します。worker がまだ launch 中なら `status()` は成功を返して service loop を続け、完了後に launch エラーがあれば `query()` または最終的な `finish()` で検出します。`finish()` は worker を join し、launch の実際のエラーを呼び出し元へ返します。エラーは通常の `verify: launch: <CUDA error string>` として返されます。

service loop が早期に失敗して worker がまだ動作中なら、`HostGraphLaunch` の destructor は GPU の mapped wait を解放してから worker を join します。これは launch が graph 内の wait で止まったまま join されるのを避ける処理です。通常終了時は `finish()` で join した後に stream を同期し、stream 同期エラーも `verify: <CUDA error string>` として返します。

## 根拠

- `src/core/verify.cpp:2235-2255` — `Verifier::run` 冒頭の Metal 分岐、引数検査、capture と staging。
- `src/core/verify.cpp:2273-2289` — all-resident gate wait の後にある環境変数読み取り、CUDA/HIP compile guard、launch、launch status の確認。
- `include/strata/core/host_graph_launch.hpp:11-30,35-52` — worker thread、device 選択、launch error の保存・query・join。
- `src/core/verify.cpp:2314-2389,2412-2422` — caller の doorbell service、早期失敗経路、launch finish と stream 同期。
- `src/core/verify.cpp:3012-3027` — batch entry points は別の直接 launch を使う。
- `docs/DETAILS.md:2032-2045` — CUDA diagnostics としての説明、および `host_graph_launch_test` の記載。これは資料上の説明であり、この調査ではビルドやテストを実行していない。
