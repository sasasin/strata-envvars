# `STRATA_GR_UP75`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA の multi-token hyper-connection read における up projection の kernel 選択を制御する。条件を満たすと通常の `gr_up_multi_kernel` の代わりに `gr_up75_kernel` を起動し、up の重み行のロードを先行させる。カーネルコメントは両者の各行の和・reduction・epilogue が同じ順序で、出力 bit も同じとしている（`engine/src/kernels/cuda/fused_gr.cu:567-578`）。

## 値と判定

`up75_on()` は環境変数を `std::getenv` で読み、設定されていれば `std::atoi(v) != 0` を ON とする。文字列全体の妥当性検査はなく、`atoi` が読む数値接頭部の結果で決まる。したがって未設定は自動判定、空文字・`0`・`false`・`true`・`0anything` は OFF、`1`・`-1`・`2`・`1anything` は ON となる。先頭空白や符号は `atoi` の変換規則に従い、大文字小文字の比較はしない。数値として表現範囲外の文字列の結果はこの実装から保証できない（`engine/src/kernels/cuda/fused_gr.cu:1560-1566`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA、`LR == 320`、通常の multi-token read | GPU ごとの既定判定。Turing (sm_75) は `STRATA_SM75_PERF` が非 0 のとき、sm_120 は `STRATA_SM120_PERF` が unset または非 0 のとき ON。それ以外は OFF。sm_121 (GB10) はこのスイッチの GPU 既定が OFF | `atoi` の結果が非 0（例: `1`, `-1`, `1abc`） | `atoi` の結果が 0（例: 空文字, `0`, `true`, `0abc`） |
| `LR != 320`、HIP build、または up75 分岐に到達しない read | カーネル選択を変えない | なし | なし |

## 有効になる条件

- CUDA build であり、`up75_on()` の先頭条件 `LR == 320` を満たす必要がある。`LR` が異なる場合は環境変数を読む前に false を返す。HIP build も環境変数を読む前に false を返す（`engine/src/kernels/cuda/fused_gr.cu:1560-1565`）。
- `launch_multi()` で `n_tok >= 3` が必要。1–2 token では `up75_on()` を呼ばず、`gr_up_multi_kernel` を使う（`engine/src/kernels/cuda/fused_gr.cu:1911-1930`）。
- multi-token read が通常の `launch_multi()` 経路まで進む必要がある。Q8 down/up のときは `launch_q8()` から戻り、RDNA 経路、`STRATA_GR_V3` が有効な経路、Q8 mixed 出力を作る経路も通常の up75 分岐を通らない（`engine/src/kernels/cuda/fused_gr.cu:4286-4302, 4304-4398, 1882-1911`）。
- unset 時の sm_75 既定は `STRATA_SM75_PERF` に依存し、sm_75 以外では適用されない。sm_120 既定は `STRATA_SM120_PERF` に依存する。sm_121 は `kGb10GrUp75 == false` なので、この直接判定による既定 ON にはならない（`engine/include/strata/core/sm75_series.hpp:22-37`; `engine/include/strata/core/sm120_series.hpp:60-81, 83-97`; `engine/src/kernels/cuda/fused_gr.cu:1567-1577`）。
- CUDA engine は、見えている全 GPU の compute capability が同じ場合に起動時 `apply_nv_defaults()` を呼ぶ。そこで未設定の変数だけを世代別テーブル値で埋めるため、ユーザーが空文字や無効値を含め何か設定していればその値が優先される。sm_86 は `STRATA_SM86_PERF` が先頭文字 `'0'` でない場合、sm_89 は `STRATA_SM89_PERF` が先頭文字 `'0'` でなく `STRATA_DEFAULTS=026` でない場合、sm_60 は `STRATA_SM60_PERF` が先頭文字 `'0'` でない場合に、テーブルがこの変数を `1` に設定する。sm_120 の既定はテーブルではなく上記 GPU 判定から来る。混在 compute capability の複数 GPU ではこの世代別既定値適用をスキップする（`engine/src/program/generate.cpp:4421-4449, 4450-4469`; `engine/src/core/nv_defaults.cpp:41-42, 55, 75-87, 104-107, 164-175, 222-234`; `engine/src/kernels/cuda/fused_gr.cu:1567-1577`）。
- `STRATA_QFUSE=1` などで q8 mixed 出力先が渡される read は、実際には `q8_mixed != nullptr` の先行分岐が選ばれる場合があり、up75 kernel は実行されない。判定は `STRATA_GR_UP75` だけでなく read のデータ状態にも依存する（`engine/src/kernels/cuda/fused_gr.cu:4272-4282, 1882-1899`）。

