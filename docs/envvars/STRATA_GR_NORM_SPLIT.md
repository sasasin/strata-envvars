# `STRATA_GR_NORM_SPLIT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版 fused hyper-connection read の正規化カーネルで、仕事グループをトークン単位にするか、トークンと hyper-connection stream の組ごとにするかを選びます。既定は組ごとの分割です。`STRATA_GR_NORM_SPLIT=0` にすると分割を止め、1トークンにつき1仕事グループで全 stream を処理します。

この名前を読む実装は `sycl/src/kernels/cuda/fused_gr.dp.cpp` だけです。CUDA/HIP 実装、Python サーバー、setup、同梱ツールには同名の読み取りがありません。そのため本変数の効果はこの SYCL カーネル経路に限られます。

## 値と判定

`gr_norm_split()` は `getenv()` が未設定なら有効、設定されていれば `std::atoi()` の結果が 0 以外のとき有効とします。文字列全体の検証はしません。

| 値 | 判定 |
|---|---|
| unset | 有効（既定） |
| 空文字 | 無効（`atoi` は 0） |
| `0`、`00`、`0suffix` | 無効（先頭から変換した整数が 0） |
| `1`、`1suffix`、` 1x`、`-1` | 有効（変換結果が 0 以外） |
| 数字に変換できない文字列 | 無効（`atoi` は 0） |

`atoi` は先頭の空白と符号を許し、読み取れる10進整数の後ろにある文字を無視します。読み取り結果は関数内の `static const bool` に保存されるため、最初に関数が実行された後でプロセス環境を変更しても判定は変わりません。

根拠: `sycl/src/kernels/cuda/fused_gr.dp.cpp:376-379`。

## 有効になる条件

- SYCL ビルドに含まれる fused GR カーネル経路で有効です。通常の layer 実行では、`--gr-native-mmvf` が有効で、`--no-fused-gr` が指定されず、GPU stage・layer dump・half dump・stage timing の各経路でもない場合に layer が fused GR を選びます（`sycl/src/program/generate.cpp:2844-2853`）。fused カーネル自体もモデルの `n_embd`、`hc`、`hc_lr` が対応 shape と一致することを要求します（`sycl/src/core/layer.cpp:1560-1561`; `sycl/src/kernels/cuda/fused_gr.dp.cpp:1888-1890`）。
- fused GR を使わない通常の `gr_read` 経路では、この変数は読み取られません。
- `fused_gr_read_multi()` が `STRATA_GR_V3` の条件を満たして二段の V3 読み取りを選ぶと、正規化カーネル選択より前にその経路を実行して戻るため、その呼び出しでは本変数の設定が使われません（`sycl/src/kernels/cuda/fused_gr.dp.cpp:1627-1662`）。

## 実行時の詳細

有効時は、`n_tok * HC` 個の仕事グループを起動し、各グループが1つの token/stream の二乗和、逆 RMS 係数 `rs`、正規化値 `xn` を計算します。ソースコメントは、この経路が B70 で仕事グループ数を増やし、各 stream の要素順・warp 内外の加算順をトークン単位カーネルと揃えることで、`rs` と `xn` を bitwise 同一にすると説明しています。無効時は `n_tok` 個の仕事グループを起動する `gr_norm_multi_kernel` が全 stream を処理します。切り替わるのは GR 読み取りの正規化段で、down/up 投影のカーネル設定を直接変更する環境変数ではありません。

`fused_gr_read_multi()` でこの分岐を行い、単一 token 用の `fused_gr_read()` も条件によって同関数へ委譲します。既定の down sliced/direct 設定も委譲条件に関係します（`sycl/src/kernels/cuda/fused_gr.dp.cpp:1762-1774,1892-1915`）。変数専用のログ出力や警告はありません。

資料 `docs/INTEL.md:468-477` は、SYCL の GR down 分割に続けて「GR norm per (token, stream)」を bitwise 同一の変更として記録しています。同じ行には複数変更を重ねた測定結果が載っているため、その tok/s 値を本変数単独の性能効果とはみなしません。

## 根拠

- `sycl/src/kernels/cuda/fused_gr.dp.cpp:260-321`: 1仕事グループ/トークンの正規化カーネル。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:324-379`: 1仕事グループ/(トークン, stream) のカーネルと環境値判定。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:1627-1662,1762-1774`: V3 経路の先行分岐と正規化カーネルの選択。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:1892-1915`: 単一 token read から multi read への委譲。
- `sycl/src/core/layer.cpp:1560-1561`, `sycl/src/program/generate.cpp:2844-2853`: fused GR の利用条件。
- `docs/INTEL.md:468-477`: SYCL の性能・bitwise 結果に関する資料記述。値は複数の変更を組み合わせた測定。
