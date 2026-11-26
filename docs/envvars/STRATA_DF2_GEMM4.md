# `STRATA_DF2_GEMM4`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

DFlash2 drafter の Q4_0 重み GEMM で使う CUDA/HIP または SYCL のカーネル variant を選ぶ、診断・調整用の環境変数です。通常値 0 は backend ごとの自動 variant を選び、非ゼロ値は固定 variant を選ぶための値として読み取られます。CUDA/HIP では 1〜9 相当の非ゼロ値は variant 1 にまとめられ、10 以上は値を variant ID として渡します。SYCL では非ゼロ値をそのまま switch に渡します。対象は Q4_0 GEMM のカーネル選択で、DFlash2 の他の計算・生成制御を直接変更する読み取りはありません（`engine/src/kernels/cuda/dflash2.cu:1859-1861`、`engine/sycl/src/kernels/cuda/dflash2.dp.cpp:702-718`）。

DFlash2 自体は `--draft dflash2` と Q4_0 の draft pack を使う経路です（SYCL generate の説明: `engine/sycl/src/program/generate.cpp:785-788,927-929`）。CUDA/HIP 実装は Q4_0 分岐のときだけこの変数を参照し、Q8_0 は後続の別分岐です（`engine/src/kernels/cuda/dflash2.cu:1859-1908`）。

## 値と判定

両実装とも `std::getenv` の戻り値が null なら 0、それ以外は `std::atoi` に渡します。空文字も `atoi("") == 0` となり自動選択です。数値全体の妥当性検査、値域検査、clamp はありません。`atoi` は先頭の空白と符号を許し、数字の後ろの文字列を検査しないため、`" 10tail"` は 10、`"0anything"` は 0、`"true"` は 0 として扱われます。大文字小文字は文字列比較に使われません。数値として読めない接頭部も 0 になります。数値範囲外の入力に対する安全な fallback は実装されていません（`engine/src/kernels/cuda/dflash2.cu:1860-1861`、`engine/sycl/src/kernels/cuda/dflash2.dp.cpp:716-717`）。

| backend / 条件 | unset・空文字・atoi 結果 0 | 有効になる値の例 | その他の値の扱い |
|---|---|---|---|
| CUDA/HIP、Q4_0、固定 variant が未指定 | 自動選択。CUDA は 17。HIP の RDNA3/RDNA4 (Wave32) は rows ≤ 640 なら 31、それ以外は 26 | `1`、`2`、`9`、`-1` はいずれも `v4=1`。10〜45 の実装済み ID はその variant | 10 以上で実装されていない ID は switch の default kernel。`STRATA_DF2_GEMM_TC` 条件を満たす CUDA 経路ではこの変数の分岐に到達しない |
| SYCL、Q4_0、固定 variant が未指定 | 自動選択。rows ≤ 1024 は 40、それ以外は 41 | 実装済み ID: 10, 11, 12, 17, 24, 25, 28, 34, 40, 41, 42, 43 | その他の非ゼロ ID（例: 1、2、13、44、-1）は default の `gemm4_nc<1,1,2>` に進む（コメント上の ID 28） |

CUDA/HIP の自動 variant は `df2_q4_auto` で選び、通常は 17、HIP の対象 RDNA 世代だけ行数に応じて 31/26 です。SYCL の既定は 40/41 です（`engine/src/kernels/cuda/dflash2.cu:1769-1785`、`engine/sycl/src/kernels/cuda/dflash2.dp.cpp:698-700,717-731`）。

## 有効になる条件

