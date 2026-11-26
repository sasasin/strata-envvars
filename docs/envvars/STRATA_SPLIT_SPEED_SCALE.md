# `STRATA_SPLIT_SPEED_SCALE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の `--layer-split auto` が各 GPU のレイヤー処理時間を見積もる際、GPU ごとの推定速度に倍率を掛ける開発・診断用の調整値である。たとえば `1,0.55` は CUDA0 の速度をそのままにし、次の stage の推定速度を 0.55 倍にする。コメント上も「test seam」とされている。実際の GPU クロックやカーネル実行速度は変更せず、自動分割の候補評価と選択に使う予測値だけを変える（`engine/src/program/generate.cpp:6976-6985,7101-7107`）。

## 値と判定

自動分割の速度表を作る stage ごとに `std::getenv` で読み、空でない場合は stage の 0 始まりの番号 `i` だけカンマをたどった位置から `std::atof` で倍率を読む。文字列全体の検証はせず、`atof` が解釈できる数値の接頭部分を使う。変換結果 `f` が `f > 0.0` の場合だけ適用し、適用後の速度は `max(1.0, 元の速度 * f)` で下限 1 に制限される。各 GPU の元の速度は SM 数 × クロック（GHz）で、クロック取得失敗または非正値の場合は 1.8 GHz を使う（`engine/src/program/generate.cpp:6968-6975,6979-6985`）。

| 条件 | 未設定 | 有効になる値の例 | 無効・適用されない値の例 |
|---|---|---|---|
| stage `i` | 倍率 1 相当（速度を変更しない） | `1`（CUDA0）、`1,0.55`（CUDA0 と次 stage）、`1,0.55,2`（3 stage 目まで） | 空文字、当該 stage の項目がない文字列、`0`、`-1`、`text`、`1,` の空項目 |

`atof` のため、先頭空白や符号を含む数値接頭部分は変換され、後続の非数値文字は検査されない（例: `1junk` は 1、`1,0.55tail` の第 2 項目は 0.55）。正数であれば 1 未満も 1 超も受理され、上限クランプはない。`0`、負数、数値に変換できない項目は倍率を適用しない。カンマで分割した各項目は全体として検証されないため、余分な項目は stage がなければ参照されない（同 `generate.cpp:6979-6984`）。

## 有効になる条件

- Strata の CUDA `generate` 経路で `--serve` と `--layer-split auto` が成立し、実際に複数 GPU の自動分割探索へ進むこと。コードは `o.serve` を要求し、探索箇所は `multi_gpu && split_auto` で囲まれる（`engine/src/program/generate.cpp:4803-4807,4856,6959`）。
- `--layer-split auto` であっても、利用可能な後段 GPU がなく単一 GPU になる場合は自動分割が解除され、倍率を使う探索は行われない（`engine/src/program/generate.cpp:4836-4839`）。`--split-skip-if-fits` により CUDA0 単独へ切り替わる場合も同様（同 `generate.cpp:6446-6481`）。
- 明示的な `--layer-split K[,K2..]` は自動配置探索ではないため、この倍率の対象外。自動分割自体が `--serve` なしでは有効にならない（同 `generate.cpp:4803-4807,4848-4853`）。
- この変数と CLI 引数・別環境変数の優先順位や上書き処理はない。ほかの条件で自動分割経路が無効になる場合は値も参照されない。

## 実行時の詳細

自動分割探索の前に、CUDA0 と各後段 stage の SM 数・クロックから基準速度を作り、環境変数の該当項目が正数なら倍率を適用する。その速度から `layer_ms = 0.33 * (84 * 2.617) / speed` を計算し、stage のレイヤー数に応じた予測時間を候補のコストへ加える。2～4 GPU の探索では候補の予測時間や同点時の比較に使われ、5 GPU 以上などの比例配分経路では速度比からレイヤー境界を計算する。したがって倍率は自動で選ばれる境界に影響し得るが、実行時に各 stage が処理する実レイヤー数を直接指定するものではない（`engine/src/program/generate.cpp:6985,7101-7107,7121-7127,7273-7284,7382-7388`）。

値は関数内 `static` には保存されず、stage ごとの速度表を組み立てるときに読み取られる。以降の候補再探索は作成済みの `layer_ms` を再利用する。読み取り後に環境を変更しても、作成済みの速度表や選択済み境界には反映されない（`engine/src/program/generate.cpp:6968-6979,7388`）。

## ログと測定値

有効・無効値に関する専用の警告やエラーはなく、無効項目は倍率を適用せず進む。各 stage について `strata generate: layer split auto: CUDA%d %d SMs at %.2f GHz -> %.2f ms per layer, %.2f GiB free before its session carve` を stderr に出す。この行の `ms per layer` は倍率適用後の推定値だが、表示される SM 数と GHz は取得したハードウェア値である。選択後には `strata generate: layer split auto: K=... - predicted ... ms per decode window; ...` の行が出る（`engine/src/program/generate.cpp:6985-6988,7510-7515`）。

## 根拠

- 候補一覧への掲載: `docs/envvars/000_envvers.md:2129`。
- Strata 所有ソースでの実読み取りと倍率適用: `engine/src/program/generate.cpp:6976-6985`。
- 自動分割の serve 条件と単一 GPU 時の解除: `engine/src/program/generate.cpp:4803-4807,4836-4839`。
- 予測コスト・比例配分への使用: `engine/src/program/generate.cpp:7101-7107,7273-7284,7382-7388`。
- stage と選択結果のログ: `engine/src/program/generate.cpp:6985-6988,7510-7515`。
