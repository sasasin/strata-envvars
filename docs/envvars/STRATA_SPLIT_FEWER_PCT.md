# `STRATA_SPLIT_FEWER_PCT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`--layer-split auto` が選んだ全 GPU の配置と、先頭側のカードを順に外した配置について、予測 decode window 時間を比較し、カードを減らした方が設定値以上速いと予測された場合に stderr へ提案を出す閾値（パーセント）。既定値は `20.0`。分割配置や使用カードを変更する設定ではなく、提案だけを表示する。予測対象は decode で、prompt の読み込み時間は対象外（`engine/include/strata/program/split_rules.hpp:202-225, 235-251, 254-276`、`engine/src/program/generate.cpp:7549-7554, 7573-7589`）。

## 値と判定

`generate.cpp` が環境から値を一度 `std::getenv` で取得し、`fewer_cards_pct_resolve` に渡す。未設定または空文字列なら既定値 `20.0`。それ以外は `std::strtod` で先頭から数値を変換し、変換が一文字も進まない場合、または結果が `0.0` 未満なら既定値に戻す。変換後の文字列末尾は検査しないため、数値の後ろに文字があっても数値部分を採用する。大文字小文字の比較はない。空白や指数表記などの受理範囲は `strtod` に委ねられており、Strata 独自の形式検査や clamp はない（`engine/include/strata/program/split_rules.hpp:215-225`）。

| ビルド / 実行経路 | unset | 設定時に有効になる値 | 無効値・結果 |
|---|---|---|---|
| CUDA/HIP の `generate` による `--layer-split auto` | `20.0`（空文字も同じ） | 変換可能で `>= 0` の数値。例: `20`, `35`, `0`, `12.5`, `20junk`（それぞれ数値部分を採用） | 数値に変換できない値（例: `true`, `x`）と負数（例: `-5`）は `20.0` に戻る。`nan` は比較 `>= 0` を満たさず既定値。`0` は提案判定を停止。`100` より大きい値も clamp されず、その閾値を満たす正の予測時間はないため提案されない。 |

`strtod` の戻り値だけを判定し、末尾まで消費したか、有限値かは確認しない（`engine/include/strata/program/split_rules.hpp:220-225`）。したがって `0anything` は `0` として扱われ提案が止まり、`infinity` のように変換される正の無限大も受理されますが、有限の予測時間は閾値を満たさず提案は出ません。負の値は `-0` を除き既定値に戻ります。`-0` は `>= 0` を満たして値として返りますが、後段の `pct > 0.0` を満たさないため提案は止まります（`engine/src/program/generate.cpp:7552-7554`）。

## 有効になる条件

- エンジンの `generate` で `--serve` が有効であり、`--layer-split auto` を選んでいること。`--layer-split` の解析でサーバーモードが要求され、auto の split 選択を経た後にこの判定へ進む（`engine/src/program/generate.cpp:4803-4805, 4848-4853, 7549-7554`）。明示的な `--layer-split K[,K2..]` ではこの auto 検索内の提案処理は実行されない。
- 2 枚以上のカードで auto split すること。auto で split 対象が空なら「one GPU visible, so no split」として auto が解除される（`engine/src/program/generate.cpp:4836-4839`）。
- 閾値が正（`fewer_pct > 0.0`）で、全カードの配置の予測時間 `best_ms` が正であること（`engine/src/program/generate.cpp:7552-7554`）。
- 先頭側のカードを少なくとも 1 枚外した候補の予測時間が正で、全カード時の時間に対して閾値以上短いこと。比較上は `ms <= ms_all * (1 - pct / 100) + ms_all * 1e-9`。条件を満たす候補が複数なら最も予測時間が小さい候補を選ぶ。同時間なら先に見つかった、より多くのカードを残す候補が保たれる（`engine/include/strata/program/split_rules.hpp:235-251`）。
- 予測中に carve が失敗していないこと。失敗時は `carve_fine` が false になり、`leave` は `0` とされて提案行を出さない。診断用予測で得た `err` と `carve_ok` は復元されるので、この提案処理自体がその carve 失敗で start を中止しない（`engine/src/program/generate.cpp:7556-7573`）。

