# `STRATA_GR_UP_ILP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL 版 fused hyper-connection read の up projection で、複数 token の dot 計算を先に行い、その後 token ごとの butterfly reduction を段階ごとに交互に進める kernel specialization を選びます。通常の specialization は token ごとに dot と butterfly reduction を続けて処理します。ILP 分岐も dot と XOR butterfly の演算順を保つ形で書かれており、コードコメントは通常版と同じ bit pattern としています（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:858-868,941-969`）。

対象は `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp` の SYCL 実装です。CUDA/HIP 共通実装や CLI オプションの読み取りは見つかりませんでした。この helper は CLI や設定値との優先順位を設けず、プロセス環境を直接読みます（同 `:1208-1210`）。

## 値と判定

`gr_up_ilp()` は `std::getenv` の戻り値が null でなく、かつ文字列の先頭 byte が文字 `'1'` の場合だけ true を返します。文字列全体の parse や数値検証はしません。比較は大文字小文字を区別し、空白も除去しません（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:1208-1210`）。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL fused GR | false | `1`、`10`、`1anything`（いずれも先頭が `1`） | 空文字、`0`、`true`、`false`、` 1`、`-1` |

空文字は環境変数自体は設定されていますが、先頭 byte が終端文字 `\0` なので false です。負値や不正な数値という概念での検査はなく、先頭文字だけで決まります。

## 有効になる条件

- SYCL 実装の `fused_gr_read_multi` で up projection が `launch_gr_up_multi` に進むこと（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3465-3493`）。`fused_gr_read` も down/norm の特定条件では 1 token を `fused_gr_read_multi` に渡しますが、通常の単独 read は別 kernel を起動します（同 `:3517-3559`）。
- `launch_gr_up_cols` が cache reuse、large-GRF、`gr_more_groups` の各経路を通らず、ILP 分岐のある通常の multi-token kernel を選ぶこと。同関数は cache reuse と large-GRF の場合に先に return し、`gr_more_groups` は別の `gr_up_multi_kernel<..., false, true>` specialization を起動します（同 `:1186-1197,1212-1237,3485-3493`）。
- `STRATA_GR_UP_COLS` が選ぶ列数は 4、8、32、64、または既定列数のいずれでもよく、ILP 分岐の template specialization は選ばれた列数 `C` で起動します。未設定・未対応値は `UPM_COLS`（16）に戻ります（同 `:853-856,1200-1206,1239-1246`）。
- `STRATA_GR_UP_ILP` が true だと、`gf_enabled()` が要求する `!gr_up_ilp()` を満たさず、Battlemage 向け private F32 経路は選ばれません。この経路は別途 `STRATA_PRIVATE_GR_F32_REG` が `atoi` で非 0、token 数 1〜4、down/norm 設定などにも依存します（同 `:2685-2689,3466-3470`）。
- 同じく true の場合、`STRATA_GR_CACHED_NORM` または `STRATA_GR_LO_REUSE` により `reuse_norm` または `reuse_lo` が true でも、再利用経路を有効にする条件の `!gr_up_ilp()` を満たさず、その条件で cache reuse は設定されません（同 `:3300-3315`）。

## 実行時の詳細

値はプロセス起動時ではなく、`gr_up_ilp()` の初回呼び出し時に関数内 `static const bool` として評価されます。呼び出しは private F32 経路の判定と cache reuse の判定にも現れるため、最初にいずれかが評価した値がプロセス終了まで保持されます。実行中に環境を変更しても再読込されません（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:1208-1210,2685-2689,3300-3306`）。

通常経路で値が true のときは `gr_up_multi_kernel<C, true>` を起動します。この kernel は各 token の dot 積をまず `accs` に計算し、次に XOR shuffle の offset `16, 8, 4, 2, 1` ごとに token の reduction を進め、最後に対応する lane の結果を使います。false のときは token ごとに dot 積を計算して `warp_sum` を完了してから次 token に進みます。どちらも続く up projection の epilogue に合流し、出力の書き込みと gate 計算を行います（同 `:941-977`）。

値は子プロセスへ転送・上書きされません。この実装内に子プロセス起動処理はありません。

## ログと測定値

この変数専用の有効・無効ログ、警告、エラー文言、終了処理はありません。確認できる効果は選択された kernel specialization です。Strata の `docs/DETAILS.md` にこの変数の測定値や説明は見つからず、ここでは性能差を記載しません（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:1232-1237,3494-3500`）。

## 根拠

- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:1208-1210` — 環境変数の唯一の実読み取りと static cache。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:941-977` — ILP / 通常 specialization の計算と後続処理。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:1212-1246,3465-3493` — specialization の選択と迂回する dispatch 経路。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2689,3300-3315` — private F32 経路・cache reuse 条件との相互作用。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3517-3559` — 単独 read と multi-token read の呼び分け。
