# `DS4_TL_AFTER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal backend の DS4 GPU timeline 計測で、GPU timestamp を記録する dispatch の開始位置を `g_disp_count` の値で絞ります。これは診断用の記録範囲を変える設定です。計算結果や dispatch 自体を省略・変更する制御ではありません。

この名前の実参照は `metal/src/mtl_rt.mm` にある `std::getenv("DS4_TL_AFTER")` の読み取りだけです。コメントにも登場しますが、他の helper や動的な環境変数名への受け渡しはありません。`docs/envvars/000_envvers.md` の候補には載っています。

## 値と判定

値は `std::atol` で `long` に変換され、値全体の妥当性検査、fallback、clamp はありません。環境変数が未設定なら `0` です。設定された空文字や先頭が数値でない文字列も `atol` の変換結果 `0` となります。先頭の空白と符号を含む10進数の数値部分を読み、数値以降の文字は変換に使いません（例: `12tail` は `12`）。

| 値の例 | 記録開始判定への影響 |
|---|---|
| unset、空文字、`abc`、`0` | threshold は `0`。通常の非負 dispatch count で記録を許可 |
| `12`, `+12`, `12tail` | threshold は `12`。`g_disp_count >= 12` になった後の encoder が記録対象 |
| `-1` | threshold は負数。dispatch count が通常の非負範囲にある間は判定を通る |
| `LONG_MAX` を超える入力 | 実装は `atol` の変換範囲エラーを検査しないため、ここでの値や結果を Strata は規定・補正していない |

比較式は `(long) g_disp_count.load() < g_tl.after` です。`g_disp_count` は dispatch を encode した後で増加し、その後に次の encoder を作るため、値 `N` の場合、カウンタが `N` 未満の間は記録せず、`N` に達した後に作られる encoder から記録します。したがってこれは「先頭 N 個の dispatch を除く」境界です（`N=0` なら先頭から記録）。

## 有効になる条件

- コードが `STRATA_DS4_RUNTIME` 定義付きでコンパイルされている必要があります。`metal/CMakeLists.txt:158-164` ではこの定義を `ds4_rt_mm` / `ds4_rt_gpu` に付けており、`docs/DEEPSEEK_MAC.md:95` はこの runtime を `strata_ds4` 専用と説明しています。
- プロセスで `DS4_TIMELINE` が設定されている必要があります。ここは値の内容ではなく `getenv` の非 null 判定なので、空文字を含む設定値で timeline 計測を有効化します。未設定なら `g_tl.on` は立たず、`DS4_TL_AFTER` は読み取られません。
- 計測を初期化する encoder 作成が必要です。最初の `tl_make_encoder()` は timestamp counter set / sample buffer の用意後に `DS4_TL_AFTER` を読みます。timestamp counter set または初期 sample buffer を用意できない場合は stderr にそれぞれ `mtl: DS4_TIMELINE: no timestamp counter set` または `mtl: DS4_TIMELINE: no counter sample buffer` を出して計測を停止し、`DS4_TL_AFTER` の読み取りにも到達しません。
- この runtime の詳細な記録は `Context::run()` の `ds.size() == 1 && reps == 1 && !barrier_between` の経路で行われます。timeline が有効な場合、この経路では各 dispatch の後に次の encoder を作るため、threshold 判定が後続 dispatch の記録開始に反映されます。ほかの `Context::run()` 経路は `tl_make_encoder()` を経由せず、dispatch を計測しません。
- `DS4_TL_DRAFT` が設定されると `g_tl.gate` は初期化時に閉じられます。DS4 の `round()` は speculative draft の実行中だけ gate を開き、draft 呼び出し後に閉じます。そのため、この組み合わせでは threshold を満たす dispatch のうち draft 実行中のものだけを記録します。gate は `ds4_timeline_gate(int)` から開閉されます。

CLI 引数や別の設定値で `DS4_TL_AFTER` の値を上書きする処理は見つかりません。読み取り結果は `g_tl.after` に保存され、以後の dispatch ごとに環境を読み直しません。したがって実行中の環境変更は反映されません。

## 実行時の詳細

`Context` の構築時に `DS4_TIMELINE` の設定有無を調べて timeline を開始し、終了時の `atexit` レポートを登録します。最初の encoder 初期化で `DS4_TL_AFTER` を読み、各 encoder 作成時に現在の dispatch 数と比較します。対象 dispatch には開始・終了 timestamp 用の sample slot が付き、名前が記録されます。記録数が上限に達した場合や追加 sample buffer の作成に失敗した場合、以後の dispatch は記録されません。

プロセス終了時、記録が2 dispatch未満ならレポートは出ません。timestamp の resolve に失敗すると stderr に `mtl: DS4_TIMELINE: resolve failed` を出してレポートを中断します。成功時は stderr に `timeline: ...` 形式で記録数、wall / GPU busy / idle gap、kernel ごとの集計を出します。レポート側の `DS4_TL_FROM` は集計対象の index をさらに絞る別変数で、`DS4_TL_AFTER` の読み取り値とは独立しています。

## 根拠

- `metal/src/mtl_rt.mm:76-93`: DS4 runtime 配下の timeline 状態と `after` の用途。
- `metal/src/mtl_rt.mm:95-132`: counter set / sample buffer 初期化、`DS4_TL_AFTER` の `getenv`・`atol` 読み取り、threshold 判定。
- `metal/src/mtl_rt.mm:156-214`: 終了レポート、出力と resolve failure。
- `metal/src/mtl_rt.mm:217`: gate の変更関数。
- `src/dsv41/ds4_main.cpp:201-209,218-235`: `DS4_TL_DRAFT` のときに draft 実行中だけ timeline gate を開く呼び出し。
- `metal/src/mtl_rt.mm:292-300`: `DS4_TIMELINE` の設定有無による有効化と `atexit` 登録。
- `metal/src/mtl_rt.mm:902-970`: 対象 `Context::run()` 経路、dispatch 記録とカウンタ更新。
- `metal/CMakeLists.txt:152-164`, `docs/DEEPSEEK_MAC.md:95`: `STRATA_DS4_RUNTIME` のビルド対象。
