# `DS4_FEEDLOG`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

`strata-dsv41` の通常の `--ids` prompt 実行で、入力 token を feed した各 window の所要時間と token/s を stderr に記録します。feed の計算方法や window の大きさを変える設定ではなく、計測ログを追加する診断用フックです。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未設定 | feed ごとのログを出さない |
| 任意の値を設定 | feed ごとのログを出す |

`std::getenv("DS4_FEEDLOG") != nullptr` だけを判定し、値の内容は parse しません。そのため `DS4_FEEDLOG=0`、空文字、その他の文字列はいずれも設定済みとしてログを有効にします。数値変換、大小文字判定、範囲制限はありません。

## 有効になる条件

- CMake の `STRATA_BUILD_DSV41` が有効で、かつ `STRATA_HIP_GFX906` が有効でない構成で `strata-dsv41` がビルドされている必要があります。`STRATA_BUILD_DSV41` は既定で `OFF` です。
- 実行時は `--serve` ではなく、通常の ID 入力処理が実行されて feed loop に入る必要があります。`--score`、`--profile-run`、`--spec-eval` などはそれぞれの処理へ先に分岐するため、このログ箇所を通りません。
- `--ids` の入力が空なら feed loop は実行されず、ログも出ません。

## 実行時の詳細

各 window について、`m.feed(...)` が成功した後に環境変数を確認します。設定済みなら、開始 token offset、feed token 数、経過ミリ秒、token/s を次の形式で stderr に出力します。

```text
feed at %zu: %d tokens in %.0f ms (%.1f tok/s)
```

時間は `std::chrono::steady_clock` から得た値の差です。環境変数の確認は feed loop の各反復で行われ、static cache や起動時の一度だけの読み取りはありません。ログを出さない場合も、feed の成否や処理はこの条件分岐より前に決まっています。別途、環境変数の有無にかかわらず、feed loop 全体の prompt 時間と tok/s が最後に stderr へ出ます。

## 根拠

- `src/dsv41/ds4_main.cpp:50-52`: `now_ms()` は `steady_clock` をミリ秒へ変換。
- `src/dsv41/ds4_main.cpp:1279-1306`: `--serve`、profile、spec、score の分岐と通常 ID 処理への到達条件。
- `src/dsv41/ds4_main.cpp:1363-1381`: feed window の反復、成功後の環境変数判定とログ、全 prompt の集計ログ。
- `CMakeLists.txt:797-811`: `STRATA_BUILD_DSV41` は既定 `OFF`。`STRATA_HIP_GFX906` でない場合に `strata-dsv41` のソースへ `ds4_main.cpp` を含める。
