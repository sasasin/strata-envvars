# `FNX_PF_HCSPLIT_PIECES`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

2 枚の NVIDIA GPU で split engine の prompt path が hyper-connection split を使うとき、カード間で行データを交換する分割数を指定する。既定は 4 で、値は `Pf::hg_pieces` に保存され、hyper-connection の `mixed` 行と draft 用の残差 `R` の両方の交換に使われる。各交換を指定数の連続した piece に分けて送受信する設定であり、行列演算そのものの設定ではない（`engine/src/split/src/prefill.cu:403-407, 427, 1095-1099, 1559-1563, 1581-1584`）。

## 値と判定

値は `fnx::env_int` が環境から取得し、符号付き十進整数として文字列全体を `std::strtoll` で変換する。未設定なら呼び出し側の既定値 `4`。設定された値は `1` から `8` までを受理し、それ以外は例外になる（`engine/src/split/src/env.hpp:15-21, 33-40`、`engine/src/split/src/prefill.cu:1095-1098`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `p->hcs` が true の場合 | `4` | `1`〜`8`。例: `1`, `4`, `8`, `+4`, `04` | 空文字、`true`、` 4`、`4 `、`1x`、`1.0` は整数全体として解析できず例外。`0`、`-1`、`9`、`+0` は整数として解析後に範囲外で例外 |
| `p->hcs` が false の場合 | 読み取らない | 該当なし | 値は検証されず、この変数による例外も発生しない |

`parse_whole` は先頭が符号または数字であることを確認し、変換後に文字列末尾まで消費されたことと `long long` のオーバーフローがないことを確認する。したがって空白、大文字小文字の扱い、`true` / `false` 表記による真偽値変換はなく、後続文字の無視もない。整数として解釈できない値では `FNX_PF_HCSPLIT_PIECES: '<値>' is not a whole number`、整数だが範囲外なら `FNX_PF_HCSPLIT_PIECES: 1 to 8, got <整数>` が例外メッセージになる（`engine/src/split/src/env.hpp:15-21, 33-39`、`engine/src/split/src/prefill.cu:1096-1098`）。

## 有効になる条件

- この読み取り箇所は `#if !FNX_HIP` 内にあり、HIP build ではこの変数を読み取らない。対象は split engine の CUDA build（`engine/src/split/src/prefill.cu:1090-1097`、build の CUDA/HIP 選択は `engine/src/split/CMakeLists.txt:80-91`）。
- `NCARD == 2`、`FNX_PF_OVERLAP` が 0 以外、`FNX_PF_RING_SM` が 0、`FNX_PF_HCSPLIT` が 0 以外であることが、`p->hcs` の初期条件。これらの値の既定値はそれぞれ overlap `1`、ring SM `0`、HCSPLIT `2`（初期判定側の HCSPLIT 既定値は `1`）である（`engine/src/split/src/prefill.cu:967, 1063-1068, 1080, 1090-1094`）。
- 両カードで `p->hcs` が有効で、hyper-connection down GEMM の校正が両方成功する必要がある。条件を満たさない場合は HCS split を止め、stderr に `fnx: prompt path: the hyper-connection read stays on both cards (no cublasLt algorithm that gives the same rows at 2048 and 4096 rows on this card)` を出す。`FNX_PF_HCSPLIT_LT=0` などにより校正を行わない場合も `down_lt` が立たないため、この fallback 条件に入る（`engine/src/split/src/prefill.cu:1099-1102, 1149-1159`）。piece 数は校正より前に読み取られるので、この fallback に至る場合でも値の解析・範囲検査は先に行われる。
- 実際の各 pass で split 読み取りを行うには、既定では少なくとも 3 chunk あり、各 chunk が 512 行以上であることも必要。chunk 数のしきい値は `FNX_PF_HCSPLIT_MIN` で変更され、pass に入る chunk 数には `FNX_PF_PASS` も関係する。`FNX_PF_HCSPLIT=1` の場合はさらに校正済みで各 chunk がちょうど 4096 行でなければ、その pass の split 読み取りを行わない（`engine/src/split/src/prefill.cu:1069, 1341-1347, 1436-1444`）。これらは piece 数の値を変更せず、その pass で split を使うかを決める。
- CLI 引数や設定ファイルによる上書きはこの読み取り経路にはない。環境値が直接 helper に渡され、`Pf` に保存される（`engine/src/split/src/prefill.cu:1095-1099`）。

## 実行時の詳細

`Engine` の初期化中に `prefill_alloc()` が prompt path の `Pf` をカードごとに作る際、上記の条件が成立したカードで `env_int("FNX_PF_HCSPLIT_PIECES", 4)` を評価する。`env_int` 自体は値を static cache しないが、この時点で読み取った値を `p->hg_pieces` に保存し、後続の prompt 処理では保存値を使う。従って通常の同一 Engine の実行中に環境変数を変更しても保存済みの piece 数は変わらず、Engine を作り直すときに再評価される（`engine/src/split/src/engine.cu:318`、`engine/src/split/src/prefill.cu:854-865, 1095-1099`）。

`pf_swap_rows` は各 GPU が担当する行範囲を `pieces` 個に整数分割し、各 piece の送信後にフラグを書き、相手から届くまで待って受信する。`hg_pieces` は `mixed` または half 型にした `mixed` の交換に使われ、同じ値が pass 終端の残差 `R` の交換にも渡される。これは転送区間の分け方を変えるが、このソース位置から生成結果への数値差や性能差は断定できない（`engine/src/split/src/prefill.cu:673-699, 1559-1563, 1579-1584`）。

## ログと測定値

この変数の有効値を示す専用ログはない。Strata の `docs/DETAILS.md` を含む `docs/` 内にこの変数名の説明は見当たらず、ソースの読み取り・分岐を照合できる説明資料は確認できなかった。値のパース・範囲違反は例外として上記メッセージを持つ。例えば `fnx_run` は stderr に `fnx_run: <例外メッセージ>` を出して終了コード `1` を返す。`sfnx` の Engine 作成時は `ERR <例外メッセージ>` を通知し、stderr に `sfnx: failed: <例外メッセージ>` を出して終了コード `1` で終了する（`engine/src/split/tools/fnx_run.cpp:1364-1373`、`engine/src/split/tools/sfnx.cpp:1094-1103, 1123-1135`）。

## 根拠

- 数値の取得・変換とエラー: `engine/src/split/src/env.hpp:15-21, 33-40`
- 初期化条件、範囲検査、保存、校正後の fallback: `engine/src/split/src/prefill.cu:1063-1069, 1080-1103, 1149-1159`
- piece 単位の行交換と利用箇所: `engine/src/split/src/prefill.cu:673-699, 1559-1563, 1579-1584`
- pass ごとの適用条件: `engine/src/split/src/prefill.cu:1436-1449`
- 初期化と実行ファイルでの例外観測: `engine/src/split/src/engine.cu:318`、`engine/src/split/tools/fnx_run.cpp:1364-1373`、`engine/src/split/tools/sfnx.cpp:1094-1103, 1123-1135`
