# `STRATA_SPEC_FIXED_TABLE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`STRATA_SPEC_FIXED_TABLE` は speculative draft policy の窓サイズ別コスト（窓の行数 1..N に対する round 時間、ms）を指定します。この変数だけでは適用されず、`STRATA_SPEC_FIXED` が先頭文字 `1` で始まる場合に限り、`DraftPolicy` の各 context bucket に同じ表を固定コストとして設定します。固定コストは測定済みコストを置き換え、実測 round 時間によるコスト更新と未測定サイズの再測定 probe を止めます。コストは lookup window と MTP window の選択に使われますが、受理 token 数などの学習統計まで固定するわけではありません（`src/spec/draft_policy.cpp:33-54,447-471,577-615,668-688`、`include/strata/spec/draft_policy.hpp:208-215`）。

## 値と判定

この変数を読むのは `fixed_env()` の一箇所です。`STRATA_SPEC_FIXED` が有効なとき、`STRATA_SPEC_FIXED_TABLE` が未設定でなく、かつ空文字でなければ、先頭から comma 区切りで最大 16 要素を走査します。各要素は `std::atof` で変換され、文字列全体の妥当性検査はありません（`src/spec/draft_policy.cpp:40-54`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `STRATA_SPEC_FIXED` が未設定、空、または先頭文字が `1` 以外 | fixed table は無効 | なし。この変数は読み取られない | 任意の値が適用されない |
| `STRATA_SPEC_FIXED` の先頭文字が `1` | 空表として fixed 扱い。内蔵 shape をコストに使う | comma 区切り要素の `atof` 結果が正数（例: `1,2.5,4`）。数値 prefix を読むため `2ms` は `2` | `0`、負数、`junk`、空要素は変換結果が正数にならず該当サイズのコストに使われない |

`STRATA_SPEC_FIXED` 自体も文字列全体の比較ではなく `e[0] == '1'` です。そのため `1`, `10`, `1anything` は有効、`0`, `true`, ` 1`, 空文字、未設定は無効です。テーブル側の `atof` は先頭空白や数値後続文字を許し、厳密な数値・有限値の検査をしません。空要素は `0` 相当となり、その列を欠測扱いにします。先頭が comma の文字列も先頭要素が 0 になります。`inf` など正の無限大も `> 0` 判定を通ります。16 要素を超える部分は無視されます（`src/spec/draft_policy.cpp:43-50,463-471`）。

## 有効になる条件

- `STRATA_SPEC_FIXED` の先頭文字が `1` であること。`STRATA_SPEC_FIXED_TABLE` 単独では反映されません（`src/spec/draft_policy.cpp:43-50`）。
- 実行経路で `DraftPolicy` が構築され、かつその policy のコストを使う選択経路に入ること。policy の構築箇所は通常生成と serve の speculative generation 内にあります（`src/program/generate.cpp:15215-15216,22392-22393`）。lookup window の選択は `DraftPolicy::choose()` が行い、lookup 候補がない場合はコスト比較をしません（`src/spec/draft_policy.cpp:577-615`）。
- `STRATA_SPEC_COST` はこの固定表を有効化する条件ではありません。別途、先頭文字 `1` のとき MTP の cost-aware window rule が有効になります（`src/program/generate.cpp:15223-15232,22346-22348`）。
- 既存サーバー設定 `--draft-costs` の読み込みは `!policy.fixed()` の場合だけ行われるため、この環境変数で policy が固定されているとファイル表の読み込みはスキップされます（`src/program/generate.cpp:15253-15262`）。CLI 経路では `STRATA_SPEC_COST_TABLE` による seed が `STRATA_SPEC_COST=1` の場合に別途実行されます。`seed_costs()` は既存の正コストを上書きしませんが、固定表で欠測になったサイズには値を補えます。固定状態は解除されず、補ったコストも実測で更新されません（`src/program/generate.cpp:22396-22411`、`src/spec/draft_policy.cpp:521-528,668-678`）。
- 読み取り箇所には OS / backend の条件分岐がありません。共通実装は CPU backend と SYCL target のソース構成に含まれます（`cmake/backends/cpu.cmake:20`、`sycl/CMakeLists.txt:159`）。環境変数一覧 `docs/SETTINGS.md:259-260` は NVIDIA と AMD を記載していますが、値の読取り・判定箇所自体にその限定はありません。

## 実行時の詳細

`fixed_env()` の関数内 `static const FixedEnv` が初回呼び出し時に両環境変数を読み、以後同じプロセス内の `DraftPolicy` 構築で共有します。したがって初回構築後に環境を変更しても再読込されません（`src/spec/draft_policy.cpp:40-54,447-452`）。

有効な固定設定があると、同じテーブルを context bucket 0..2 に設定します。各要素の値が正数なら当該サイズのコストとして保存されます。非正数・無効 prefix の列は保存されず、他のサイズにも値がなければ `cost_ms()` は内蔵の `kShape` を返します。CLI の `STRATA_SPEC_COST_TABLE` seed が同時に使われる場合は、固定表で欠測のサイズをその seed が埋めることがあります。テーブルが未設定・空の場合も policy は fixed 状態になりますが、他の seed がなければコスト値は内蔵 shape になります（`src/spec/draft_policy.cpp:18-19,447-471,495-507,521-528`、`src/program/generate.cpp:22396-22411`）。

固定状態では round time が `observe()` に渡ってもコスト更新は行われず、`stale()` による再測定も起きません。一方、lookup / MTP の成功・受理結果の統計は通常どおり更新されます。`choose()` はコストと受理率から MTP と lookup の期待値を比べ、lookup が margin を超える場合に lookup window とサイズを選びます（`src/spec/draft_policy.cpp:570-615,668-688`）。表は選択基準を変えますが、モデルの token 計算・検証自体を置き換えません。

## ログと測定値

この環境変数の読み取りや値の拒否を示す専用ログ、警告、終了経路はありません。無効・空の要素は失敗を起こさず、固定表のそのサイズにコストが設定されない扱いになります（`src/spec/draft_policy.cpp:40-54,463-471`）。`docs/DETAILS.md` にこの名前の記述はなく、同資料から測定値は確認できません。

## 根拠

- `src/spec/draft_policy.cpp:33-54` — 固定環境設定の取得、依存条件、comma 区切りと `atof`。
- `src/spec/draft_policy.cpp:447-471,495-507,570-615,668-688` — policy 構築、コスト適用・fallback、選択と更新。
- `include/strata/spec/draft_policy.hpp:208-215` — fixed table の効果と学習との区別。
- `src/program/generate.cpp:15215-15216,15223-15232,15253-15262` — serve policy、`STRATA_SPEC_COST`、`--draft-costs` の条件。
- `src/program/generate.cpp:22392-22411` — CLI policy と `STRATA_SPEC_COST_TABLE` の適用条件。
- `cmake/backends/cpu.cmake:20`、`sycl/CMakeLists.txt:159` — 共通 policy 実装の backend 構成。
