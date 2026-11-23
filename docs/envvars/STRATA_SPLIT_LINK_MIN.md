# `STRATA_SPLIT_LINK_MIN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`--layer-split auto` の候補評価で、各 GPU のキャッシュに載らない expert の予測コストを PCIe H2D リンク比に応じて増やし始める閾値を指定する。最速 stage と各 stage の計測帯域の比が閾値以上なら、その stage の miss cost に比率を掛ける。これにより自動分割の候補スコアと選ばれる層境界が変わり得る。実行中の転送速度や expert cache の容量を直接設定する変数ではない。`generate.cpp` の自動分割探索でのみ読み取る（`engine/src/program/generate.cpp:6931-6932,6962-6985`）。

## 値と判定

`link_scale_min_resolve` は `nullptr` と空文字を既定値にし、それ以外は `std::strtod` で `double` に変換する。変換が一文字も進まない場合、または変換値が `1.0` 未満の場合も既定値 `4.0` に戻す。`end` が文字列末尾かは検査しないため、数値として読める接頭辞の後ろに文字があっても、その接頭辞が採用される（`engine/include/strata/program/split_rules.hpp:146-156`）。

| 条件 | unset | 有効になる値（例） | 無効・既定値に戻る値（例） |
|---|---|---|---|
| `--layer-split auto` の候補探索 | 閾値 `4.0` | 変換結果が `>= 1.0` の数値。`1`、`3`、`2.5`、`1junk` はそれぞれ `1`、`3`、`2.5`、`1` として採用 | 空文字、`banana`、`0`、`0anything`、`0.5`、負値は `4.0` |

`strtod` を使うため、先頭空白・符号・指数表記などは変換関数の規則に従い、文字列全体の数値妥当性や大文字小文字を別途検査しない。たとえば ` 3tail` は `3`、`3e0x` は `3` として採用される。`nan` は比較 `v >= 1.0` を満たさず既定値、`inf` のように 1 以上へ変換される値はそのまま閾値になる。`errno`、上限値、末尾文字の検証はない（`engine/include/strata/program/split_rules.hpp:151-155`）。

閾値が採用されても、stage の帯域が未計測または `<= 0` なら倍率は `1.0` のまま。計測値が正なら `r = 最速帯域 / 当該帯域` を計算し、`r >= link_min` の場合に `min(r, 64)` を倍率として使う。したがって境界 `r == link_min` は対象になり、閾値は倍率自体を変えず、適用を始める境界だけを変える（`engine/include/strata/program/split_rules.hpp:158-169`）。

## 有効になる条件

- `--layer-split auto` を指定し、サーバーモードで起動する必要がある。`--layer-split` は `o.serve` が偽なら不成立となる（`engine/src/program/generate.cpp:4798-4800,4843-4848`）。
- 複数 GPU を使う自動分割探索に到達する必要がある。可視 GPU が 1 台なら自動分割指定を解除し、分割しない（`engine/src/program/generate.cpp:4831-4835`）。メモリ不足時のカード削減などで 1 台になり自動分割が解除される経路もある（`engine/src/program/generate.cpp:5878-5885`）。
- `--split-skip-if-fits` により CUDA0 だけで足りると判定された場合も分割探索をしない（`engine/src/program/generate.cpp:6422-6455`）。
- リンク帯域の探索時プローブは native pack の場合に行われ、native pack でない場合は各 stage の帯域値が `-1.0` となるため、この閾値による倍率は適用されない。プローブ内の host/device allocation 失敗や計測失敗でも負値が返り、同じく倍率 `1.0` になる（`engine/src/program/generate.cpp:2922-2931,2935-2962,2974-2978,6962-6979`; `engine/include/strata/program/split_rules.hpp:163-166`）。
- `STRATA_SPLIT_UNIFORM` の値が先頭 `'1'` なら全 stage の倍率を `1.0` に戻し、この閾値の効果を無効にする。これは `STRATA_SPLIT_LINK_ABS` より先に評価される。そうでなく `STRATA_SPLIT_LINK_ABS` の値が先頭 `'1'` なら、閾値方式の倍率を使わず、正の帯域に対して `20 / 帯域`（1〜64に clamp）を使う。両変数とも未設定・先頭が `'1'` 以外なら閾値方式が残る（`engine/src/program/generate.cpp:6971-6985`）。
- `--pcie-frac` が指定されていても、この探索自身は必要な per-stage H2D 帯域を計測する。`STRATA_SPLIT_LINK_MIN` は `--pcie-frac` の値を読み替えたり変更したりしない（`engine/src/program/generate.cpp:4775-4777,6962-6969`）。
- 閾値の読取り・スコア計算には OS や backend を分ける条件分岐はない。帯域プローブは通常 CUDA event で計測し、HIP と Windows の組み合わせだけは event がコピー時間を測れないため、同期を挟んだ host timer で測る（`engine/src/program/generate.cpp:2935-2947`）。

## 実行時の詳細

値は `multi_gpu && split_auto` の探索ブロック内で、関数内 `static const double` の初期化時に `std::getenv` から一度読み取られる。resolver と倍率計算自体は GPU 探索中に呼ばれるが、閾値の環境値はプロセス内で初回初期化後に cache され、同一プロセスでの環境変更は反映されない（`engine/src/program/generate.cpp:6931,6977-6979`）。

各 stage の H2D 帯域から最速帯域との比を求め、閾値以上の stage の miss cost を倍率化する。候補配置の予測時間では、各 stage の「その stage に割り当てられた miss mass − cache に保持された mass」に `miss_ms × link_scale` を掛けて合算し、層ごとの予測時間を加える。探索はこのスコアと他の配置制約を使って層境界を選ぶため、変更されるのは予測コストを通じた分割位置であり、生成 token を決める処理ではない（`engine/src/program/generate.cpp:6987,7071-7080,7235-7243,7244-7257,7482-7487`）。

## ログと測定値

この変数の値や fallback 理由だけを示す専用ログはない。探索に進むと各 stage について `strata generate: layer split auto: CUDA%d link %.1f GB/s -> miss cost x%.2f` が stderr に出て、適用後の帯域値と miss cost 倍率を確認できる。選択結果は `strata generate: layer split auto: K=... - predicted ...` の行に出る（`engine/src/program/generate.cpp:6980-6985,7482-7487`）。有効だが条件を満たさない場合、環境変数を理由とした警告はなく、分割探索自体が行われないか倍率 `1.0` となる。

`docs/MULTI_GPU.md:154` は既定閾値 4 と、閾値を 3 にした場合に PCIe 4.0 x8 + x2 の例で x2 側の層数が減るという説明を掲載している。実装上は同じ閾値規則と整合する。`docs/DETAILS.md` にこの変数の記載はない。ここでは資料の速度測定値を一般化せず、コードで追えるスコアへの作用だけを記した。

## 根拠

- `engine/src/program/generate.cpp:6931-6932,6962-6985` — 探索条件、帯域計測、環境変数の読み取り、別設定による上書き、ログ。
- `engine/src/program/generate.cpp:7071-7080,7235-7243,7244-7257,7482-7487` — miss cost を含む配置スコアと選択結果。
- `engine/src/program/generate.cpp:4775-4800,4831-4848,5878-5885,6422-6455` — server / auto / 複数 GPU / split skip の適用条件。
- `engine/include/strata/program/split_rules.hpp:146-169` — 既定値、`strtod` 判定、比率境界、倍率上限。
- `docs/MULTI_GPU.md:154` — 関連説明との照合（挙動の根拠は上記ソースコード）。
