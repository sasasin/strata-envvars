# `STRATA_SPLIT_LINK_ABS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

複数 GPU の `--layer-split auto` が配置を探索するとき、GPU ごとのリンク帯域に応じて expert cache miss の推定コストを補正する係数を、帯域の絶対値から計算します。値が有効だと各 stage の係数は `20 GB/s ÷ その stage の測定帯域` を 1〜64 に clamp した値になり、測定帯域が正でない場合は 1 です。これは自動配置の予測コストと選ばれる layer 境界に作用します。実行時の通信方式や実測性能を直接変更する処理ではありません（`engine/src/program/generate.cpp:6990-7013,7099-7108`）。

対象コードは CUDA の GPU 情報・デバイス切替 API を使う `generate.cpp` の自動分割処理です。設定は layer split の自動探索にだけ参照され、手動境界指定には使われません（`engine/src/program/generate.cpp:4783-4809,6959-6961`）。候補名の他のソース参照はなく、`terminal/data/settings-register.json:46091` にも名前がありますが、そこは設定レジストリの記載であり、環境から値を読む実装ではありません。

## 値と判定

`std::getenv` の結果について、先頭 1 文字が `'1'` かだけを判定し、その結果を関数内 `static const bool` に保存します。文字列全体の parse、数値検証、trim、大文字小文字変換はありません（`engine/src/program/generate.cpp:7003`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 自動 layer split 探索の最初の評価 | `false`（相対帯域差に基づく既定係数） | `1`、`10`、`1anything`、`1.0`（先頭が `1`） | 空文字、`0`、`true`、` 1`、`2`（先頭が `1` でない） |

未設定・空文字・無効値は同じく絶対帯域式を選びません。無効値の警告や fallback ログはありません。最初にこの分岐へ到達した時の値がプロセス内に cache されるため、その後の環境変更は反映されません。

## 有効になる条件

- `--layer-split` が `auto` であること。layer split 自体は serve モードでのみ受け付けられます（`engine/src/program/generate.cpp:4775-4780,4803-4805`）。
- 自動分割が無効化されず、CUDA0 に加えて少なくとも 1 枚の GPU が split stage として残り、複数 GPU の配置探索に到達すること。追加 GPU がない場合は `--layer-split auto: one GPU visible, so no split` と出して自動分割を解除します（`engine/src/program/generate.cpp:4836-4840,6959`）。
- `STRATA_SPLIT_UNIFORM` が先頭 `'1'` で有効の場合、この変数より優先されます。係数を全 stage で `1.0` に固定するため、`STRATA_SPLIT_LINK_ABS` は実質無視されます（`engine/src/program/generate.cpp:7004,7008-7011`）。
- 正のリンク帯域が必要です。native pack では各 stage の H2D 帯域を測定し、正値なら絶対式が使われます。native pack 以外ではこの探索コードが帯域を `-1.0` とし、式の fallback により係数は `1.0` になります（`engine/src/program/generate.cpp:6992-6997,7011`）。
- `STRATA_SPLIT_LINK_MIN` は通常の相対帯域係数を決めますが、この変数が有効ならその係数を絶対式で置き換えます（`engine/src/program/generate.cpp:7005-7011`）。`STRATA_SPLIT_MISS_MS` は係数適用後の miss コスト全体を変えます（同 `:7015,7099-7103`）。

## 実行時の詳細

serve の layer split 初期化中、`multi_gpu && split_auto` の配置探索に入ると各 stage の H2D 帯域を得て、通常は最速 stage との比率に基づく係数を作ります。`STRATA_SPLIT_LINK_ABS` が有効で、かつ `STRATA_SPLIT_UNIFORM` が無効なら、各係数を `clamp(20.0 / bw, 1.0, 64.0)`（`bw > 0` の場合）で上書きします。リンク帯域が 20 GB/s 以上なら係数 1、20 GB/s 未満では帯域に反比例して最大 64 です（`engine/src/program/generate.cpp:6990-7013`）。

探索の各配置では、各 stage に割り当てられた routed mass のうち cache に入らない分へ `miss_ms × link_scale[stage]` を掛け、layer 実行時間と足して予測時間を比較します。したがって係数は自動配置の選択に影響し得ますが、最終的な境界が必ず変わるとは限りません（`engine/src/program/generate.cpp:7099-7108,7110-7112,7510-7515`）。この変数に対応する CLI 引数はありません。`--layer-split auto` は処理経路を選びますが、係数値の優先設定は前述の `STRATA_SPLIT_UNIFORM` です。

読み取りは初回の自動探索時で、値は関数内 static に cache されます。同一プロセス内で複数回探索する場合も初回評価値が使われます。リクエストごとの読み直しではありません（`engine/src/program/generate.cpp:7003`）。

## ログと測定値

各 stage について `strata generate: layer split auto: CUDA%d link %.1f GB/s -> miss cost x%.2f` を stderr に出し、探索後に予測時間と選ばれた `K` を出します。係数ログには最終的に適用された値が出るため、`STRATA_SPLIT_UNIFORM` が優先した場合もその結果を確認できます。無効値・帯域測定失敗に対する専用警告はありません（`engine/src/program/generate.cpp:7008-7013,7513-7515`）。

この文書では性能向上を示す測定値は記載しません。ソースコメントの「20 GB/s rule」は旧式の係数を説明する記述であり、この環境変数を設定した場合の一般的な性能保証ではありません（`engine/src/program/generate.cpp:6999-7002`）。

## 根拠

- `engine/src/program/generate.cpp:4783-4809` — layer split の serve 条件、`auto` 判定。
- `engine/src/program/generate.cpp:4836-4840,6959-6961` — GPU がない場合の解除と自動配置探索の条件。
- `engine/src/program/generate.cpp:6990-7015` — 帯域測定、対象変数の読み取りと係数の優先順位。
- `engine/src/program/generate.cpp:7099-7108,7510-7515` — miss コストへの反映と探索結果ログ。
- `engine/include/strata/program/split_rules.hpp:141-171` — 通常時の相対帯域式。
- `terminal/data/settings-register.json:46091` — 名前のレジストリ記載（実行時読み取りではない）。
