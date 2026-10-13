# `STRATA_QFUSE_HC_LOCAL`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP の fused hyper-connection（HC）複数 token 読み取りで、HC の出力 `mixed` から q8_1 画像を作る方式を選びます。既定（unset）または 0 以外なら、32列を1 block が担当する `gr_up_q32_kernel` が計算と q8_1 書き込みを行います。0 ならこの専用 kernel を選ばず、通常の `gr_up_multi_kernel` に戻します。切り替えるのは q8_1 画像の生成経路であり、q8_1 自体を有効にする設定ではありません。

## 値と判定

`src/kernels/cuda/fused_gr.cu` の `qfuse_hc_local()` は `getenv()` の値を `atoi()` で整数変換し、unset の場合だけ有効を返します。文字列全体の厳密な検査はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 無効（`atoi("")` は 0） |
| 数値として 0 になる文字列（例: `0`, `false`, `abc`, `0suffix`） | 無効 |
| 数値として 0 以外になる文字列（例: `1`, `-1`, `2`, `1suffix`） | 有効 |

`atoi()` のため、先頭の空白や符号の後にある数値接頭部が変換され、後続文字は判定されません。環境変数の値は関数内の `static const bool` に初回評価時点で保存されます。その後プロセス内で環境を変更しても、この判定は変わりません。

根拠: `src/kernels/cuda/fused_gr.cu:1025-1029`。

## 有効になる条件

設定が有効でも、次の条件がそろう場合に限って専用 kernel の選択に影響します。

- ビルド時の `STRATA_GR_FAST_BUILD` が 0 であること。ソース上これは HIP コンパイルかつ `STRATA_HIP_GFX906` ではない場合です。通常の CUDA ビルドと gfx906 向け HIP ビルドでは fast-build 分岐が優先され、この環境変数による `gr_up_q32_kernel` 選択はコンパイル対象の分岐にありません。
- `fused_gr_read_multi()` が通常の `launch_multi()` 経路まで到達すること。`STRATA_GR_V3` で有効な split が選ばれると先に戻り、gfx906 の `STRATA_GR_SPLIT=1` 経路も先に戻るため、このスイッチは使われません。
- `m.a[0].q8_mixed` が null でないこと。これは呼び出し側が q8_1 出力先を渡していることを表します。

Verifier では `STRATA_QFUSE=1` または `STRATA_QFUSE_HC` が有効で q8_1 group counter の確保に成功した場合に q8_1 出力先を設定します。`STRATA_QFUSE_HC` は HIP でのみ評価され、明示値があれば `atoi(value) != 0`、unset なら現在の GPU が gfx12 かどうかで既定値を決めます。したがって、`STRATA_QFUSE_HC_LOCAL` を単独で有効にしても q8_1 出力先は作られず、この切り替えは働きません。`STRATA_QFUSE=1` により出力先が渡る場合も、上記のビルドおよび実行経路の条件内でこの変数が選択に関与します。

根拠: `src/kernels/cuda/fused_gr.cu:28-33, 1092-1118, 1930-1962`; `src/core/verify.cpp:141-156, 789-795, 1065-1072`。

## 実行時の詳細

通常経路の `launch_multi()` は、`m.a[0].q8_mixed != nullptr && qfuse_hc_local()` の場合、`n_tok`（または `STRATA_NO_MULTI_GR` による固定上限）に応じた template instance の `gr_up_q32_kernel` を起動して、そのまま戻ります。専用 kernel は block ごとに32列を処理し、各 block が自身の列に対応する `mixed` の q8_1 group を書きます。変数が無効、または出力先が null なら、この分岐を通らず `gr_up_multi_kernel` が起動します。ソースコメントでは、後者は atomic tail を使う既存経路、前者はそれを必要としない32列 kernel と説明されています。

この変数自体についてのログ出力やエラー処理はありません。kernel 起動後の CUDA/HIP エラーは通常の `fused_gr_read_multi` のエラーチェックで stderr に出力され、プロセスを終了します。q8_1 出力が返ったかどうかは呼び出し側の `fused_gr_read_multi()` の戻り値で伝えられます。

根拠: `src/kernels/cuda/fused_gr.cu:378-381, 1025-1029, 1092-1118, 1830-1863, 1955-1962`。

## 文書との照合

`docs/DETAILS.md` と `docs/STRIX_HALO.md` に `STRATA_QFUSE_HC_LOCAL` の個別説明は見つかりませんでした。`docs/STRIX_HALO.md` には `STRATA_QFUSE` を activation q8_1 画像の producer 側生成として扱う記載がありますが、それだけから本変数の選択肢、既定値、性能効果は導けません。本調査ではソースコメントと実際の分岐だけを根拠にし、性能値は記載していません。

## 根拠

- `src/kernels/cuda/fused_gr.cu:28-33`: CUDA/HIP gfx906 とその他 HIP の fast-build 条件。
- `src/kernels/cuda/fused_gr.cu:378-381, 1025-1029, 1092-1118`: 専用 kernel、値の parse、dispatch 条件。
- `src/kernels/cuda/fused_gr.cu:1830-1863, 1930-1962`: 入力検証、q8_1 出力の存在条件、early return と通常 dispatch。
- `src/core/verify.cpp:141-156, 789-795, 1065-1072`: q8_1 counter の確保と `q8_mixed` の設定条件。
