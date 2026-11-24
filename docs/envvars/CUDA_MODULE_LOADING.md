# `CUDA_MODULE_LOADING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Strata はこの変数を CUDA のモジュール読み込み設定として値解析せず、起動時に設定有無を確認し、未設定ならプロセス環境へ既定文字列を設定する。共通 CUDA/HIP 系エンジンと CUDA を使う Inkling / Hy4 / Qwen3.6 エンジンでは、volta-forever 検出時に `LAZY`、それ以外では `EAGER` を選ぶ。SYCL エンジンは volta-forever 分岐を持たず、未設定なら `EAGER` を設定する（`engine/include/strata/core/volta_forever.hpp:74-93`、`engine/src/program/generate.cpp:3770-3776`、`engine/sycl/src/program/generate.cpp:1867-1875`）。

このコードが行うのは環境変数の有無確認と設定だけである。明示値の意味や、その後 CUDA runtime / driver がそれをどう扱うかは Strata の挙動としては説明しない。

## 値と判定

| 経路 | 未設定 | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 共通 CUDA/HIP 系、CUDA Inkling / Hy4 / Qwen3.6 | volta-forever 非検出なら `EAGER`、検出なら `LAZY` を設定 | Strata による値判定なし。既存値をそのまま保持 | Strata による値判定なし。既存値をそのまま保持 |
| SYCL | `EAGER` を設定 | Strata による値判定なし。既存値をそのまま保持 | Strata による値判定なし。既存値をそのまま保持 |

両経路とも `std::getenv(...) == nullptr` のみを未設定とみなす。空文字 `""` は設定済みなので上書きされず、`0`、`1`、`true`、`false`、小文字値、前後に空白がある値、その他の文字列も同様にそのまま残る。文字列比較、数値変換、範囲検査、無効値時の fallback は Strata 側にない（`engine/include/strata/core/volta_forever.hpp:82-93`、`engine/sycl/src/program/generate.cpp:1870-1875`）。

## 有効になる条件

- 共通エンジンでは `apply_default_cuda_module_loading()` が実行される経路で有効。標準エンジンの起動処理から呼ばれ、値設定の直後に `--gpu` の環境設定や後続の引数処理へ進む（`engine/src/program/generate.cpp:3770-3802`）。
- CUDA Inkling と CUDA Hy4 はそれぞれ `INKLING_ENABLE_CUDA` / `INKLING_ENABLE_EP_CUDA`、`HY4_CUDA` のビルド条件内で helper を呼ぶ。Inkling の通常エントリは CUDA build のとき、別の CUDA エントリも起動直後に呼ぶ。Hy4 は `HY4_CUDA` 条件内で呼ぶ（`engine/src/inkling2/ink_main.cpp:832-836`、`engine/src/inkling2/cuda/ink_cuda_main.cu:38-41`、`engine/src/hy4flash/run/hy4_main.hip.cpp:350-354`）。Qwen3.6 は独立 engine の引数処理後、モデル必須確認を通った場合に呼ぶ（`engine/src/qwen35/q36_engine.cu:5419-5423`）。
- 共通 helper の volta-forever 判定は、`STRATA_VOLTA_FOREVER` が空でなく先頭文字が `0` 以外なら強制 on、先頭が `0` なら他の検出より優先して off とする。それ以外では `VOLTA_FOREVER` が空でなく文字列全体が `0` でない場合、version symbol が空でない場合、または `LD_PRELOAD` に `libvolta_forever` が含まれる場合に on となる（`engine/include/strata/core/volta_forever.hpp:40-65`）。この判定が on で、かつ `CUDA_MODULE_LOADING` が未設定のときに限って helper は `LAZY` を選ぶ。
- SYCL の実装は別の entry point にあり volta-forever 判定を行わず、他の起動条件にかかわらず未設定なら `EAGER` を設定する（`engine/sycl/src/program/generate.cpp:1822-1828,1867-1875`）。
- 明示された環境値を上書きする CLI 引数や設定ファイルはこの読み取り箇所にない。明示値（空文字を含む）がある場合、volta-forever 検出も既定値の選択に使われず、共通 helper は設定を行わず `false` を返す（`engine/include/strata/core/volta_forever.hpp:82-93`）。

## 実行時の詳細

共通 helper は呼び出しごとに volta-forever 判定を行い、その後 `CUDA_MODULE_LOADING` を一度取得する。未設定なら Windows では `_putenv_s`、それ以外では `setenv(..., 0)` で値を設定し、設定済みなら何もしない。SYCL は同じ設定有無判定を entry point で一度行い、同じ OS 分岐で `EAGER` を設定する。static cache やリクエストごとの再読込はない。起動時に一度設定された後の変更を Strata が監視・反映するコードも、この変数については見つからない（`engine/include/strata/core/volta_forever.hpp:61-93`、`engine/sycl/src/program/generate.cpp:1870-1875`）。

共通 helper は `setenv` / `_putenv_s` の戻り値を確認しない。したがって設定失敗を検出して fallback する処理や、それ専用のエラー出力はない。volta-forever を検出し、かつ変数が未設定だった場合は helper が `true` を返し、呼び出し元が設定成功を確認せず「setting ... LAZY」のログを出す。非 volta-forever 時の `EAGER` 設定、明示値がある場合、および SYCL の設定時には、この設定処理専用のログはない（`engine/include/strata/core/volta_forever.hpp:81-93`、`engine/src/program/generate.cpp:3773-3776`、`engine/sycl/src/program/generate.cpp:1870-1875`）。

## ログと測定値

volta-forever 検出かつ未設定時、呼び出し元により次の stderr ログが出る。

- 標準エンジン: `strata: volta-forever detected (%s): setting CUDA_MODULE_LOADING=LAZY`（`%s` は version string。取得できない場合は `env`）（`engine/src/program/generate.cpp:3773-3776`）
- Qwen3.6: `strata-q36: volta-forever detected: setting CUDA_MODULE_LOADING=LAZY`（`engine/src/qwen35/q36_engine.cu:5421-5423`）
- Inkling: `[inkling] volta-forever detected: setting CUDA_MODULE_LOADING=LAZY` または `[inkling-cuda] volta-forever detected: setting CUDA_MODULE_LOADING=LAZY`（`engine/src/inkling2/ink_main.cpp:833-835`、`engine/src/inkling2/cuda/ink_cuda_main.cu:39-41`）
- Hy4 CUDA: `[gpu] volta-forever detected: setting CUDA_MODULE_LOADING=LAZY`（`engine/src/hy4flash/run/hy4_main.hip.cpp:351-353`）

この変数の設定による Strata 自身の終了・エラー経路や、生成結果への影響は上記コードからは確認できない。測定値は記載しない。

## 根拠

- `engine/include/strata/core/volta_forever.hpp:40-65,74-93` — volta-forever の判定、既定値選択、環境値の有無判定と設定。
- `engine/src/program/generate.cpp:3770-3776` — 標準エンジンの helper 呼び出しとログ。
- `engine/src/qwen35/q36_engine.cu:5419-5423` — Qwen3.6 の呼び出し位置とログ。
- `engine/src/inkling2/ink_main.cpp:832-836`、`engine/src/inkling2/cuda/ink_cuda_main.cu:38-41` — Inkling の呼び出し条件とログ。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:350-354` — Hy4 CUDA の呼び出し条件とログ。
- `engine/sycl/src/program/generate.cpp:1867-1875` — SYCL の `EAGER` 既定値設定。
