# `STRATA_DF2_CHECK_REBUILD`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal 版 DFlash2 の serve で、会話 lineage の切り替え後に drafter の K/V ring を row log から復元したとき、復元前のリング内容と復元後の内容をバイト単位で比較する診断用スイッチです。DFlash2 の通常の復元処理を有効にする設定ではなく、比較用のリング複製を保持し、復元結果を stderr に報告します。

## 値と判定

値は parse されず、`std::getenv(...) != nullptr` だけで判定します。

| 設定状態 | 結果 |
|---|---|
| 未設定 | 比較用コピーを作らず、復元結果を比較しない |
| 空文字を含む設定済みの値 | 有効。文字列の内容にかかわらず比較用コピーを作る |

判定結果は関数内の `static const bool` に保存されます。最初に `cur_hi > 0 && !cur_hist.empty()` となる退避処理へ到達した時点で評価され、そのプロセスで以後変更しても再評価されません。CLI 引数による上書きや、別の環境変数との優先順位はありません。読み取りとコピーの条件は `metal/src/engine/dflash2.inc:877-896` です。

## 有効になる条件

- Metal エンジンに組み込まれた DFlash2 実装でのみ読み取られます。`metal/src/engine/window.cpp:3437-3438` がこの実装を取り込みます。CUDA/HIP 側にこの名前の読み取りはありません。
- serve の DFlash2 がリクエスト開始時に `begin_request()` を呼び、リング状態が stale と判定される必要があります。呼び出し元は `src/program/generate.cpp:16032-16046`、stale 判定と復元呼び出しは `metal/src/engine/dflash2.inc:1114-1137` にあります。
- 復元関数が `bound`、`fuse_h`、row log、stash 上限、`resume` の各条件を満たす必要があります。退避対象の lineage については `cur_hi > 0` かつ履歴が空でない場合にスナップショットを作ります。条件を満たさない場合は関数が早期 return するか退避されず、比較は行われません（`metal/src/engine/dflash2.inc:877-896`）。
- 退避だけでなく、再利用 prefix に一致する stash があり、比較対象の行範囲が空でない場合にリング再構築と比較まで進みます。一致する stash がない、または再構築範囲が空の場合は比較ログは出ません（`metal/src/engine/dflash2.inc:897-934`）。

この実装は `--draft dflash2` が使われたときの serve 経路に属し、通常の単発 generate では `begin_request()` を呼びません（serve の呼び出し位置: `src/program/generate.cpp:16032-16046`）。

## 実行時の詳細

有効な状態で lineage を stash に退避すると、各 layer の K ring と V ring の全バイトを `Stash::chk` に複製します。比較時は復元範囲 `[from, r_end)` の各位置について、各 layer の K/V それぞれ 4096 バイトを `memcmp` します。これは K/V ring の内容を検査するだけで、比較結果に応じて復元を取り消したり実行を失敗させたりする分岐はありません（`metal/src/engine/dflash2.inc:886-893,957-979`）。

差分があれば最大 3 件について layer、K/V 種別、position、最大絶対差と先頭値を `strata metal: rebuild check: ...` 形式で stderr に出します。その後、差分数と検査数を `strata metal: DFlash2 rebuild check: <bad> of <total> ring rows (K/V x layers x positions) differ from the original update` 形式で必ず stderr に出します。`bad` が 0 の場合も集計行は出ます。通常の serve 側には、復元行数・所要時間を示す別の `strata serve: DFlash2: ... context rows ... rebuilt ...` ログがあります（`metal/src/engine/dflash2.inc:967-978`; `src/program/generate.cpp:16037-16044`）。

比較用コピーは固定長リング全体について layer ごとに K/V を保持します。コード上の割当サイズは `DF2_RING * 1024 * 4 * 2 * d.L` bytes（`DF2_RING` は 2064）で、stash の各 lineage ごとに確保されます（`metal/src/engine/dflash2.inc:73,886-892`）。

## 根拠

- `metal/src/engine/dflash2.inc:82,885-896` — stash に保持する比較用バッファ、設定有無判定、比較用コピー。
- `metal/src/engine/dflash2.inc:877-934` — Metal DFlash2 の復元条件、lineage の選択と対象範囲。
- `metal/src/engine/dflash2.inc:957-986` — K/V ring のバイト比較、差分・集計ログ、復元後の処理。
- `metal/src/engine/dflash2.inc:1114-1137`, `src/program/generate.cpp:16032-16046` — serve リクエスト開始時の stale 判定と復元呼び出し。
- `metal/src/engine/window.cpp:3437-3438` — Metal window 実装への DFlash2 実装の取り込み。
