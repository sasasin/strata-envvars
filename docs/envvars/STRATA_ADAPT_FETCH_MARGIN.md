# `STRATA_ADAPT_FETCH_MARGIN`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

`STRATA_ADAPT_FETCH` による VRAM expert の admission で、PCIe 経由で取得した未 resident expert を、window が使わない resident expert の slot に入れるか決める使用回数の差を指定します。候補 expert の使用回数が比較対象の resident expert より少なくともこの値だけ多い場合に admission します。

この値だけでは機能は有効になりません。`STRATA_ADAPT_FETCH` が有効で、適応 tier、GPU residency table、GPU plan、PCIe share などの条件を満たしたときだけ読み取られ、判定に使われます。

## 値と判定

`ExpertDispatch` の既定値は `0.5f` です。設定されている場合、`std::atof` で `float` に変換して上書きします。文字列全体の妥当性検査、範囲検査、clamp はありません。

| 状態・値 | 結果 |
|---|---|
| 未設定 | 既定値 `0.5` を維持 |
| 空文字 | `atof("")` の結果 `0` を設定 |
| 数値文字列 | `atof` の変換結果を `float` にして設定。例: `0.75` |
| 数値の後ろに文字が続く値 | 数値として読める先頭部分を変換。例: `0.5x` は `0.5` |
| 数字として読めない値 | 変換結果 `0` |
| 負値 | そのまま設定。負値なら、候補の使用回数が比較対象より小さくても、差が設定値以上なら条件を通り得る |
| 大きな値 | 上限なし。比較条件を満たす候補がなくなり得る |

候補の使用回数 `use[e]` が resident expert の使用回数 `use[v]` に margin を加えた値より小さい場合は admission を止めます。したがって境界値と等しい場合は条件を通ります（`use[e] < use[v] + fetch_margin` なら停止）。設定値の読み取り・変換時のエラーや警告は実装されていません。

## 有効になる条件

margin は次の条件を通過した場合にだけ読み取られます。

- `STRATA_ADAPT_FETCH` の値が 1 または 2 相当である（この変数自身が機能を opt-in するのではない）。
- 適応 tier が稼働し、GPU residency table と GPU plan がある。
- PCIe share が 0 より大きく、`--pcie-mode dma` / `direct` ではない。
- resident RAM mode ではない。
- 実行経路固有の制限を満たす。serve は layer split、peer device、helper GPU、`--adapt-async`、`--pipeline-windows`、`--batch`、`--spec-split`、`STRATA_ADAPT_OVERLAP=1` などで admission を停止する。generate は `--spec-split`、layer split、peer tier、helper GPU などで停止する。

停止理由がある場合、margin は読み取られず、その値に関するログも出ません。停止理由はそれぞれ `strata serve: STRATA_ADAPT_FETCH is off (...)` または `strata generate: STRATA_ADAPT_FETCH is off (...)` と stderr に出ます。開始条件を満たすと、起動時に `STRATA_ADAPT_FETCH=...` の閾値を示すログが出ます。

## 実行時の詳細

`strata serve` と `strata generate` の初期化経路に読み取り箇所があります。どちらも `STRATA_ADAPT_FETCH` が正で、上記の停止条件がない場合に `getenv` し、値を `drive.d.fetch_margin` に保存します。既定値は `include/strata/core/expert_source.hpp` の `ExpertDispatch` にあります。server では初期化時の設定が server の実行中に使われます。リクエストごとの再読込はありません。プロセス起動後に環境を変更しても、すでに保存された値には反映されません。

各 verify window で、PCIe share が取得した miss のうち、使用回数が `fetch_min`（別変数 `STRATA_ADAPT_FETCH_MIN`、既定 `1.0`）以上で、適応 tier のコピー中ではない候補を使用回数の高い順に並べます。window が使わない resident expert も使用回数の低い順に選び、候補と比較します。margin 条件を通った候補は resident expert の VRAM slot にコピーされ、host residency table 上で resident となります。margin 条件で最初の候補が止まると、その後の候補比較も終了します。

設定値は起動ログで小数点以下2桁まで表示されます。margin の値自体に対する invalid-value 警告、終了処理、fallback はありません。`STRATA_ADAPT_FETCH_VERIFY` が generate で有効な場合、admission された slot の read-back 検証ログは別途出ますが、これは margin の検証ではありません。

## 根拠

- 既定値と `float` フィールド: `include/strata/core/expert_source.hpp:658-675`
- 既定の admission 条件と serve の読み取り・起動ログ: `src/program/generate.cpp:12772-12795`
- generate の有効条件、読み取り・起動ログ: `src/program/generate.cpp:20451-20473`
- 候補missの選択、最低使用回数、resident victim の選択、margin の厳密比較、slot と residency 更新: `src/core/expert_source.cpp:5013-5029,5095-5134`
- generate の verify read-back ログ: `src/program/generate.cpp:20976-20995`
- Strata の機能一覧に記載された既定の閾値と適用条件: `docs/DETAILS.md:1076`
