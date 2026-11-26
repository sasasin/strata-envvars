# `STRATA_ADAPT_FETCH_MIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

PCIe share で取得した未常駐 expert を VRAM cache に採用する際の、候補 expert に必要な最小 routing 回数を指定する。未設定なら `ExpertDispatch::fetch_min` の初期値 `1.0f` が使われる。候補の回数は各 layer の routing entry ごとに `usage` に加算され、対象変数は候補選別の `use[e] >= fetch_min` 判定にだけ関わる。採用候補の VRAM cache への配置には、別の差分閾値 `STRATA_ADAPT_FETCH_MARGIN` も必要になる。`STRATA_ADAPT_FETCH` が無効、または fetch 機能の利用条件を満たさない場合、この値は読み取られず、fetch の動作にも使われない（`engine/include/strata/core/expert_source.hpp:659-661,674-692`、`engine/src/core/expert_source.cpp:5472-5474,5640-5672`、`engine/src/program/generate.cpp:15067-15089,24580-24603`）。

## 値と判定

`std::getenv` が null でなければ `std::atof` で変換し、`float` にして `fetch_min` に代入する。未設定時は初期値を維持し、空文字は設定済みとして変換され `0` になる。`atof` は数値文字列全体の厳密な検査をせず、先頭から変換できる部分を読み、変換できなければ `0` を返す。値の clamp やエラー処理はない（`engine/include/strata/core/expert_source.hpp:679-680`、`engine/src/program/generate.cpp:15083-15084,24596-24597`）。

| 条件 | 未設定 | 例と実効値 | 注意 |
|---|---|---|---|
| fetch の初期化条件を満たす | `1.0f` | `1` → `1`、`0anything` → `0`、`1.75tail` → `1.75`、`true` / `false` / 空文字 → `0`、` -2` → `-2` | 前後の空白を含む数値は `atof` の変換対象になる。無効な接尾辞は拒否されず、数値部分だけが使われる。負数を含め値域制限はない。 |
| fetch が無効、または初期化条件を満たさない | 読み取りなし | 値は fetch 用 `drive.d.fetch_min` に反映されない | この経路では同フィールドの既定値が残っても fetch 自体が有効にならない。 |

実効値は routing 回数との比較に使われる。`NaN` のように比較が真にならない値では候補条件を通らない。設定値の数値妥当性、有限性、符号は検証されない（`engine/src/core/expert_source.cpp:5647-5652`）。

## 有効になる条件

- 親スイッチ `STRATA_ADAPT_FETCH` が正の値であること。`adapt_fetch()` は未設定を `0` とし、`atoi` の結果を `0..2` に clamp してプロセス内 static に保持する。NVIDIA の対応 GPU では起動時の既定値注入により `2` となる場合もある。これは対象変数の既定値を変えず、対象変数自身には CLI 引数の優先設定はない（`engine/src/program/generate.cpp:2345-2347,4438-4448,15067-15089,24580-24603`、`engine/src/core/nv_defaults.cpp:21-24,222-238`）。
- 適応 tier が動作して routing 使用量 `usage` が記録されること。CLI の適応設定 (`--adapt-every` と `--adapt-swaps`) が有効でなければ対象変数は使われない（`engine/src/program/generate.cpp:15001-15002,24563-24570`）。
- residency table と 1 slot 以上の VRAM expert cache があり、GPU plan が PCIe share を持つこと。fetch 実行時には `ExpertDispatch::fetch_can` が `plan->pcie_mode == 2`、`plan->dst2 != nullptr`、`pcie_num > 0`、PCIe 層のデータソースなども要求する（`engine/src/program/generate.cpp:15055-15072,24571-24585`、`engine/src/core/expert_source.cpp:5271-5275`）。
- serve 経路では layer split、peer/helper GPU、`--adapt-async`、`--pipeline-windows`、`--batch`、`STRATA_ADAPT_OVERLAP=1`、`--pcie-mode dma` / `direct`、resident RAM mode などの除外条件に該当しないこと。generate 経路では `--spec-split`、layer split、peer/helper tier、`--pcie-mode dma` / `direct`、resident RAM mode などで対象機能が使われない（`engine/src/program/generate.cpp:15055-15072,24571-24585`）。
- 各 verify window で PCIe share に割り当てられた未常駐 expert であり、source blob が pin 済みであること。候補 expert は window 内で routing されたものを除いた resident expert の最小使用回数と `STRATA_ADAPT_FETCH_MARGIN` でも比較され、in-flight でない場合に slot を置き換える（`engine/src/core/expert_source.cpp:5555-5571,5640-5676`）。

## 実行時の詳細

対象変数は `strata serve` と `strata generate` の engine 初期化箇所で、fetch が有効と判定された場合に直接読み取られる。ここで `fetch_min` にコピーした後は dispatch の各 verify window がそのフィールドを使う。対象変数の読み取り自体に static cache はないが、初期化後に環境を変更しても、すでに作られた `ExpertDispatch` の閾値は変わらない（`engine/src/program/generate.cpp:15067-15084,24580-24597`、`engine/src/core/expert_source.cpp:5647-5652`）。

各 layer の verify window では routing entry 数を `usage` に加算する。PCIe share が選んだ miss のうち、`use[e] >= fetch_min` で in-flight ではない expert が候補になり、routing 数の大きい順に、window 内で未使用の resident expert と比較される。`use[e] < use[v] + fetch_margin` なら採用を止め、それ以外では resident slot を候補に割り当て、host residency table を更新する。よってこの閾値は expert の選択数やモデル出力を直接指定する値ではなく、取得済み expert を VRAM tier に残す条件の一つである（`engine/src/core/expert_source.cpp:5472-5474,5640-5679`）。

## ログと測定値

fetch 初期化が成功すると stderr に `strata serve: STRATA_ADAPT_FETCH=%d: the PCIe share takes each layer's most-routed misses and admits those routed >= %.2f and %.2f more than a resident one%s\n` または同じ接頭辞の `strata generate:` 行を出し、`fetch_min` と `fetch_margin` を小数点以下 2 桁で表示する。表示は丸められるが、比較には `float` の値を使う。親スイッチが有効でも利用条件を満たさない場合は `strata serve: STRATA_ADAPT_FETCH is off (%s)\n` / `strata generate: STRATA_ADAPT_FETCH is off (%s)\n`、既定注入値なら `strata serve: STRATA_ADAPT_FETCH=2 (the default for this card) is not used in this run (%s)\n` / `strata generate: STRATA_ADAPT_FETCH=2 (the default for this card) is not used in this run (%s)\n` を出し、対象値の閾値行は出ない（`engine/src/program/generate.cpp:15073-15088,24586-24602`）。

この環境変数単独の測定値は該当なし。`docs/DETAILS.md` の `STRATA_ADAPT_FETCH` 記述は親機能の条件と測定をまとめているが、`STRATA_ADAPT_FETCH_MIN` 個別の測定値は示していない（`docs/DETAILS.md:1262`）。

## 根拠

- 初期値と dispatch 状態: `engine/include/strata/core/expert_source.hpp:659-692`
- `strata serve` / `strata generate` の読み取りと条件: `engine/src/program/generate.cpp:15055-15089,24570-24603`
- 実行時の eligibility と閾値比較・slot 更新: `engine/src/core/expert_source.cpp:5271-5275,5472-5474,5555-5571,5640-5679`
- 親スイッチの parsing と NVIDIA 既定値: `engine/src/program/generate.cpp:2345-2347,4438-4448`、`engine/src/core/nv_defaults.cpp:21-24,222-238`
- 設計資料との照合: `docs/DETAILS.md:1262`
