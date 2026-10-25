# `STRATA_GFX1151_EXP8`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP で動作する Strix Halo（AMD `gfx1151`）の native grouped expert kernel で、exp mode 8 を自動選択するかを制御します。mode 8 は gate/up の積和、SwiGLU、Q8_1 量子化を一つの kernel launch にまとめる経路です。既定では gfx1151 に対してこの mode を選びます。`STRATA_GFX1151_EXP8=0` はこの自動選択を止め、既定の exp mode 0（CUDA layout）に戻します。

この変数は `src/kernels/cuda/iq_kernels.cu` の `gfx1151_exp8()` だけで直接読み取られます。同関数は `__HIPCC__` かつ `STRATA_HIP_GFX906` ではないビルドでのみ実装が有効です。CUDA ビルドと gfx906 用 HIP ビルドでは常に false を返します。

## 値と判定

文字列全体や数値としての妥当性は検査せず、値の先頭文字だけを見ます。空文字は設定済みですが先頭文字が `\0` なので有効側です。

| 値 | `gfx1151_exp8()` の判定 |
|---|---|
| 未設定 | 有効候補 |
| 空文字 | 有効候補 |
| 先頭文字が `0`（例: `0`, `0abc`） | 無効 |
| その他すべて（例: `1`, `true`, `false`, `-1`） | 有効候補 |

「有効候補」は実際に mode 8 になることを保証しません。デバイス取得に成功し、デバイス名が gfx1151 と一致する場合に限り true になります。大文字小文字、空白、後続文字は判定に影響しません。

## 有効になる条件

次の条件が揃った場合に gate/up の mode 8 が選ばれます。

- HIP で、gfx906 専用ビルドではない。
- 有効な CUDA/HIP device index（0〜63）を使い、そのデバイスの `gcnArchName` が `gfx1151`。名前の後ろに `:sramecc-` などの属性が付く形式も認識します。
- `STRATA_EXP_MODE` が未設定、または `atoi()` の結果が負。0 以上の値を指定した場合は `exp_mode()` がその値を優先し、gfx1151 の自動 mode 8 判定を通りません。たとえば空文字や数値でない文字列は `atoi()` で 0 となるため mode 0 を指定した扱いです。
- native grouped expert 経路に入り、呼び出しの `grid_groups` が正で `cap_groups` 未満という部分 grid 条件に該当しない。この条件ではコードが `em0=0` を選び、`exp_mode()` を呼ばないためです。

それらの条件を満たしても、fused gate/up kernel の利用対象は `gu_type` が 18, 21, 22, 23、または `kExpLds16` が true のビルドで 16 であり、かつ `n_ff` が 32 の倍数の場合に限られます。その他の形式では mode 8 の LDS gate/up 経路または fallback kernel が使われます。

down projection には別の相互作用があります。`d_type == 20`（コードコメント上の Q2_0）では、gfx1151_exp8 が true のとき LDS down kernel を避けます。`STRATA_GFX1151_EXP8=0` でこれが false になると、exp mode 7 または 8 が選択されている呼び出しでは LDS down kernel の条件を満たせるようになります。`d_type == 42` はこの gfx1151 判定に関わらず LDS down の候補です。

## 実行時の詳細

`gfx1151_exp8()` は関数内の `static int per_dev[64]` にデバイスごとの結果を記憶します。最初の判定は当該デバイスでの初回呼び出し時で、同じプロセス内では環境変数を後から変更しても再評価されません。`STRATA_EXP_MODE` の変換結果も `exp_mode()` 内の static 値として初回評価後に保持されます。

デバイス index が範囲外なら false です。`cudaGetDeviceProperties()` が失敗した場合も false となり、その後 `cudaGetLastError()` でエラー状態を読み捨てます。この判定自体について専用のログ出力はありません。

ソースコメントは gfx1151 の exp mode 8 について、IQ pack の gate/up を一つの launch で処理する設計、および native expert bench による特定ケースの所要時間変化と mode 0 に対する bitwise equality を記しています。これはコメントに記載された測定条件の説明であり、一般的な性能向上を示すものではありません。`docs/DETAILS.md` と gfx1151 向け資料には、この環境変数固有の追加測定表は見つかりませんでした。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:4361-4376` — exp layout のビルド条件と既定値（gfx906 以外は mode 0）。
- `src/kernels/cuda/iq_kernels.cu:4951-4969` — 変数の読み取り、先頭文字判定、HIP/gfx906 条件、デバイス別 cache と gfx1151 判定。
- `include/strata/kernels/gfx_arch.hpp:15-20,32-33` — architecture 名の完全一致（任意の `:` 属性付き）判定。
- `src/kernels/cuda/iq_kernels.cu:4971-5007` — `STRATA_EXP_MODE` の優先順位と gfx1151 自動 mode 8 の選択。
- `src/kernels/cuda/iq_kernels.cu:5140-5156,5186-5204` — 部分 grid の mode 0 選択、mode 8 gate/up の形式・幅条件、LDS 経路。
- `src/kernels/cuda/iq_kernels.cu:5258-5273` — gfx1151 判定と down projection の LDS 条件。
- `include/strata/kernels/iq_kernels.hpp:75-82` — `grid_groups` の意味と既定値。