## 実行時の詳細

`up75_on()` は `LR` の確認後、HIP ではない場合に関数内 static 変数へ環境値を一度だけ保存する。したがって最初の評価後にプロセス環境を変えても、この値の判定には反映されない。unset のときだけデバイス番号ごとの static cache を使い、CUDA device 属性から compute capability を取得して sm_75 / sm_120 系の既定判定を保存する。device 取得失敗または番号が 0–63 の範囲外なら OFF になる（`engine/src/kernels/cuda/fused_gr.cu:1560-1578`）。

選択時は `gr_up75_kernel` を token 数ごとの template instance で起動し、それ以外は対応する `gr_up_multi_kernel` を起動する。`no_multi_gr` の場合も 3 token 以上なら up75 判定は行われるが、template の token 数には `kFusedGrMaxT` が使われる（`engine/src/kernels/cuda/fused_gr.cu:1816-1820, 1911-1930`）。

起動時の世代別既定値設定は、未設定の環境変数だけに `setenv(..., 0)`（Windows は `_putenv_s`）で値を書き込む。プロセス内での設定であり、CLI 引数による別の上書き箇所は見つからない（`engine/src/core/nv_defaults.cpp:222-234`; `engine/src/program/generate.cpp:4421-4449`）。

## ログと測定値

世代別既定値が何か設定された場合、Strata は stderr に `strata: ... speed switches on by default ...` の行を出し、設定した switch 名を列挙する。既に利用者が設定した `STRATA_GR_UP75` は既定値適用の列挙には加えない。`up75_on()` 自体には選択理由や ON/OFF のログはない（`engine/src/core/nv_defaults.cpp:227-255`）。

カーネルソースのコメントには、RTX 2080 Ti 上の `fused_gr_bench` cold 測定で、stamp 込み up が T=3 で 27.3→24.6 µs、T=4 で 33.2→28.7 µs、T=6 で 46.6→36.6 µs と記載されている。コメントには OS、モデル、量子化、測定回数の記載がないため、この値を一般的な性能差とは扱えない（`engine/src/kernels/cuda/fused_gr.cu:1558-1559`）。

`docs/DETAILS.md` の GPU 世代別一覧も sm_86、sm_60、sm_120 にこのスイッチを列挙している。現行ソースでは sm_86 / sm_60 は `nv_default_env()` の起動時テーブル、sm_120 は `up75_on()` のデバイス既定判定で実現している。ソースのテーブルには同じ形式で sm_89 も含まれる（`docs/DETAILS.md:1478-1489`; `engine/src/core/nv_defaults.cpp:41-42, 55, 75-87, 164-175`; `engine/src/kernels/cuda/fused_gr.cu:1567-1577`）。

選択された up kernel の launch error は通常の `fused_gr_read_multi` エラー経路で stderr に `fused_gr_read_multi: <CUDA error>` を出し `exit(1)` する。環境変数固有の警告・エラー経路はない（`engine/src/kernels/cuda/fused_gr.cu:4424-4431`）。

## 根拠

- `engine/src/kernels/cuda/fused_gr.cu:1560-1578` — 値の読み取り、GPU 判定、cache、fallback。
- `engine/src/kernels/cuda/fused_gr.cu:567-578, 1911-1930` — kernel の選択と実行条件。
- `engine/src/kernels/cuda/fused_gr.cu:4286-4302, 4304-4398` — 通常 launch 前に戻る代替 read 経路。
- `engine/src/core/nv_defaults.cpp:41-42, 55, 75-87, 104-107, 164-175, 222-255` — GPU 世代別の既定値、設定優先、ログ。
- `engine/src/program/generate.cpp:4421-4449, 4450-4469` — 起動時の既定値適用条件と混在 GPU 経路。
- `engine/include/strata/core/sm75_series.hpp:22-37`; `engine/include/strata/core/sm120_series.hpp:60-81, 83-97` — unset 時の世代別判定。
