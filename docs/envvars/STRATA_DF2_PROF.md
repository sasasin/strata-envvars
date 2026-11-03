# `STRATA_DF2_PROF`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal engine の DFlash2 draft 実行で、1 回だけ GPU dispatch の計測を行う診断用スイッチです。DFlash2 の通常の decode graph を実行した後、各 DFlash2 状態で round カウンターが 10 の回に dispatch 全体と kernel class ごとの時間を追加計測し、stderr に出します。draft の設定値や CLI 引数を選ぶものではありません。

## 値と判定

`Window::df2_draft()` 内で `std::getenv("STRATA_DF2_PROF") != nullptr` を判定し、`static const bool` に保持します。値の内容は parse しません。

| 環境の状態 | 判定 |
| --- | --- |
| 未設定 | 無効 |
| 設定あり（空文字を含む） | 有効 |
| `0`、`false`、その他の文字列 | 有効（文字列比較なし） |

初めて `df2_draft()` がこの判定行に到達した時点でプロセス内に cache されます。その後に環境を変更しても再評価されず、別の Window でも同じ値を使います。CLI 引数や別の環境変数による上書き・優先順位はこの読み取り箇所にはありません。

## 有効になる条件

この読み取りと計測処理は Metal engine 固有の DFlash2 実装 `metal/src/engine/dflash2.inc` にあります。DFlash2 の draft 呼び出しがなければ `df2_draft()` に到達せず、何も起きません。値が有効でも、カウンターが `d.rounds == 10` である呼び出し以外では計測しません。構造体の初期値は `rounds = 0` で、各呼び出し末尾で増えるため、この条件は各 DFlash2 状態のカウンターが 10 の呼び出し（0 始まりで数えると 11 回目）に成立します。

索引の隣接項目 `STRATA_DF2_PROFILE` は別名です。CUDA 側 `src/core/dflash2.cpp` はその別名を別の規則で読み取りますが、`STRATA_DF2_PROF` の別名や fallback ではありません。

## 実行時の詳細

通常の `cx_->run_graph(d.list[n_new])` を実行して `d.rounds` を検査した後に profiler が呼ばれます。dispatch を kernel class ごとにまとめ、各 dispatch に barrier を付けた計測リストを作ります。全 dispatch と各 class のリストをそれぞれ 7 回実行し、昇順に並べた中央の値（4 番目）を時間として使います。したがって該当 round では計測のための追加 GPU 実行が発生します。

stderr には `strata metal df2 prof: round of ...` の全体計測行と、`strata metal df2 prof: ... ms ...% ...` の class 別行が出ます。環境変数の無効値エラー、警告、終了処理はこのスイッチに対して実装されていません。計測結果は `df2_prof()` の中で出力され、draft の返却配列はその後に設定されます。

## 根拠

- `metal/src/engine/dflash2.inc:1-6` — Metal engine 固有の DFlash2 drafter とその公開経路。
- `metal/src/engine/dflash2.inc:111-115` — `rounds` の初期値。
- `metal/src/engine/dflash2.inc:740-795` — draft graph 実行後の static 環境判定、計測条件、呼び出し後の round 加算と draft 出力。
- `metal/src/engine/dflash2.inc:801-841` — dispatch の分類、7 回計測と中央値の選択、stderr の出力。
- `metal/src/engine/dflash2.inc:1084-1094` — DFlash2 の公開 draft 呼び出しから `Window::df2_draft()` への委譲。
- `src/core/dflash2.cpp:236` — 別名 `STRATA_DF2_PROFILE` の独立した CUDA 側読み取り。
