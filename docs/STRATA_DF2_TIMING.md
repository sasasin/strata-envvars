# `STRATA_DF2_TIMING`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

DFlash2 drafter の各 draft round について、GPU 上で処理が走った時間を CUDA/HIP event で計測し、`ms_gpu` に累積します。DFlash2 の処理内容や draft token の選び方を切り替える設定ではなく、GPU 時間の診断用です。

この機能は DFlash2 対応ビルドで、CLI の `--draft dflash2` が実際に利用されるときに関係します。DFlash2 は CUDA/HIP ビルドに含まれ、Metal/SYCL ビルドには含まれません。

## 値と判定

読み取り時に `getenv("STRATA_DF2_TIMING")` が返す文字列の先頭 1 文字だけを検査します。

| 値 | timing 計測 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭が `1`（例: `1`, `10`, `1abc`） | 有効 |
| その他（例: `0`, `true`, `01`） | 無効 |

数値としての parse、文字列全体の比較、大文字小文字変換はありません。`timing_` の初期値は `false` です。`load()` の実行時に値を読み、以後の環境変数の変更は既存の drafter に反映されません。

## 有効になる条件

DFlash2 は `--draft dflash2` を指定しただけでは必ず使われるわけではありません。少なくとも `--mtp` の fallback と `--spec 2` 以上が必要で、native pack を使う単一 GPU の CLI 実行であること、`--draft-model PACK` が指定されることが必要です。`--serve`、`--batch`、layer split の経路は対象外です。モデルの load/bind、Verifier の tap 利用、graph 準備に失敗した場合も DFlash2 は無効になり、MTP が fallback になります。

これらの条件を満たさない経路では、環境変数を有効にしてもこの計測は行われません。環境変数を未設定にした場合でも DFlash2 自体は使えます。

## 実行時の詳細

`Dflash2Drafter::load()` は DFlash2 の stream と通常の event を作成した後に環境変数を読みます。先頭文字が `1` なら `timing_` を有効にし、GPU event `ev_a_` と `ev_b_` を作成します。event 作成の戻り値はこの箇所では検査しません。

各 `draft()` は GPU stream に処理を投入する直前に `ev_a_` を記録し、graph launch（または `STRATA_DF2_PROFILE=1` による段階別実行）の後に `ev_b_` を記録します。stream の同期後に `cudaEventElapsedTime()` が成功すれば、その区間の GPU 時間を `ms_gpu` に加算します。draft がエラーで終了した場合、その round の時間は加算されません。CPU 側の経過時間 `ms_draft` は別に毎回累積されます。

生成処理の最後に、DFlash2 が実際に使われて成功した round が1回以上あれば stdout に `dflash2 ... ms/round drafting (..., GPU ...), ... MiB of VRAM` を表示します。この行自体は `STRATA_DF2_TIMING` の設定有無で出し分けられず、無効時の GPU 欄は初期値から `0.000` です。`STRATA_DF2_PROFILE` は別の診断設定で、段階別 event を記録するため通常の graph launch を使わない経路にします。両方を有効にした場合も `STRATA_DF2_TIMING` の event はその実行区間を囲みます。

## 根拠

- `CMakeLists.txt:333-340` — DFlash2 を含む `strata_core` は CUDA または HIP が有効なビルドで構成される。
- `src/core/dflash2.cpp:122-124,212-224` — `load()` 内で環境変数を読み、先頭文字 `1` のときだけ timing を有効化する。
- `include/strata/core/dflash2.hpp:72-73,134-138` — `ms_gpu`、round 数、event と `timing_` の初期状態。
- `src/core/dflash2.cpp:504-550` — draft の GPU event 記録、同期、経過時間の累積、および CPU 時間の累積。
- `src/program/generate.cpp:5474-5518,16148-16165` — DFlash2 の CLI 適用条件、fallback、bind/prepare。
- `src/program/generate.cpp:16831-16839` — round がある場合の stdout 統計行。
- `src/core/dflash2.cpp:218-223,524-546` — `STRATA_DF2_PROFILE` との実行経路の相互作用。

`docs/DETAILS.md` と `tools/dflash2/README.md` も確認しました。前者にこの環境変数の説明はなく、後者は冒頭で研究用 tooling と記す DFlash2 実験資料で、本番の `STRATA_DF2_TIMING` の値判定や出力については説明していません。したがって性能値は記載していません。
