# `FNX_PF_HCSPLIT_LT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

NVIDIA split backend の prompt path で、2枚のカードに hyper-connection read を分割する機能（HCSPLIT）が有効な場合に、hyper-connection down GEMM 用の cublasLt アルゴリズムを実行時に校正するかを切り替える。既定では校正し、行数が 4096 と 2048 のとき unsplit 側と同じ結果になる候補を探す。校正を無効にすると `down_lt` が設定されず、後段の全カード判定で HCSPLIT は使われない。変数自体が HCSPLIT を有効にする設定ではない（`engine/src/split/src/prefill.cu:408-426, 531-534, 1090-1102, 1149-1159`）。

## 値と判定

`fnx::env_int("FNX_PF_HCSPLIT_LT", 1)` が環境から値を読み、`0` 以外なら校正を呼び出す。`env_int` は符号付き十進整数全体を `strtoll` で読み、値の範囲は `long long` 内に限る。`+` または `-` は先頭に許されるが、空白、数字以外の接尾辞、空文字、範囲外の数値は受け付けず、`runtime_error` を投げる。整数の値域に別の制限はなく、0 か非0かだけを分岐に使う（`engine/src/split/src/env.hpp:15-22, 33-40`; `engine/src/split/src/prefill.cu:1101`）。

| 条件 | unset | 有効になる値 | 校正を無効にする値 | 無効な文字列 |
|---|---|---|---|---|
| HCSPLIT の初期化に入る NVIDIA build | 既定値 `1` で校正する | `1`, `-1`, `2` など整数の非0 | `0`, `-0`, `+0` | ``, `true`, ` 1`, `1x`, `9223372036854775808` は整数全体として読めず例外 |
| HIP build、または HCSPLIT 初期化条件を満たさない場合 | この変数の読み取り箇所に到達しない | 該当なし | 該当なし | この変数を理由とする変換エラーも起きない |

## 有効になる条件

- split backend の NVIDIA build であること。読み取りと校正呼び出しは `#if !FNX_HIP` 内にある。HIP ではこの変数による校正は行わない（`engine/src/split/src/prefill.cu:1090-1102`）。
- `Engine::prefill_alloc()` が実行され、`NCARD == 2`、`FNX_PF_RING_SM=0`、`FNX_PF_OVERLAP` が非0、`FNX_PF_HCSPLIT` が非0となって `p->hcs` が true になること。これらを満たさない経路では対象変数を読まない（`engine/src/split/src/prefill.cu:854-857, 1063-1068, 1080-1094`）。
- 校正が成功しても、そのカードに候補アルゴリズムが見つからない場合や別カードで校正が成功しない場合は HCSPLIT は使われない。全カードで `p->hcs && p->down_lt` が成立したときだけ各カードの HCSPLIT を維持する（`engine/src/split/src/prefill.cu:586-610, 1149-1157`）。
- prompt の個々の pass でも、chunk 数が `FNX_PF_HCSPLIT_MIN` 未満、512行未満の chunk がある、または `FNX_PF_HCSPLIT=1` なのに校正済みアルゴリズムがない／chunk が4096行でない場合は、その pass の分割を無効にする（`engine/src/split/src/prefill.cu:1436-1444`）。
- CLI 引数による上書き箇所はない。`FNX_PF_HCSPLIT`、`FNX_PF_OVERLAP`、`FNX_PF_RING_SM` が上記の初期化条件を左右するが、対象変数は校正呼び出しだけを制御する（`engine/src/split/src/prefill.cu:1063-1102`）。

## 実行時の詳細

値はプロセス起動後、prompt 用バッファを作る `Engine::prefill_alloc()` のカードごとの初期化時に読み取られる。対象の値を static cache するコードはなく、HCSPLIT 初期化条件が成立する各カードで `env_int` が呼ばれる。後から環境を変更しても、すでに作られた Engine の校正結果や `down_lt` は更新されない（`engine/src/split/src/prefill.cu:854-864, 1090-1102`）。

既定値または非0値では `pf_lt_calibrate()` が各カードで一度走る。これは 4 MiB の workspace を作り、4096行用の cublasLt heuristic 候補（最大32件）を検査し、cublasGemmEx の4096行結果とのビット比較と、候補アルゴリズムの4096行結果・2048行の各半分とのビット比較を行う。一致候補があれば `down_lt=true` とそのアルゴリズムを保存する。0 を指定するとこの処理を飛ばすため `down_lt` は false のままとなり、全カード条件を満たさず HCSPLIT は両カードで無効化され、通常の hyper-connection read に戻る（`engine/src/split/src/prefill.cu:531-534, 535-620, 1101, 1149-1157`）。

## ログと測定値

校正を実行したカードごとに、候補の有無に応じて stderr に次のいずれかを出す（`engine/src/split/src/prefill.cu:617-619`）。

- `fnx: prompt path card %d: hyper-connection down GEMM through cublasLt with an algorithm that gives the same rows at 2048 and 4096 rows (and cublasGemmEx's at 4096)`
- `fnx: prompt path card %d: hyper-connection down GEMM has no row-count-independent algorithm: the split's results differ in the last bits from the unsplit path's`

全カードでアルゴリズムが得られなかったとき、HCSPLIT が要求されていれば `fnx: prompt path: the hyper-connection read stays on both cards (no cublasLt algorithm that gives the same rows at 2048 and 4096 rows on this card)` を出す。機能が有効な場合は `fnx: prompt path: the hyper-connection read is split between the cards (...)` を出す。対象変数が0で校正を飛ばした場合も、HCSPLIT が要求されていれば前者の fallback ログになる。この場合、文言は「アルゴリズムがない」とするものの、実際には校正を省略しており、候補の有無を確認した結果ではない。HCSPLIT の初期化条件が成立しない場合はこの判定ログも出ない（`engine/src/split/src/prefill.cu:1149-1159`）。

## 根拠

- `engine/src/split/src/env.hpp:15-22, 33-40` — 整数の全体 parse、unset 時の既定値、無効値の例外。
- `engine/src/split/src/prefill.cu:854-864, 1063-1102` — prompt 初期化、HCSPLIT 条件、対象変数の読み取り。
- `engine/src/split/src/prefill.cu:531-620` — 校正方法、候補判定、カードごとのログ。
- `engine/src/split/src/prefill.cu:1149-1159, 1436-1444` — 全カードでの fallback と pass ごとの適用条件。
