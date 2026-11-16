# `QUANT_CTAB`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`QUANT_CTAB` は Metal の parity test `expert_parity` と `moe_mm_parity` が、gate/up カーネルの function constant 23 を有効にするか選ぶテスト用スイッチである。設定されていると値の内容にかかわらず `true` を渡し、未設定なら `false` を渡す。Strata の `strata` 実行エンジンが読む変数ではない。Metal エンジン側で同じ function constant 23 を切り替える変数は別名の `STRATA_METAL_CTAB` であり、`window.cpp` の `metal_ctab()` が読む（`metal/tests/expert_parity.cpp:433-445`、`metal/tests/moe_mm_parity.cpp:118-126`、`metal/src/engine/window.cpp:146-154,1294-1302`）。

function constant 23 が有効なとき、`quant.metal` の量子化グリッドと符号表の参照 helper は threadgroup table ではなく constant 配列を選ぶ。同ソースは値が同じで、threadgroup への表コピーと先頭 barrier を省く経路としている（`metal/kernels/quant.metal:91-102`）。これは parity harness のカーネル設定の説明であり、`QUANT_CTAB` を Strata エンジンの起動設定として案内するものではない。

## 値と判定

両テストとも `std::getenv("QUANT_CTAB") != nullptr` を `.b(23, ...)` に渡す。文字列を parse せず、設定の有無だけを見るため、空文字や `0` も有効になる（`metal/tests/expert_parity.cpp:438`、`metal/tests/moe_mm_parity.cpp:122`）。

| 実行経路 | 未設定 | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `expert_parity` の gate/up pipeline 作成 | function constant 23 は `false` | 空文字、`1`、`0`、`false`、その他の任意の文字列（すべて `true`） | なし。`getenv` が非 null なら文字列内容を検査しない |
| `moe_mm_parity` の v3 gate/up pipeline 作成 | function constant 23 は `false` | 空文字、`1`、`0`、`false`、その他の任意の文字列（すべて `true`） | なし。`getenv` が非 null なら文字列内容を検査しない |

大文字小文字、空白、数値としての妥当性は検査しない。CLI 引数による上書きはこの値の設定箇所にはない。`moe_mm_parity` では v3 以外の gate/up pipeline 分岐は function constant 23 を渡さないため、この変数はその経路に作用しない（`metal/tests/moe_mm_parity.cpp:118-126`）。

## 有効になる条件

- Metal テストプログラムを実行すること。`metal/CMakeLists.txt` は macOS 以外では構成を停止し、`metal/tests/*.cpp`（`runtime_hello.cpp` を除く）から個別実行ファイルを作る（`metal/CMakeLists.txt:17-19,42-48`）。
- `expert_parity` では gate/up pipeline を作る経路に入ること。値は `make` lambda が pipeline を作る時に判定される（`metal/tests/expert_parity.cpp:433-445`）。
- `moe_mm_parity` では v3 gate/up pipeline の分岐に入ること。v2/v4/v5/v6 など他の分岐ではこの設定を渡さない（`metal/tests/moe_mm_parity.cpp:112-126`）。
- 通常の Strata Metal エンジンの実行には適用されない。エンジンは `STRATA_METAL_CTAB` を別途読み、未設定なら有効、値全体が `"0"` なら無効としている（`metal/src/engine/window.cpp:148-154`）。

## 実行時の詳細

`expert_parity` は `make` lambda 内で pipeline ごとに `getenv` を評価する。`moe_mm_parity` は v3 pipeline を作る式の中で評価し、その結果を Metal function constant 23 に設定する。`QUANT_CTAB` の値をキャッシュするコードや、環境変数を書き換えるコードはこれらの参照箇所にはない（`metal/tests/expert_parity.cpp:433-439`、`metal/tests/moe_mm_parity.cpp:118-126`）。

テストが使う `quant.metal` では function constant 23 が真のとき、`ksg` と `g_iq*` helper が constant 配列を参照し、偽または未定義のときは threadgroup table を参照する（`metal/kernels/quant.metal:91-102`）。このスイッチ自体に専用のログ出力はない。テストの通常の parity 結果は `PASS` / `FAIL` として表示され、判定結果に応じた終了コードを返す（`metal/tests/expert_parity.cpp:586-590`、`metal/tests/moe_mm_parity.cpp:225-230`）。

## 根拠

- 候補一覧への掲載: `docs/envvars/000_envvers.md:786`。
- テストでの環境読み取りと function constant の設定: `metal/tests/expert_parity.cpp:433-445`、`metal/tests/moe_mm_parity.cpp:118-126`。
- Metal テスト実行ファイルの構成条件: `metal/CMakeLists.txt:17-19,42-48`。
- function constant 23 に応じた量子化テーブル参照: `metal/kernels/quant.metal:91-102`。
- 実行エンジンで読む別変数 `STRATA_METAL_CTAB`: `metal/src/engine/window.cpp:146-154,1294-1302`。
