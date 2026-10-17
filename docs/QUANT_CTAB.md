# `QUANT_CTAB`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`QUANT_CTAB` は通常の Strata エンジンが読む環境変数ではなく、Metal の2つの parity / benchmark 実行ファイルにあるテスト用スイッチです。設定されているかどうかを Metal 関数定数23へ渡し、routed expert の i-quant lookup table を threadgroup にコピーする経路と、定数配列から直接参照する経路を選びます。

通常エンジンで同じ関数定数を制御する環境変数は `STRATA_METAL_CTAB` です。名前が似ていますが、`QUANT_CTAB` は本番エンジンの設定名ではありません。

## 値と判定

| `QUANT_CTAB` | テスト側の値 |
|---|---|
| 未設定 | 関数定数23に `false` を渡す |
| 任意の値で設定 | 関数定数23に `true` を渡す |

テストコードは値の内容を parse せず、`std::getenv(...) != nullptr` だけを確認します。したがって空文字列や `0` も「設定済み」として `true` になります。

## 有効になる条件

`metal/tests/expert_parity.cpp` の `expert_parity`、または `metal/tests/moe_mm_parity.cpp` の `moe_mm_parity` を実行する場合に限って、この環境変数の読み取りが行われます。通常の engine (`metal/src/engine/window.cpp`) は `QUANT_CTAB` を読まず、`STRATA_METAL_CTAB` を使います。

## 実行時の詳細

parity / benchmark プログラムは routed gate/up kernel の pipeline 作成時に `QUANT_CTAB` の設定有無を関数定数23へ渡します。kernel 側では関数定数が有効なら i-quant grid と IQ2_XS の sign table を定数配列から読み、threadgroup table のロードと対応する barrier を省く経路を使います。未設定なら従来の threadgroup table 経路を使います。対象の値は同一とソースコメントに記されています。

通常エンジン側は `STRATA_METAL_CTAB` を初回評価時に一度読み、その値を `static const bool` に保持します。未設定または文字列が厳密に `"0"` 以外なら有効で、厳密な `"0"` なら無効です。値は routed gate/up pipeline の関数定数23へ渡され、pipeline cache key にも有効・無効が反映されます。このエンジン側の挙動は `QUANT_CTAB` の挙動ではありません。

## 根拠

- `metal/tests/expert_parity.cpp:221-227` — `QUANT_CTAB` の設定有無を pipeline 関数定数23へ渡す。
- `metal/tests/moe_mm_parity.cpp:96-106` — v3 gate/up GEMM の pipeline で同じ設定有無判定を行う。
- `metal/tests/expert_parity.cpp:1-5`, `metal/tests/moe_mm_parity.cpp:1-6` — 対象ファイルが parity / benchmark プログラムであることを示す。
- `metal/kernels/quant.metal:65-76,91-118` — 定数 table 経路と threadgroup table 経路の分岐。
- `metal/src/engine/window.cpp:65-73,864-875,1833-1839` — 通常エンジンが別名 `STRATA_METAL_CTAB` を読み、同じ関数定数を設定する箇所。
