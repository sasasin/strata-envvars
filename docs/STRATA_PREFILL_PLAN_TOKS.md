# `STRATA_PREFILL_PLAN_TOKS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

自動 prefill chunk planner が候補 chunk / ring の所要時間を見積もるときの、prompt 計算速度（tokens/s）の仮定値を指定します。この値は planner のコスト計算と選択に使われます。エンジンの実際の計算速度やスケジューリングを直接設定するものではありません。

環境変数の読み取りは `host_plan_chunk()` 内だけにあります。planner が選んだ chunk が変わると、長い prompt を分割して処理するときの chunk 形状に反映されます。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | `Host::compute_tok_s` の既定値 `1200` tokens/s を使う |
| `atof()` の結果が `0` 以下 | 上書きせず、既定値を使う。空文字、数値で始まらない文字列、`0`、負値もここに含まれる |
| `atof()` の結果が正 | その値で上書きする |

判定と変換には C の `std::atof()` を使い、文字列全体の妥当性検査や上限 clamp はありません。したがって、先頭部分が数値として読める文字列は後続部分を無視して変換されます（例: `1500junk` は `1500`）。先頭空白も `atof()` の変換規則に従います。`NaN` は `> 0.0` を満たさず採用されません。正の無限大など、正値に対する追加の範囲制限はコードにありません。

## 有効になる条件

この値が参照されるのは `host_plan_chunk()` が呼ばれ、次の条件をすべて満たす場合です。

- `--prefill auto` 相当の自動 chunk 選択が有効である。
- 入力 chunk が正である。
- `srcp == &src` であり、別の expert source を使う経路ではない。
- `STRATA_PREFILL_HOST_PLAN` が `0` で始まる値で無効化されていない。ここは `std::atof()` ではなく先頭文字比較のため、`0abc` や `0.5` も無効、空文字や `false` は無効化しない。
- prefill ring の byte-budget 機能が有効である。
- planner 内で全 expert が GPU cache に収まる、または host memory 情報が得られないといった早期 return に該当しない。

ホスト側 planner は既定で有効と `docs/DETAILS.md` に記載されています。資料では Linux の file tier を対象とし、Windows は file tier を unbuffered で読むため既存の chunk 選択を維持すると説明しています。`STRATA_PREFILL_HOST_PLAN` は planner 自体を止める別変数で、`STRATA_PREFILL_PLAN_TOKS` は planner の有効化スイッチではありません。

## 実行時の詳細

planner は GPU cache、RAM copy、file tier、page cache の見積もり、PCIe 転送速度、ドライブ読み出し速度とともに候補ごとの prompt 時間を計算します。`compute_tok_s` はその計算時間項（prompt token 数 / 想定 tokens/s）を決めます。値を変更すると候補間の相対コストが変わり、十分な予測改善がある場合に限って chunk / ring の選択が変わる可能性があります。候補切り替えには、既定では基準案に対して少なくとも5%かつ2秒以上の予測改善が必要です。

planner が実行されるたびに `getenv()` で読みます。static cache ではないため、関数呼び出し前にプロセス環境が変更されれば次の呼び出しで再読込されます。ソース上の呼び出し箇所は、初期化時の multi-GPU prefill 計画と、長さが1024 tokenを超える request ごとの計画です。通常の CLI / server がどの時点で環境を変更するかは、この変数の実装箇所では規定されません。

planner が走ると stderr に候補の選択結果（`strata: prefill plan: ...`）と入力概要（`strata: prefill plan inputs: ...`）を出します。`STRATA_PREFILL_PLAN_TOKS` の採用値自体を表示するログや、変数値が不正であることを示す警告はありません。

## 根拠

- `src/program/generate.cpp:7651-7671`: planner の適用条件、host 情報と既定の計算速度設定、変数の `atof()` 判定と代入。
- `src/program/generate.cpp:7719-7733`: 候補選択、閾値を満たさない場合の元 chunk 維持、ring / chunk の反映。
- `src/program/generate.cpp:8465-8494`: 初期化時の自動 chunk 経路からの呼び出し。
- `src/program/generate.cpp:15551-15582`: 1024 token 超の request prefill 経路からの呼び出し。
- `include/strata/program/prefill_plan.hpp:30-40,121-145`: `compute_tok_s` の既定値 `1200`、計算時間への寄与、選択改善の既定閾値（5%、2秒）。
- `docs/DETAILS.md:1943-1970`: planner の適用範囲、環境変数の説明と測定条件。ここに記載された性能値は同資料の測定結果であり、`STRATA_PREFILL_PLAN_TOKS` 単独の効果を示す値ではありません。
