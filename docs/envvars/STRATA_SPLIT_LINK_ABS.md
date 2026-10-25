# `STRATA_SPLIT_LINK_ABS`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--layer-split auto` の配置コストに使う、GPU stage ごとの expert miss cost のリンク帯域補正を切り替えます。未設定時の現行方式は最速リンクとの相対比較です。この変数を有効にすると、各 stage の実測 H2D 帯域を旧来の 20 GB/s 基準で個別に補正する方式に戻ります。配置計算の補正であり、実際のリンク速度や転送自体は変更しません。

## 値と判定

実装は文字列を数値 parse せず、環境変数が設定されているかと先頭文字だけを見ます。

| 環境変数 | `link_abs` |
|---|---|
| unset | `false`（現行の相対方式） |
| 空文字 | `false` |
| 先頭文字が `1` の文字列（`1`, `10`, `1abc` など） | `true` |
| その他の設定値（`0`, `true`, `false`, 空白で始まる値など） | `false` |

大文字小文字や後続文字、数値としての妥当性は検査されません。判定結果は `static const bool` に保存され、プロセス内でこのコード経路に初めて到達した後に環境を変更しても再評価されません。

## 有効になる条件

- `multi_gpu && split_auto`、すなわち複数 GPU の `--layer-split auto` の配置検索に入る必要があります。明示的な layer split や単一 GPU の実行では、この判定箇所を通りません。
- リンク帯域を実測するのは `native_pack` の場合です。それ以外では各帯域値が `-1.0` となり、どちらの方式でも補正係数は `1.0` になります。
- `ns` は stage 数（GPU 数）です。2 または3 stage の配置検索では補正後の係数が配置予測に使われます。4 stage の全配置列挙は別の目的関数を使い、miss cost を単一係数で計算するため、この環境変数による係数は配置順位に反映されません。4 stage でもリンク係数自体は計算・ログ出力されます。5 stage 以上は比例配分へ進み、配置検索の目的関数による選択をしません。

## 実行時の詳細

各 GPU stage について `probe_pcie_h2d_gbps()` で取得した H2D 帯域 `bw` から `link_scale` を作ります。デフォルトの `link_miss_scale()` は、最速 stage の帯域を基準に比率を取り、4倍以上遅い stage にのみ最大64倍まで係数を付けます。リンクが同程度なら係数は `1.0` です。

`STRATA_SPLIT_LINK_ABS` の先頭が `1` のときは、各 stage の係数を `bw > 0` なら `clamp(20.0 / bw, 1.0, 64.0)` に置き換えます。たとえば帯域が20 GB/sなら `1.0`、10 GB/sなら `2.0`、1 GB/sなら上限の `64.0` です。`bw <= 0`（未測定・無効な測定値）の場合は `1.0` です。この方式では各リンクを個別に20 GB/s基準と比較するため、対称なリンクでも全リンクが20 GB/s未満なら各 stage の miss cost が増えます。

2・3 stage の予測では、stage ごとに「全 routed mass に占める、その stage の cache に入らなかった routed mass」に `STRATA_SPLIT_MISS_MS` の値と `link_scale` を掛け、各 stage の layer 時間を加算します。この予測コストで layer 境界候補を比較し、自動配置を選びます。`STRATA_SPLIT_MISS_MS` は別変数で、既定値は190.0です。4 stage の列挙では miss cost が `miss_ms * (1 - held_mass / total_mass)` で計算され、stage 別 `link_scale` を使いません。

各 stage の帯域と最終係数は stderr の `strata generate: layer split auto: CUDA%d link %.1f GB/s -> miss cost x%.2f` に表示されます。自動選択した境界と予測時間は `layer split auto: K=...` の行に表示されます。後者は予測値で、実測性能の保証ではありません。

## 根拠

- `src/program/generate.cpp:3814-3815`: 複数 GPU かつ auto split の場合に配置検索へ入る条件。
- `src/program/generate.cpp:3837-3849`: native pack の場合だけ帯域を測り、既定係数を作る。
- `src/program/generate.cpp:3846-3854`: 先頭文字 `1` の判定、絶対帯域式への置換、stage 別ログ。
- `include/strata/program/split_rules.hpp:77-97`: 現行の相対係数（最速との比率、4倍の閾値、64倍上限）。
- `src/program/generate.cpp:3937-3947`: 2・3 stage 等で使う予測コストに stage 別係数を適用。
- `src/program/generate.cpp:4131-4185`: 4 stage の専用列挙は link scale を使わず、miss cost を評価。
- `src/program/generate.cpp:4214-4218`: 5 stage 以上は比例配分。
- `src/program/generate.cpp:4287-4292`: 選択境界と予測コストのログ。

`include/strata/program/split_rules.hpp:77-82` は、旧方式が各 stage の miss 項を `20 GB/s / 実測帯域`（1〜64に制限）で補正していたことと、現行方式を最速リンクとの相対比較にした設計理由を説明しています。`docs/DETAILS.md` にはこの環境変数固有の説明や測定値は見つかりませんでした。