- DFlash2 の GEMM 呼び出しで Q4_0 の重みが使われている必要があります。CUDA/HIP では `mats[0].q4` が true の分岐でのみ読み取ります。Q8_0 GEMM では `STRATA_DF2_GEMM` 側の分岐です（`engine/src/kernels/cuda/dflash2.cu:1859-1908`）。
- SYCL 実装は Q4_0 pack 専用で、Q8_0 の行列は `df2_gemm` が `df2_gemm: the SYCL drafter runs the Q4_0 pack only` を投げます（`engine/sycl/src/kernels/cuda/dflash2.dp.cpp:702-710`）。
- ベンチ用 setter `df2_gemm_variant(v)` が非ゼロ値を設定している場合、その値が環境変数より優先されます。実装のグローバル値は初期値 0 で、setter はベンチ用途と記されています（`engine/src/kernels/cuda/dflash2.cu:26,1762`、`engine/sycl/src/kernels/cuda/dflash2.dp.cpp:37,735`、宣言: `engine/include/strata/kernels/dflash2.hpp:61-66`）。通常の CLI / server 設定からこの setter を呼ぶ参照は見つかりませんでした。
- CUDA（HIP コンパイルを除く）では、`STRATA_DF2_GEMM_TC` が設定され、空文字でなく先頭文字が `0` でもなく、GPU compute capability major ≥ 8、`g_gemm_variant == 0`、`ncols >= 2`、rows ≥ 1024 かつ rows が 16 の倍数なら Tensor Core GEMM が先に実行され、この環境変数は評価されません（`engine/src/kernels/cuda/dflash2.cu:1836-1857`）。
- CUDA で `ncols > 8` の場合、先に batch Tensor Core GEMM が成立すればそこで終了します。成立しない場合は列を最大 8 ずつに分けて再帰呼び出しするため、再帰先で Q4_0 の環境変数分岐に到達することがあります（`engine/src/kernels/cuda/dflash2.cu:1801-1834`）。SYCL は `ncols` が 1〜8 の範囲外なら unsupported shape 例外です（`engine/sycl/src/kernels/cuda/dflash2.dp.cpp:702-703`）。

## 実行時の詳細

値は `df2_gemm` 内の関数ローカル `static` 初期化子で最初にその Q4_0 分岐を通った時に一度だけ読み取られます。同じプロセス内の後続 GEMM 呼び出しはキャッシュ値を使うため、初回読み取り後に環境を変更しても反映されません。CUDA/HIP と SYCL は別々の実装・別々の static 値です（`engine/src/kernels/cuda/dflash2.cu:1859-1861`、`engine/sycl/src/kernels/cuda/dflash2.dp.cpp:714-718`）。

CUDA/HIP は 10〜45 の variant ID に対して `gemm4_rows_kernel` の template 配置を起動し、ID 2 は旧 `gemm4_kernel<2>`、未知の ID は行数の 32 倍数条件で `gemm4_kernel<4>` または `<2>` に fallback します。環境変数の 1〜9 は `v4=1` となって switch default に入り、同じ基本 GEMM kernel を選びます（`engine/src/kernels/cuda/dflash2.cu:1862-1905`）。

SYCL は switch によって列挙された variant を専用 GEMM template に割り当て、それ以外は `gemm4_nc<1,1,2>` を実行します。環境変数値が不正でも警告やエラーにはせず、switch の default に進みます（`engine/sycl/src/kernels/cuda/dflash2.dp.cpp:718-732`）。

## ログと測定値

variant の選択や環境変数値を表示する専用ログはありません。CUDA/HIP の GEMM launch 後は `check("gemm4")` が CUDA エラーを調べ、失敗時は stderr に `dflash2 kernel gemm4: <CUDA error text>` を出して例外を投げます（`engine/src/kernels/cuda/dflash2.cu:29-34,1904-1905`）。Tensor Core 経路のエラー識別子は `gemm4_tc` または `gemm4_batch_tc` です（`engine/src/kernels/cuda/dflash2.cu:1814-1817,1848-1852`）。SYCL 側にはこの環境変数専用のログはありません（`engine/sycl/src/kernels/cuda/dflash2.dp.cpp:716-732`）。

この変数の値ごとの性能測定値は記載しません。CUDA ソースの近傍コメントには特定 GPU・行列サイズでのベンチ結果がありますが、環境変数の各値との対応を一般利用条件として裏付ける資料ではありません（`engine/src/kernels/cuda/dflash2.cu:1765-1768`）。

## 根拠

- `engine/src/kernels/cuda/dflash2.cu:1787-1908` — CUDA/HIP GEMM の入力制約、Q4_0 判定、Tensor Core 優先経路、`STRATA_DF2_GEMM4` 読み取りと variant dispatch。
- `engine/src/kernels/cuda/dflash2.cu:26,29-34,1762,1769-1785` — setter の初期値・用途、エラー出力、自動選択。
- `engine/sycl/src/kernels/cuda/dflash2.dp.cpp:698-735` — SYCL Q4_0 GEMM の入力制約、読み取り、既定 variant、dispatch。
- `engine/include/strata/kernels/dflash2.hpp:61-68` — variant setter と GEMM interface、Q4_0 データ形式。
- `engine/sycl/src/program/generate.cpp:785-788,925-929` — SYCL generate の DFlash2 起動条件の説明。
