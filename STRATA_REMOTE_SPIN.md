# `STRATA_REMOTE_SPIN`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA ビルドで、remote expert helper GPU の初期化時に Strata が `cudaInitDevice` へ渡すスケジューリング flags を選びます。未設定または先頭文字が `0` ではない値なら `cudaDeviceScheduleSpin | cudaDeviceMapHost` を渡し、先頭文字が `0` ならこの呼び出しを省略してドライバーの既定設定を使います。

ここでの「remote」は `--expert-cache-device1..3` で expert cache を置く補助 GPU を指します。環境変数は cache の容量、expert の割り当て、演算内容を直接変えません。スケジューリング flags の外部ランタイム上の意味はこの調査対象外です。

## 値と判定

`getenv()` で得た文字列の先頭 1 文字だけを確認します。数値変換や文字列全体の比較はありません。

| ビルド | unset | 設定値 | Strata の処理 |
|---|---|---|---|
| CUDA（`STRATA_USE_HIP` 未定義） | スピン設定を要求 | 先頭文字が `0` なら要求しない。それ以外は要求する。空文字も要求する | 要求時は `cudaInitDevice(device, cudaDeviceScheduleSpin \| cudaDeviceMapHost, 0)` を呼ぶ |
| HIP（`STRATA_USE_HIP` 定義） | 読み取りも設定も行わない | 読み取りも設定も行わない | このコード経路では環境変数を使わず、HIP の既定スケジューリング方針を維持する |
| SYCL | 値を読むが使用しない | 値を読むが使用しない | `spin` を破棄し、スケジューリング設定を行わない |

CUDA では `0`、`0anything` など先頭が `0` の全値が無効側です。`1`、`false`、空文字など先頭が `0` でない値は有効側です。大文字小文字、空白、数値としての妥当性は検査しません。

## 有効になる条件

- 通常の CUDA ビルドであること。HIP 実装では `#if !defined(STRATA_USE_HIP)` の範囲外となり、この環境変数による設定はありません。
- `RemoteExperts::preflight()` が実行されること。これは `--expert-cache-device1..3` により補助 GPU の expert cache が要求された初期化経路で呼ばれます。通常の単一 GPU 実行や remote cache を使わない実行では、この設定箇所は通りません。
- SYCL ポートにも同名の読み取りコードがありますが、値は `(void) spin` で破棄されます。SYCL では unset と全ての設定値で動作差はありません。

## 実行時の詳細

CUDA/HIP 共通の `RemoteExperts::preflight()` は、対象 device の可視性を確認した後にスケジューリング箇所へ進みます。CUDA ではこの位置で環境変数をその呼び出し時に読み、先頭文字が `0` でなければ `cudaInitDevice` を呼んでから `cudaGetLastError()` を呼びます。戻り値は判定されず、ここでの `cudaInitDevice` 失敗は Strata のエラー文字列や失敗ログに変換されません。その後 `DeviceScope` で device を選択し、空きメモリを取得します。

この preflight は補助 GPU の context を作る起動処理の一部です。`generate.cpp` では補助 cache の初期化に先立って呼び、追加デバイスについては `STRATA_EARLY_REMOTE_CONTEXTS` の設定に応じて呼び出し時点が分かれます。`STRATA_REMOTE_SPIN` 自体は `static` にキャッシュされず、preflight の各呼び出しで読み直されますが、生成中の継続的なポーリングや再設定はありません。

## 根拠

- `src/core/remote_experts.cpp:68-89`: CUDA/HIP の preflight、先頭文字判定、`cudaInitDevice`、`cudaGetLastError()`、および HIP 側で設定を行わない条件。
- `sycl/src/core/remote_experts.cpp:89-122`: SYCL 側の読み取り値の破棄と、それ以降の preflight 処理。
- `src/program/generate.cpp:2715-2729,4511-4519`: remote helper GPU に対する preflight の起動位置と `STRATA_EARLY_REMOTE_CONTEXTS` による追加 GPU のタイミング分岐。
- `src/program/generate.cpp:2320-2330,5360-5444`: remote cache の条件と補助 GPU cache の初期化。
- `docs/SECOND_GPU.md:102-120`: remote helper cache の利用例と動作概要。`STRATA_REMOTE_SPIN` の値判定や挙動の記述はありません。
