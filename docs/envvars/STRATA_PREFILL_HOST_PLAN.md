# `STRATA_PREFILL_HOST_PLAN`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

自動 prompt chunk (`--prefill auto`) の候補を、GPU cache に収まるかだけでなく、RAM の page cache とモデルファイルからの読み込み量も含めて選び直します。候補の chunk と ring の組を予測時間で比較し、十分な改善が見込める場合に prompt の chunk 計画を変更します。重みや expert の配置は変更しません。

この環境変数は `host_plan_chunk` 内で読み取られます。通常の単一 GPU prompt 経路と layer-split prompt 経路の両方がこの helper を呼びます。

## 値と判定

実装は値全体を parse せず、`getenv()` の有無と先頭文字だけを見ます。

| 値 | 判定 |
|---|---|
| 未設定 | planner を許可（既定で ON） |
| 空文字 | planner を許可。設定ありだが `off[0]` は `\0` であり `'0'` ではない |
| 先頭文字が `0` | planner を無効化。`0`, `0anything` など |
| それ以外 | planner を許可。`1`, `false`, `anything` など |

大文字小文字、空白、数値としての妥当性は検査しません。判定は呼び出しごとに `getenv()` で行われ、static cache されません。

## 有効になる条件

値が許可でも、次をすべて満たす場合に限り planner の候補計算へ進みます。

- `--prefill auto` が有効（`o.prefill_auto`）。明示 chunk は対象外。
- 入力 chunk が正。
- expert source が通常の `src` (`srcp == &src`) である。arena source など他の source は対象外。
- `STRATA_PREFILL_HOST_PLAN` の先頭が `0` ではない。
- `Prefill::ring_bytes_enabled()` が true。

さらに、expert の総量を算出できない場合、全 expert が GPU cache に収まる場合、または host memory のサンプルを取得できない場合は、元の chunk をそのまま返します。これらの条件では planner の説明ログも出ません。RAM copy が GPU cache 外の expert をすべて保持していて計算上の file tier が 0 になるケースは、この早期 return 条件ではなく、候補評価へ進みます。

## 実行時の詳細

planner は `STRATA_PREFILL_PLAN_TOKS` が設定され正数として `atof()` で読める場合、その値を予測計算の prompt throughput に使います。それ以外は helper の既定値 1200 token/s です。page-cache 予算は `sample_host_memory()` の available RAM から 1200 MiB を差し引いた値（ただし下限 0）で、unbuffered source なら 0 です。PCIe 速度は直近の H2D 測定値、未測定なら 12 GB/s を使います。drive 読み込み速度は `drive_read_gbps()` が与え、`STRATA_SSD_GBPS` が正数ならその値を優先します。

planner は既存の GPU 向け chunk を基準候補にし、512-token 以上の複数 chunk と ring の候補を構成します。page cache に対する file set の大きさから推定した drive miss、H2D stream、prompt compute、ring の penalty を足して候補を比較します。基準より少なくとも 5% かつ 2 秒以上速い予測でなければ変更しません。変更時は ring 予算も選択値に合わせます。単一 GPU 経路では選択 chunk を `pf_plan_chunk` に記録し、確保済み buffer のサイズは GPU 向け chunk のまま保持します。実際の prompt 長に応じた適用は後続の planned/equal chunk 処理で行われます。layer-split 経路でも helper の選択後に request 長に合わせた chunk を決めます。

条件を通過すると stderr に `strata: prefill plan:` の行と planner 入力の要約が出ます。候補を変更しない場合は `chunk ... kept` 相当の説明、変更する場合は `chunk A -> B` と予測値を表示します。早期 return の条件に当たる場合はこのログを出しません。

`docs/DETAILS.md` は Linux の file tier 向けの既定 ON 機能として紹介し、Windows の unbuffered 読み込みでは従来 chunk を維持すると説明しています。一方、この helper 自体には OS 判定による一律の無効化はなく、unbuffered source は page-cache 予算を 0 としてモデル計算に渡します。したがって OS ごとの実際の選択は、他の条件と入力値を含めた planner の結果によります。

## 根拠

- `src/program/generate.cpp:7647-7661` — helper、環境変数の判定、適用条件、全 expert が GPU にある場合と host memory 不明時の早期 return。
- `src/program/generate.cpp:7663-7682` — page-cache、PCIe、drive、計算速度、file tier と対象 token 数の設定。
- `src/program/generate.cpp:7683-7733` — 候補生成、選択、ログ、ring 予算の反映。
- `src/program/generate.cpp:8465-8498` — layer-split prompt 経路での呼び出しと、選択 chunk を計画値として保存する処理。
- `src/program/generate.cpp:15555-15583` — 通常 prompt 経路での呼び出しと request 長への適用。
- `include/strata/program/prefill_plan.hpp:34-39,81-127,151-173` — planner の既定値、費用計算、変更閾値、ログ文面。
- `src/program/generate.cpp:1365-1380` — drive 読み込み速度と `STRATA_SSD_GBPS` の優先。
- `docs/DETAILS.md:1943-1968` — 適用対象の説明と、記載された測定条件・結果。測定値は同資料の報告であり、この調査で再測定したものではありません。
