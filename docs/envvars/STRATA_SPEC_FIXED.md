# `STRATA_SPEC_FIXED`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（2026-11-17 時点）。

## 役割

`STRATA_SPEC_FIXED` は、投機的デコードの `DraftPolicy` が参照する窓コストを固定します。通常は実行中に測った round 時間でコストが更新されますが、この変数が有効なら測定値で更新しません。コストは MTP 窓と prompt-lookup 窓の選択に使われます。選択した窓は verifier の batch 幅を変え、Strata のコメントは異なる窓が異なる出力 token を生み得ると説明しています。この変数はコストと窓選択を制御し、トークン分布を直接設定するものではありません（`src/spec/draft_policy.cpp:447-472`, `577-615`, `652-679`; `include/strata/spec/draft_policy.hpp:21-25`）。

## 値と判定

`std::getenv` の返り値が null でなく、先頭文字が `'1'` の場合だけ有効です。文字列全体や数値としての妥当性は検査しません。未設定・空文字・先頭が `1` 以外なら無効です。大文字小文字や空白の除去はありません（`src/spec/draft_policy.cpp:40-54`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 全ビルド共通の `DraftPolicy` 初期化 | 無効。測定 round 時間に応じてコストが更新される | `1`, `10`, `1anything` | 空文字, `0`, `0anything`, `true`, ` 1` |

有効時に `STRATA_SPEC_FIXED_TABLE` が未設定または空文字なら、組み込みの窓コスト形状が固定されます。非空ならカンマ区切りの先頭最大 16 要素を `std::atof` で読みます。`atof` の結果が正数の要素だけがコスト表として採用され、全要素を正数として検証する処理はありません。たとえば `12ms` は `12`、`bad` や `0` は採用されず、負数も採用されません。余分な要素は無視されます。固定表がないサイズは `cost_ms()` の既定形状・利用可能なサイズからの比例推定に委ねられます（`src/spec/draft_policy.cpp:18-19`, `40-54`, `454-472`, `495-507`）。

## 有効になる条件

- `DraftPolicy` が生成される実行経路で評価されます。ソース上の生成箇所はサーバー処理と通常の生成処理です（`src/program/generate.cpp:15215-15216`, `22391-22393`）。索引 `docs/SETTINGS.md` は NVIDIA / AMD 向けと記載していますが、環境値の判定自体には backend や OS の条件分岐がありません（`docs/SETTINGS.md:259`, `src/spec/draft_policy.cpp:40-54`）。
- 固定コストは窓選択で参照されます。`choose()` は lookup 候補数 `lookup_k` が 0 以下なら MTP 窓をそのまま返すため、その呼び出しでは固定表による lookup 窓選択はありません（`src/spec/draft_policy.cpp:577-615`）。`STRATA_SPEC_COST=1` の cost-aware MTP chaining もコストを参照する別機能であり、この変数だけでは有効化されません（`src/program/generate.cpp:15223-15233`, `include/strata/spec/draft_policy.hpp:287-292`）。
- `--draft-costs` は `policy.fixed()` が false の場合だけ読み込まれます。この環境変数で固定済みなら、その処理はスキップされ、CLI のコスト表は上書きしません（`src/program/generate.cpp:15253-15262`）。
- `--spec` などで決まる `DraftPolicy` の最大窓幅は別に適用され、固定表が幅を拡張することはありません（`src/program/generate.cpp:22389-22418`, `include/strata/spec/draft_policy.hpp:208-213`）。

## 実行時の詳細

設定は `fixed_env()` 内の関数ローカル `static const` に一度だけ保存されます。最初の `DraftPolicy` 生成時に環境を読み、その後に同一プロセス内で環境を変更しても反映されません。`STRATA_SPEC_FIXED=1` なら 3 つの context bucket（位置 `<6K`、`<24K`、それ以上）すべてに同じ表を設定します（`src/spec/draft_policy.cpp:40-54`, `447-452`; `include/strata/spec/draft_policy.hpp:154`, `src/spec/draft_policy.cpp:530-550`）。

表の各正数は窓サイズ 1 から順に対応し、設定された値は既存のコストを置き換えます。表が短い場合や正数でない要素は、その窓の直接コストにならず、`cost_ms()` が同じ bucket の既知サイズから形状比で推定し、既知サイズがなければ組み込み `kShape` を返します。固定中は round 時間を `CostLearner` に記録する設定が別途あっても、`cost_` の更新は行われません（`src/spec/draft_policy.cpp:454-472`, `495-507`, `652-679`）。

## ログと測定値

この変数を読み取る箇所や `DraftPolicy` コンストラクターには、この設定の有効・無効や表の内容を通知するログがありません（`src/spec/draft_policy.cpp:40-54`, `447-452`）。測定値の新規記載はありません。`docs/SETTINGS.md` は変数名と on/off、backend の一覧のみを示し、`docs/DETAILS.md` にこの変数の個別説明は見つかりませんでした。

## 根拠

- `src/spec/draft_policy.cpp:33-54` — 環境変数の読み取り、先頭文字判定、表のキャッシュと変換。
- `src/spec/draft_policy.cpp:447-472` — コンストラクターで全 bucket に適用し、固定コストを設定。
- `src/spec/draft_policy.cpp:495-507`, `577-615`, `652-679` — コストの参照・窓選択と、固定時に測定 round でコスト更新しない分岐。
- `src/program/generate.cpp:15215-15216`, `15223-15262`, `22391-22418` — 利用経路、関連設定、`--draft-costs` の適用条件。
- `include/strata/spec/draft_policy.hpp:154`, `208-215`, `287-292` — bucket 数、固定コスト API、別機能の cost-aware MTP chaining。
- `docs/SETTINGS.md:259` — 設定一覧上の backend 表記。