CUDA/HIP 以外の backend でこの `generate.cpp` 経路が使われるかを示す実装根拠は、この変数の読み取り箇所にはない。Strata の `docs/SETTINGS.md:467` は NVIDIA と AMD を掲載している。

## 実行時の詳細

環境値は auto split の候補探索・全カード配置決定後に `std::getenv` で読み取られる。関数内 static cache はなく、この処理が走るたびにその時点の値を使う。同一の auto split 処理が終わった後の環境変更で既に出した提案は変わらず、次にこの処理を通るときには新しい値が読まれる（`engine/src/program/generate.cpp:7549-7554`）。

正の閾値で条件を通ると、先頭から `drop=1` から `ns-1` まで段階的に外した候補を `predict` し、全カード時の予測と比較する。外すのは先頭 stage 群で、最後のカードは残る。選ばれた候補についてカード名・engine 上の番号と再実行方法を案内するだけであり、実際の split、GPU 可視性、カード設定は変更しない（`engine/include/strata/program/split_rules.hpp:227-251, 254-276`、`engine/src/program/generate.cpp:7559-7589`）。

CLI の自動 split 選択が必要条件で、他の環境変数や設定ファイルによるこの閾値の上書き処理は読み取り箇所にない。`STRATA_SPILL_OFF` は前段の空きメモリによるカード除外処理の条件だが、この提案ブロック自身の条件ではない（`engine/src/program/generate.cpp:4815-4835, 7552-7554`）。子プロセスへの環境変数の転送もこの処理にはない。

## ログと測定値

選んだ候補があると stderr に `strata generate: layer split auto: FEWER CARDS - without ...` で始まる行を出す。行には外すカード、同じモデルの予測 decode window 時間、全カード時との差、残すカード、再実行の指定が含まれる。1 枚だけ残す候補には `--gpu N` と `--layer-split` を付けない方法、複数枚を残す候補には `CUDA_VISIBLE_DEVICES=...` と `--layer-split auto` の方法を案内し、Terminal では gpu roles の設定も案内する。行末には `STRATA_SPLIT_FEWER_PCT=0 turns this line off.` と表示する（`engine/include/strata/program/split_rules.hpp:258-276`）。

この変数の未設定・無効値への fallback、0、閾値を満たす候補がない場合に、この変数由来の警告やエラーは出ず、終了もしない。carve 失敗時も提案だけを省略する。auto split の他の診断ログや失敗経路はこの変数の判定とは別に存在する（`engine/include/strata/program/split_rules.hpp:220-225, 238-251`、`engine/src/program/generate.cpp:7556-7573`）。

既定の 20% はソース定数 `kFewerCardsPct` と `docs/MULTI_GPU.md:250-255` の記述で一致する。同資料は予測が decode のみであること、配置を自動変更しないことも記載している。この文書では資料中の実測値を本変数の効果として一般化しない。

## 根拠

- `engine/src/program/generate.cpp:4803-4805, 4836-4839` — layer split の serve / auto 条件と、1 GPU 時の auto 解除。
- `engine/include/strata/program/split_rules.hpp:202-225` — 既定値、`strtod` による値の判定、0 の意味。
- `engine/include/strata/program/split_rules.hpp:227-251` — 先頭 stage を除いた候補生成と閾値判定。
- `engine/include/strata/program/split_rules.hpp:254-276` — stderr 提案文と実際には配置を変更しない旨。
- `engine/src/program/generate.cpp:7549-7589` — 読み取り時点、予測・carve failure の扱い、提案出力。
- `docs/SETTINGS.md:467`, `docs/MULTI_GPU.md:250-255` — backend の記載と既定 20%・表示内容の説明（動作の根拠は上記ソース）。
