# `DS4_TL_FROM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal の DeepSeek V4.1 (`strata_ds4`) 実行経路で `DS4_TIMELINE` による dispatch 計測が有効な場合、終了時の timeline 集計をどの記録 index から始めるかを指定します。dispatch の記録や実行自体を開始・停止する設定ではなく、既に記録されたサンプルの集計範囲を切ります。

## 値と判定

`tl_report()` は終了時に環境変数を読み、`std::atoll()` で整数変換した結果を `size_t` にキャストします。未設定なら `0` です。空文字列や数字で始まらない文字列は `atoll` の変換結果が `0` になり、先頭の空白や符号は整数変換で扱われ、数字の後ろの文字列は値の判定に使われません（例: `12tail` は 12）。文字列全体の妥当性検査、エラー報告、範囲 clamp はありません。

| 値 | 集計開始 index |
|---|---:|
| 未設定、空文字、数値に変換できない文字列 | 0 |
| 非負の整数文字列 | その整数 |
| 負の整数文字列 | 負の結果を `size_t` にキャストした値（通常は大きな unsigned 値となり、記録件数を超える） |

値はプロセス終了時の `tl_report()` で読み取られます。したがって、計測の初期化後に環境が変更された場合も、その時点の値が集計に使われます。CLI 引数や別設定との優先順位はなく、この変数は終了時レポートの集計開始位置だけに使われます。

## 有効になる条件

- macOS の Metal backend で、`STRATA_DS4_RUNTIME` を付けてビルドされた DeepSeek V4.1 実行ファイル `strata_ds4` が対象です。CMake は `metal/src/mtl_rt.mm` の DeepSeek 用 object にこの macro を定義します。
- `DS4_TIMELINE` が `Context` 作成時に設定されている必要があります。値の内容は検査せず、空文字を含め、環境変数が存在すれば timeline を有効化します。
- `DS4_TL_DRAFT` も設定されている場合、DeepSeek の speculative `round()` が draft を実行している間だけ記録 gate を開閉します。このとき `DS4_TL_FROM` は gate が開いて記録されたサンプルの index に対して働きます。
- 計測サンプルが少なくとも 2 dispatch 分記録されていない場合、終了時レポートはそこで終了し、`DS4_TL_FROM` の集計効果は現れません。
- 計測対象は単一 dispatch・1 repetition・barrier-between 無効の `Context::run()` の deferred 経路です。`DS4_TL_FROM` はこの経路を有効にせず、他の `run()` 経路や一般の CUDA/HIP 実行の動作を変えません。

## 実行時の詳細

`DS4_TIMELINE` が設定されると `Context` 初期化時に計測を有効化し、終了時に `tl_report()` を呼ぶ `atexit` handler を登録します。timestamp counter set または counter sample buffer を作れない場合は、`mtl: DS4_TIMELINE: no timestamp counter set` または `mtl: DS4_TIMELINE: no counter sample buffer` を stderr に出し、計測を無効にします。計測された dispatch ごとに timestamp と kernel 名を記録し、終了時に `DS4_TL_FROM` を読みます。

開始 index は dispatch 全体の通し番号ではなく、timeline に記録されたサンプル配列 `g_tl.names` の index です。`DS4_TL_AFTER` は別設定で、記録を始める dispatch 通し番号を制御します。`DS4_TL_FROM` の値が記録件数以上なら、サンプルの集計は行われず、レポートの集計値は 0 件・0 時間になります。負値の unsigned cast も通常この範囲外となります。集計件数が 2 未満でレポートが省略される場合を除き、開始 index による警告やエラーはありません。

集計可能なデータがある場合、stderr に `timeline: ...` の概要、overlap 集計、kernel ごとの busy/gap 表を出します。counter range の resolve が失敗した場合は `mtl: DS4_TIMELINE: resolve failed` を出して集計を中断します。`DS4_TL_FROM` 自体による終了コード変更や失敗経路はありません。

## 根拠

- `metal/src/mtl_rt.mm:78-80` — timeline の目的と `DS4_TL_FROM` の位置づけ。
- `metal/src/mtl_rt.mm:95-153` — timeline encoder の作成、counter 初期化とサンプル記録条件。
- `metal/src/mtl_rt.mm:156-176` — 終了時集計と `DS4_TL_FROM` の読み取り・変換。
- `metal/src/mtl_rt.mm:182-212` — 開始 index からの集計と stderr 出力。
- `metal/src/mtl_rt.mm:292-300` — `DS4_TIMELINE` による有効化と `atexit` handler 登録。
- `metal/src/mtl_rt.mm:902-929` — 計測対象となる deferred dispatch 経路。
- `src/dsv41/ds4_main.cpp:204-208,223-235` — `DS4_TL_DRAFT` による draft 中の記録 gate。
- `metal/CMakeLists.txt:152-165` — DeepSeek Metal runtime object の `STRATA_DS4_RUNTIME` 定義と `strata_ds4` への組み込み。
