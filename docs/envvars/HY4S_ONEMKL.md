# `HY4S_ONEMKL`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`HY4S_USE_ONEMKL` を付けてビルドした SYCL Hy4-Flash エンジンで、S_K 重みを FP16 に展開して oneMKL の GEMM を呼ぶ経路を有効／無効にする。変数が未設定なら有効、値の先頭文字が `0` なら無効。無効時や oneMKL 経路の適用条件を満たさないときは、後続の XMX または SIMT GEMM、さらに `linear_auto` の行列ベクトル経路へ進む（`engine/src/hy4flash/sycl/sy_gemm_xmx.h:856-866,889-905,943-985`）。

対象の処理は `linear_auto` からモデル重みの線形演算に使われる。SYCL グラフの線形層と Engram 線形層が同関数を呼び、出力ヘッドや DFly2 の一部も同関数を使う（`engine/src/hy4flash/sycl/sy_graph.h:476-480,817-825,1448-1469`; `engine/src/hy4flash/sycl/sy_dfly2.h:650-656,669-687,760-779`）。

## 値と判定

`HY4S_USE_ONEMKL` 定義時にだけ `std::getenv("HY4S_ONEMKL")` を行う。値全体の parse や空白除去、大文字小文字変換はせず、設定値の1文字目だけを `e[0] == '0'` で比較する（`engine/src/hy4flash/sycl/sy_gemm_xmx.h:856-866`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `HY4S_USE_ONEMKL` 定義あり | 有効 | 空文字、`1`、`true`、`false`、` 0` など先頭が文字 `0` でない値 | `0`、`0anything`、`00` など先頭が文字 `0` の値 |
| `HY4S_USE_ONEMKL` 定義なし | 無効（環境変数を読まない） | なし | 常に無効 |

空文字は unset ではなく設定済み値だが、空文字列に対する `e[0]` は終端文字なので `0` ではなく、機能フラグは有効になる。`false` も先頭が `0` ではないため有効。` 0` は先頭が空白なので有効、`0anything` は先頭が `0` なので無効である。後続文字や値の妥当性は検査しない（同上）。

`engine/src/hy4flash/sycl/build_hy4_sycl.sh:45-50,62-68` は、`MKLROOT` が空でなく `$MKLROOT/include/oneapi/mkl/blas.hpp` が存在するとき `-DHY4S_USE_ONEMKL` を付けてリンクする。このビルド条件を満たさないバイナリでは、環境変数を設定しても有効化できない。

## 有効になる条件

