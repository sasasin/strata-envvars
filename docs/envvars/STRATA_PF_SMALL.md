# `STRATA_PF_SMALL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

自動 chunk が小さい単一 GPU の prompt で、small-card 用の prompt path を選ぶ分岐を止めるスイッチです。未設定時は条件を満たす場合にその経路を試し、環境値の先頭が `0` なら試しません。経路を採用すると既定の fused expert path を外し、条件により layer-major walk も有効にしてから、同じ cache に収まる chunk を再計算します。モデル重みや生成 token を直接指定する設定ではありませんが、prompt の計算経路を変えます。layer-major は集約順序が異なる経路として記述されており、出力の同一性は保証されません（`engine/src/program/generate.cpp:12561-12583`、`engine/include/strata/core/sm120_series.hpp:195-204`）。

## 値と判定

`generate.cpp` は `std::getenv("STRATA_PF_SMALL")` の結果を一度調べ、値が存在し、かつ先頭文字が ASCII `'0'` の場合だけ small-card 判定をスキップします。文字列全体の parse、数値妥当性、空白、大文字小文字の検査はありません（`engine/src/program/generate.cpp:12566`）。

| 条件 | unset | 有効になる値（small-card 判定を許す） | 無効になる値（判定を止める） |
|---|---|---|---|
| 共通 | 判定を許す | `""`、`1`、`true`、`false`、` 0` など、先頭が `0` ではない文字列 | `0`、`00`、`0anything` など先頭が `0` の値 |

「有効」はこの分岐を通過する意味であり、それだけで経路が選ばれるわけではありません。空文字は設定済みでも無効扱いではなく、先頭文字がないため判定を許します。`false` や `off` も `0` で始まらないため同様です。無効文字列への警告や fallback はありません（同 `generate.cpp:12566`）。

## 有効になる条件

- 自動 chunk が有効であること。通常は `--prefill auto` または `--prefill auto:N` で選びます。明示 chunk の `--prefill N` は `o.prefill_auto` を false にするため対象外です（`engine/src/program/generate.cpp:4000-4008`）。
- prompt の cache lending が実行され、選ばれた既定 chunk が 1 以上であること。借用は `--no-prefill-borrow` がなく、expert profile がある場合に初期化されます。自動 cache sizing などで lending が解除される経路も対象外です（同 `generate.cpp:6821`、`12452-12453`）。
- 単一 GPU で `stages` が空であること。multi-GPU / layer split は対象外です（同 `generate.cpp:12566`）。
- 既定 chunk が `8192` 未満であること。`small_card_prompt_path` は `default_chunk <= 0` または `>= 8192` なら何もしません（`engine/include/strata/core/sm120_series.hpp:210-218`）。この chunk は cache borrowing scan の結果です（`engine/src/program/generate.cpp:12538-12561`）。
- `STRATA_USE_HIP` build ではないこと、`STRATA_DEFAULTS=026` の既定セットではないこと、native pack であること（同 `generate.cpp:12567-12578`、header `sm120_series.hpp:211-218`）。コメントは CUDA の単一カード経路として説明していますが、この分岐コード自体は HIP 以外の backend を別途判定する guard を持たず、native pack 条件で判定します（`generate.cpp:12562-12578`）。
- `STRATA_PF_FUSED` がユーザー指定されていないこと。非空の値がユーザー指定なら、その値にかかわらず small-card rule 全体が引き下がります。own-only build が自動で設定した値はユーザー指定として扱いません。空文字はユーザー指定とみなしません（`generate.cpp:12572-12578`; `engine/include/strata/prefill/own_only_switches.hpp:67-73`）。
- `STRATA_PREFILL_LAYER_MAJOR` の非空値がある場合、fused-off の変更は適用可能ですが layer-major はこの rule が設定しません。特に `"0"` は既存の walk を無効のままにします（`generate.cpp:12572-12583`）。
- `STRATA_PF_SMALL_FUSED` は `pp.fused_off` の場合に fused-kernel override を選びます。値による詳細は別変数側ですが、`STRATA_PF_SMALL=0` はこの override を含む small-card rule へ入る前に全体を止めます（同 `generate.cpp:12582-12583`）。

## 実行時の詳細

cache lending の setup 内で、既定 chunk の scan 後にこの環境値を読みます。関数内 static cache はなく、この判定を通るたびにプロセス環境を参照します。プロセス起動後の環境変更も、この読み取りより前に行われれば判定に反映されます（`engine/src/program/generate.cpp:12452-12453`、`12561-12578`）。

条件を満たすと `small_card_prompt_path` が `fused_off=true` とし、`STRATA_PREFILL_LAYER_MAJOR` が未設定または空なら chunk が 2 個以上のときに `layer_major=true` を返します。fused override を設定し、layer-major を選んだ場合は環境変数を `1` にしてから chunk を再 scan します。再 scan が成立すれば新しい chunk で prompt path を進めます（`engine/include/strata/core/sm120_series.hpp:205-218`、`engine/src/program/generate.cpp:12576-12594`）。

ただし Unix 系では `setenv("STRATA_PREFILL_LAYER_MAJOR", "1", 0)` が既存値を上書きしません。空文字は上の判定で「未指定」と扱われる一方、`setenv` からは既存値なので `1` に置き換わらず、後段の resolver も空文字を既定値として読むため layer-major が有効にならないことがあります。Windows は `_putenv_s` で値を設定します（`generate.cpp:12572-12590`; `engine/src/prefill/prefill.cpp:9657-9661`; `engine/include/strata/core/sm120_series.hpp:189-192`）。

新しい layout の chunk が収まらない場合は fused override を戻し、rule が設定した layer-major 値を解除して既定 path を再 scan します。環境に元からあった非空の layer-major 値は `pp.layer_major` が false なので、この解除経路では対象になりません（`generate.cpp:12595-12606`）。

## ログと測定値

経路を再 scan できた場合、stderr に `strata serve: small expert cache: the default prompt path would read in chunks of ...` で始まる行が出ます。再 scan 失敗時は `strata serve: small expert cache: the unfused prompt path does not fit here; the default path stays (chunk ... tokens)` が出ます。`STRATA_PF_SMALL=0` で分岐を止めた場合や、先行条件・small-card 判定を満たさない場合、この rule 固有のログは出ません（`engine/src/program/generate.cpp:12595-12612`）。

この変数の性能差を裏付ける測定値はここでは記載しません。ソースコメントには測定結果への参照がありますが、調査範囲内の設計資料から条件と値を照合できる資料は見つかりませんでした。

## 根拠

- `engine/src/program/generate.cpp:12561-12612` — 読み取り、条件、他変数との関係、再 scan、fallback、stderr 出力。
- `engine/include/strata/core/sm120_series.hpp:195-218` — `8192` の閾値、HIP / defaults / native pack / stage / chunk 条件、small-card path の結果。
- `engine/src/program/generate.cpp:4000-4008`、`6821`、`12452-12453` — CLI の auto chunk と cache borrowing の入口。
- `engine/include/strata/prefill/own_only_switches.hpp:67-73`、`engine/src/prefill/prefill.cpp:244-254` — own-only build が設定した `STRATA_PF_FUSED` とユーザー指定の区別。
- `engine/src/prefill/prefill.cpp:9657-9661`、`engine/include/strata/core/sm120_series.hpp:189-192` — layer-major 環境値の resolver。
