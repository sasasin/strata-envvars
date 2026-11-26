# `STRATA_BATCH_DF2_DEFER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の `--batch` スロットで DFlash2 のスロット別ドラフトを使うとき、窓に空き行がないラウンドでも各スロットのドラフトを毎回計算するかを決める。既定ではその場合の計算を遅らせ、確定行の tap をホスト側に保留する。値を `0` で始めると毎ラウンド計算する。既に空き行が割り当てられているスロットのドラフト計算には、この変数による違いはない（`engine/src/program/generate.cpp:17123-17146,17343-17374`）。

この変数は DFlash2 自体を有効化する設定ではなく、スロット別 DFlash2 が動作するときの遅延方針だけを変える。スロット別 DFlash2 は CUDA/HIP 共通 GPU エンジンに実装され、Metal ビルドでは無効化される（`engine/cmake/strata_gpu_engine.cmake:6-13`, `engine/src/program/generate.cpp:7828-7840`）。

## 値と判定

`std::getenv` の返す文字列の先頭 1 文字だけを調べる。値全体の数値変換や真偽値解析はせず、空白除去・大文字小文字変換・妥当性検査もない。未設定、空文字、先頭が `0` 以外なら defer が有効。先頭が `0` なら無効で、`0`, `00`, `0anything` はいずれも同じ扱い（`engine/src/program/generate.cpp:16803-16808`）。

| ビルド／値 | unset | defer が有効 | defer が無効 |
|---|---|---|---|
| CUDA/HIP でスロット別 DFlash2 が実行される経路 | 有効 | 空文字、`1`, `true`, `false`, ` 0`, `anything` | `0`, `00`, `0anything` |
| Metal、またはスロット別 DFlash2 が実行されない経路 | 読み取り値は同じ判定だが挙動に影響しない | 同左 | 同左 |

`false` や空白で始まる文字列も先頭が `0` ではないため defer 有効となる。評価は `generate.cpp` の `--batch` 状態を構成する処理中に一度行い、以後の環境変更は反映されない。CLI 引数や別環境変数がこの値を上書きする分岐はない（`engine/src/program/generate.cpp:16802-16808`）。

## 有効になる条件

- 実際の効果には `STRATA_HAVE_DFLASH2` を含む CUDA/HIP GPU エンジンが必要。CMake では CUDA または HIP の GPU エンジンにこの macro を定義し、Metal と SYCL のビルドは DFlash2 なしとしている（`engine/cmake/strata_gpu_engine.cmake:6-13`）。
- `batch_df2` が有効である必要がある。通常は `--draft dflash2`（自動選択ではない）、`--batch` 2 以上、`--serve` が必要。1 GPU の経路、または layer split でも slot group が 1 以下になる経路で有効になり、複数 group の pipeline では通常使われない。Metal では常に対象外。`STRATA_BATCH_DF2=0` でも無効になる。その他、DFlash2 のロード・準備に失敗した場合はスロット別ドラフトも動かない（`engine/src/program/generate.cpp:7822-7840,8266-8275,8328-8348`）。
- layer split でグループを複数にする経路や helper expert cache の条件では `batch_mtp` の適用判定で DFlash2 が止められることがある。無効化時は `strata generate: WARNING: ... is off: ...` が stderr に出る（`engine/src/program/generate.cpp:7841-7873`）。
- 値の違いが現れるのは、アクティブスロット数が窓の行数上限以上で、各スロットに余分なドラフト行が割り当たらないラウンド。余分な行があるスロットは、値にかかわらずドラフトを続ける（`engine/src/program/generate.cpp:17121-17146,17351-17368`）。

## 実行時の詳細

バッチ窓では各スロットに最低 1 行（現在の token）を割り当て、残りをアクティブスロット間でドラフト行として配る。既定の defer 有効時にスロットへドラフト行がないと、確定 tap 行を defer バッファへ集めて `draft_ready` を落とし、そのラウンドではドラフトを実行しない。後続ラウンドで空き行ができたとき、そのスロットの保留行を `catch_up` し、次 token の tap から最初のドラフトを作ってから窓を組む（`engine/src/program/generate.cpp:17127-17146,17148-17172`）。

先頭 `0` の場合は、窓にドラフト行を持たないラウンドでも確定行の tap を drafter に渡して `draft_launch` を呼ぶ。前回以前の defer 行が残っていれば先に catch-up して保留を消す。行がある場合の draft rows の上限・選別は `STRATA_BATCH_DF2_MAXX`、`STRATA_BATCH_DF2_CONF` とスロットの残り生成数・コンテキストに従う。この変数は窓の行数や slot/token の commit 判定そのものを変更する分岐ではなく、余分な行がないときのドラフト起動タイミングを変える（`engine/src/program/generate.cpp:16804-16808,17132-17145,17343-17374`）。

## ログと測定値

この変数の値だけを示す起動ログはない。遅延行から初回ドラフトを作る際の catch-up に失敗すると stderr に `strata batch: DFlash2 slot %d: catch-up failed (%s): no drafts for it this round` と出し、そのスロットはそのラウンドのドラフトを行わない。通常の窓後の defer 行収集が失敗すると stdout に `ERR batch DFlash2 slot %d: %s` を出してバッチ処理を失敗させる。非 defer 側の catch-up、tap gather、draft launch/finish の失敗も stdout の同じ `ERR batch DFlash2 slot %d: %s` 経路に入る（`engine/src/program/generate.cpp:17160-17168,17351-17371,17400-17410`）。

`docs/DETAILS.md` と `docs/BATCHING.md` にこの変数固有の測定値はなく、ソースコメントにもこの切替の性能値はないため、ここでは性能・生成結果への影響を定量化しない。

## 根拠

- `engine/src/program/generate.cpp:16802-16808` — 値の読み取り、先頭文字判定、関連する DFlash2 の draft 設定。
- `engine/src/program/generate.cpp:7822-7840,7841-7873` — スロット別 DFlash2 の適用条件と無効化ログ。
- `engine/src/program/generate.cpp:17121-17172,17343-17375` — 余剰行の配分、保留、catch-up、ドラフト起動。
- `engine/src/program/generate.cpp:17400-17410` — 起動したドラフトの完了と失敗出力。
- `engine/cmake/strata_gpu_engine.cmake:6-13` — CUDA/HIP GPU エンジンでの DFlash2 macro。
