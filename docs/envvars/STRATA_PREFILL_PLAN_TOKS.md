# `STRATA_PREFILL_PLAN_TOKS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

host-aware prefill planner が予測 prompt 計算速度として使う `compute_tok_s`（token/s）を上書きします。これは chunk × ring 候補の推定時間を採点する入力です。実測速度の変更や GPU 計算自体の制御ではありません。planner が別の chunk または ring を選べば、その形で prefill が進みます。読み取りと採点は `engine/src/program/generate.cpp:11432-11455`、推定時間への使用は `engine/include/strata/program/prefill_plan.hpp:34-39,81-99` です。

## 値と判定

planner の呼び出しごとに `std::getenv` し、設定されていて `std::atof(e) > 0.0` の場合だけ、その `atof` 結果を採用します。それ以外は `Host::compute_tok_s` の既定値 `1200` token/s です。数値全体の消費確認や上限・下限の clamp はありません（`engine/src/program/generate.cpp:11449-11455`; `engine/include/strata/program/prefill_plan.hpp:34-39`）。

| ビルド・経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `engine/src/program/generate.cpp` の host planner | 1200 token/s | 正の `atof` 値。例: `1`, `1200`, `1e3`, ` 25`, `12tail`（数値 prefix の 12 を変換） | 空文字、`0`, `-1`, `true`, `0anything`, 数字で始まらない文字列。`atof` 結果が正でないため既定値を使う |

`std::atof` は末尾までの数値文字列検証をしないため、例の `12tail` は 12 として受理されます。先頭空白を含む数値も変換されます。正値なら大小を問わずそのまま使い、別の数値境界チェックはありません。大文字小文字比較は行わず、`true`/`false` は数値扱いされません（`engine/src/program/generate.cpp:11454-11455`）。

## 有効になる条件

- `--prefill auto` 等で `o.prefill_auto` が有効で、正の chunk があること。固定値の `--prefill N` はこの host planner の対象になりません（`engine/src/program/generate.cpp:4000-4008,11439-11441`）。
- 元の expert source が `src`（`srcp == &src`）であり、`STRATA_PREFILL_HOST_PLAN` が未設定か、先頭文字が `0` 以外であること。`STRATA_PREFILL_HOST_PLAN=0` や `0anything` は planner を迂回します（`engine/src/program/generate.cpp:11438-11441`）。
- `Prefill::ring_bytes_enabled()` が true であること。byte-budget ring が無効なら host planner を呼んでも chunk をそのまま返します（同 `11438-11441`; `engine/src/prefill/prefill.cpp:833-845,3912`）。
- 対象 expert の総量が 0 ではなく、GPU cache が全 expert を保持していないこと。さらに `sample_host_memory()` が値を返す必要があります。条件を満たさなければ環境変数は読まれず、元の chunk が返ります（`engine/src/program/generate.cpp:11442-11447`）。
- serve の初期 chunk 計画では auto と ring 条件の下で呼び出されます。生成時はさらに prefill borrow が許可され、resident source と device residency があり、`k > 0`、`n_batched > 1024` のときに prompt 長を渡して呼びます（`engine/src/program/generate.cpp:12629-12657,23989-24010`）。
- 対象名の直接参照は `engine/src/program/generate.cpp` にだけあります。SYCL 専用実装 `engine/sycl/src/program/generate.cpp` にはこの名前の読み取りがなく、この変数の効果をその経路へは一般化できません。対象箇所自体には OS / build macro の条件分岐がありません。
- `STRATA_SSD_GBPS` は別入力の drive 速度を上書きしますが、この変数の値を上書きしません（`engine/src/program/generate.cpp:1891-1905,11451-11505`）。`STRATA_PREFILL_RING` は実際の ring の解決に優先します（`engine/src/prefill/prefill.cpp:833-875`; `engine/include/strata/prefill/prefill.hpp:146-150`）。

## 実行時の詳細

環境値は `host_plan_chunk` の各実行で読み直され、関数内 `static` や他の cache には保存されません。serve 初期化時と、条件を満たした個々の長い prompt の計画で再び読み取られ得ます。したがって、プロセス内で環境値が変わった場合でも、次の planner 呼び出しが新値を読みます（`engine/src/program/generate.cpp:11432-11455,12629-12657,23989-24010`）。

planner は RAM copy, GPU cache, page cache, drive, PCIe の推定値から候補を作り、`prefill_plan::choose` で最小予測時間を選びます。`compute_tok_s` は `tokens / compute_tok_s * ring_pen` の項と予測秒数に使われます。選択変更には基準案から 5% 以上かつ 2 秒以上の予測改善が必要で、満たさなければ基準 chunk/ring を維持します（`engine/include/strata/program/prefill_plan.hpp:81-99,106-127`）。選択が変わると ring budget と chunk 計画に反映されます。serve 初期化では buffer は元の chunk 用に保ち、より小さい計画 chunk は長い prompt に使います（`engine/src/program/generate.cpp:11513-11518,12659-12663`）。生成時も計画 chunk に従って prompt chunk と lend 数を更新します（同 `23997-24024`）。

この値のために Strata が子プロセスへ環境変数を転送する処理は、対象参照からは確認できません。

## ログと測定値

planner が実行されると、選択が変わる場合は `strata: prefill plan: chunk ... -> ..., ring ... -> ...: ...`、変わらない場合は `strata: prefill plan: chunk ..., ring ... kept: ...` を stderr に出し、続けて `strata: prefill plan inputs: ...` を出します。いずれも `STRATA_PREFILL_PLAN_TOKS` 自体の値や採否は表示しません。早期 return で planner が動かない場合、これらの planner ログも出ません（`engine/src/program/generate.cpp:11438-11512`; `engine/include/strata/program/prefill_plan.hpp:151-173`）。この変数固有の警告・終了・失敗経路は見つかりませんでした。

`docs/DETAILS.md:346-351` は host planner を Linux の file-tier 経路とし、Windows では動かないと記載しています。一方、調査対象コードの host planner に OS guard はなく、`sample_host_memory()` は Windows 分岐も持ちます（`engine/src/program/generate.cpp:11438-11447`; `engine/src/core/conversation_memory.cpp:411-424`）。この文書では実装コードを根拠とし、DETAILS の Windows に関する説明との食い違いを記録します。新たな測定値はありません。

## 根拠

- 変数の全直接参照、判定、値の採用: `engine/src/program/generate.cpp:11432-11455`。
- host planner の早期 return、入力構築、候補評価、ring/chunk の反映: `engine/src/program/generate.cpp:11438-11518`。
- 既定値・予測式・選択閾値・ログ文言: `engine/include/strata/program/prefill_plan.hpp:34-39,81-127,151-173`。
- serve 初期 chunk 計画と生成時の適用条件: `engine/src/program/generate.cpp:12629-12663,23989-24024`。
- planner 用メモリ取得の OS 分岐: `engine/src/core/conversation_memory.cpp:411-424`。
- drive 速度の別入力: `engine/src/program/generate.cpp:1891-1905`。
- ring byte budget と ring override: `engine/src/prefill/prefill.cpp:833-875`; `engine/include/strata/prefill/prefill.hpp:146-150,204-211`。