- `HY4S_USE_ONEMKL` 付きでビルドされていること。提示されたビルドスクリプトでは上記の `MKLROOT` と oneMKL ヘッダーの条件で定義される（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:45-50`）。
- 設定値が unset、空文字、または先頭文字が `0` 以外であること（`engine/src/hy4flash/sycl/sy_gemm_xmx.h:856-866`）。
- 対象呼び出しで `M >= 32`、`N` が64の倍数、`K` が256の倍数であること。また `HY4S_XMX_I8` を `atoi` した結果が0であること。`HY4S_XMX_I8` の未設定時は0、設定時は `atoi` の結果となる（`engine/src/hy4flash/sycl/sy_gemm_xmx.h:847-853,889-890`）。
- 通常レイアウトは `FMT_S2`～`FMT_S8` が対象。RP レイアウトでは `FMT_S4`、`FMT_S5`、`FMT_S8` のみが対象。その他の形式は oneMKL 関数が false を返す（`engine/src/hy4flash/sycl/sy_gemm_xmx.h:892-906`）。
- dequant scratch の有効容量から算出した `n_step` が正であること。容量不足で0以下なら oneMKL 経路を使わず呼び出し元の fallback に戻る（`engine/src/hy4flash/sycl/sy_gemm_xmx.h:870-886`）。
- `gemm_onemkl` 自体には GPU 世代や `dev_caps()` による追加 gate はない。Strata 側で確認できる適用境界は上記 build、形状、形式、scratch、`HY4S_XMX_I8` の条件である（`engine/src/hy4flash/sycl/sy_gemm_xmx.h:889-905`）。

値を切り替える CLI 引数や、別の設定値による優先上書きはこの経路にはない。`HY4S_XMX_I8` は oneMKL 経路の適用を止める条件として作用する（`engine/src/hy4flash/sycl/sy_gemm_xmx.h:889-890`）。

## 実行時の詳細

`onemkl_enabled()` は関数内 `static const bool` に初回評価結果を保存する。ビルドマクロがある場合、最初の呼び出し時に環境を読み、同じプロセスで後から環境を変えても反映しない。マクロがない場合は `false` を返し、環境を読み取らない（`engine/src/hy4flash/sycl/sy_gemm_xmx.h:856-866`）。通常の非 serve `strata-hy4-sycl` 実行では GPU 情報のログ引数で `onemkl_enabled()` を呼ぶ（`engine/src/hy4flash/sycl/sy_main.cpp:255-260`）。`--serve` は先に `hy4s_serve_main` へ分岐し、そこで同じ `Runner` を作るため線形経路から設定が使われるが、serve 側の GPU ログには `onemkl=` 表示がない（`engine/src/hy4flash/sycl/sy_main.cpp:248-249`; `engine/src/hy4flash/sycl/sy_serve.h:236-267`）。

`gemm_onemkl` は適用条件を確認し、対象フォーマットを選んで `gemm_onemkl_fmt` に渡す。各出力列ブロックについて S_K の重みを FP16 scratch に dequantize し、行列積 `X × buf^T` を oneMKL の row-major GEMM に渡す。`n_step` は `min(N, scratch容量/K)` をもとにし、64以上なら64の倍数へ切り下げて列方向に分割する。scratch が足りない場合は false を返す（`engine/src/hy4flash/sycl/sy_gemm_xmx.h:870-886`）。通常の Runner は 32 MiB scratch を確保し登録する（`engine/src/hy4flash/sycl/sy_graph.h:578-583`）。

oneMKL 関数が false を返した場合、`linear_auto` は条件が合えば XMX/SIMT GEMM を試し、それ以外の行を `linear_h` または RP 用 `gemv_rp` で処理する。RP の未対応形式で `gemv_rp` も失敗した場合は `linear_auto: rp fmt %d unsupported` を stderr に出し `abort()` する（`engine/src/hy4flash/sycl/sy_gemm_xmx.h:943-985`）。SYCL 例外がメイン処理まで伝播した場合は `SYCL exception: %s` を stderr に出して終了コード4で返す（`engine/src/hy4flash/sycl/sy_main.cpp:612-615`）。

## ログと測定値

非 serve 実行では GPU 初期化後に `[gpu] ... onemkl=%d` を stderr に出す。この値はビルドマクロと環境変数から決まる有効フラグであり、寸法・形式などの条件も通過して個々の GEMM が実際に oneMKL 経路を使ったことまでは示さない。serve 実行の GPU ログにはこの表示がない（`engine/src/hy4flash/sycl/sy_main.cpp:248-260`; `engine/src/hy4flash/sycl/sy_serve.h:236-241`; `engine/src/hy4flash/sycl/sy_gemm_xmx.h:889-905`）。

この変数による速度や出力一致の測定値は記載しない。コードコメントにある性能・品質の説明は測定条件を伴う根拠として扱わず、`docs/DETAILS.md` にもこの変数の適用条件に結び付いた測定値は確認できなかった。

## 根拠

- `engine/src/hy4flash/sycl/sy_gemm_xmx.h:847-866` — `HY4S_XMX_I8` と `HY4S_ONEMKL` の読み取り、値の判定、ビルドマクロ分岐。
- `engine/src/hy4flash/sycl/sy_gemm_xmx.h:868-908,943-985` — oneMKL の寸法・形式条件、scratch 処理、GEMM と fallback。
- `engine/src/hy4flash/sycl/build_hy4_sycl.sh:45-50,62-68` — oneMKL build macro の付与条件。
- `engine/src/hy4flash/sycl/sy_graph.h:476-480,578-583,817-825,1448-1469`; `engine/src/hy4flash/sycl/sy_dfly2.h:650-656,669-687,760-779` — モデル計算からの線形関数呼び出し。
- `engine/src/hy4flash/sycl/sy_main.cpp:248-260,612-615`; `engine/src/hy4flash/sycl/sy_serve.h:236-267` — 起動時ログ、serve 分岐、SYCL 例外経路。
