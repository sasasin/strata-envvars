# `STRATA_COPY_HIP_PRIO`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。Strata 所有ソースを対象とし、外部ライブラリやHIPランタイム内部の動作は含めない。

## 役割

通常のHIPビルドで、Verifierがexpert転送に使う専用copy streamを高優先度で作るかを指定する。既定では通常のnon-blocking streamを作る。環境変数が有効と判定された場合、HIPから取得した優先度範囲の `hi` を使ってstream作成を試みる。

このstreamは、GPU planで必要になったmiss expertのホストからデバイスへのDMA転送と、その完了後にGPU側の待ちを解除するhost functionに使われる。したがって、この設定は転送データやモデル計算を変更せず、転送streamの作成方法を変える（`src/core/verify.cpp:2535-2564`; `include/strata/core/verify.hpp:482-488`）。

## 値と判定

実装は `std::atoi` で整数変換し、結果が0でないかを判定する。文字列全体の妥当性確認はない。

| 値 | 判定 |
|---|---|
| 未設定 | 無効。通常streamを作る |
| 空文字、整数に変換できない文字列、`0`、`-0` | `atoi` の結果が0となり無効 |
| `1`、`2`、`-1` など、変換結果が0以外 | 有効 |
| 数字の後ろに文字が続く値（例: `1abc`） | `atoi` が読む先頭の整数部分が非0なら有効（例では有効） |

先頭の空白と符号は `atoi` の整数変換に従う。たとえば ` 1` は有効、`0abc` は無効になる。値の判定はVerifierの初期化中に行い、関数内 `static const bool` に保存するため、その判定後に環境変数を変更しても再評価されない（`src/core/verify.cpp:752-763`）。

## 有効になる条件

環境変数を読むコードは `STRATA_USE_HIP` が定義され、かつ `STRATA_HIP_GFX906` が定義されていないビルドに限られる。通常のCUDA、Metal、およびgfx906互換HIPビルドではこの分岐がコンパイルされず、設定しても本変数によるstream優先度の変更はない（`src/core/verify.cpp:753-764`; gfx906互換ビルド定義: `CMakeLists.txt:128-144`）。

通常HIPビルドでも、非0値の設定だけで高優先度streamが確定するわけではない。優先度範囲の取得または高優先度stream作成が失敗した場合、Strataは通常のnon-blocking stream作成に進む。通常stream作成も失敗した場合は `verify: copy stream create failed` をエラー文字列にして初期化を失敗させる（`src/core/verify.cpp:758-767`）。

## 実行時の詳細

Verifier初期化時に `STRATA_COPY_HIP_PRIO` を読み、非0なら `hipDeviceGetStreamPriorityRange(&lo, &hi)` を呼ぶ。成功時は返された `hi` で `hipStreamCreateWithPriority(&copy_, hipStreamNonBlocking, hi)` を試す。どちらかの呼び出しに失敗すると `copy_made` はfalseのままなので、続いて `cudaStreamCreateWithFlags(&copy_, cudaStreamNonBlocking)` を実行する。HIP互換層ではこのCUDA互換APIがHIP APIへ写像される（`include/strata/platform/hip_compat/strata_hip.h:129-130`）。優先度付きstream作成のエラー状態はその場で `cudaGetLastError()` により消費され、fallback自体の失敗時のみ上記の初期化エラーとなる。

DMA fetchでは、`copy_` にexpert blobを非同期コピーし、その後同じstreamにhost functionを登録して、転送完了を示すflagを上げる。Verifierはwindow完了時にcopy streamも同期し、次windowで前windowのhost functionがflagを上げないようにする（`src/core/verify.cpp:2428-2433,2535-2564`）。

`src/core/verify.cpp` の完全一致検索では環境変数の読み取り箇所は上記1箇所だけだった。`docs/DETAILS.md` と `docs/AMD_HIP.md` にこの環境変数の個別説明や測定値は見当たらない。ソースコメントは、HIPで優先度ごとにhardware queueが割り当てられる前提と、window graph待ち中にコピーstreamの処理が同じqueueで詰まる問題を理由として記すが、その効果や性能向上を裏付ける測定条件はリポジトリ資料に示されていない（`src/core/verify.cpp:754-756`）。

## 根拠

- 変数の読み取り、値判定、priority付きstream作成、通常streamへのfallback: `src/core/verify.cpp:752-767`
- DMA fetchとコピー完了flagの登録: `src/core/verify.cpp:2535-2564`
- window終了時のcopy stream同期: `src/core/verify.cpp:2428-2433`
- copy streamの役割とfetch callbackの宣言: `include/strata/core/verify.hpp:482-488`
- HIP gfx906互換ビルドのmacro定義: `CMakeLists.txt:128-144`
