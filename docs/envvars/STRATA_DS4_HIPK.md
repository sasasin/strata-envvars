# `STRATA_DS4_HIPK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。Strata checkout の `git status --short --branch` は `## main...origin/main`。

## 役割

HIP ビルドの DSV41 IQ expert gate/up・down カーネルで、gfx12 / gfx11 の WMMA カーネルを使うかを選びます。対象は `IQ2_XXS`、`IQ2_XS`、`IQ2_S`、`IQ3_XXS`、`IQ3_S`、`IQ4_XS`、`IQ1_S`、`IQ1_M`、`IQ4_NL` です。ほかの型や条件に合わない入力では、この経路は使われず、呼び出し元が通常の `set_kernel` を起動します（`src/dsv41/ds4_iq_hip.inc:21-23,296-334`、`src/dsv41/ds4_iq.cu:1185-1201`）。

## 値と判定

デバイス許可判定では値の先頭文字を直接比較し、許可後のカーネル選択では `std::atoi` を使います。そのため、値の意味は GPU 世代ごとに異なります。

| GPU 世代 | 未設定 | 設定時の許可判定（`ok_device()`） | 許可後のカーネル選択 |
|---|---|---|---|
| gfx12 (`gfx12` prefix) | 有効 | 先頭文字が `0` なら無効。それ以外は有効（空文字を含む） | `atoi` 結果が `2` なら共有メモリ重みカーネル。それ以外はレジスタ重みカーネル |
| gfx11 (`gfx11` prefix) | gfx1151 のみ有効。それ以外は無効 | 先頭文字が `1` の場合だけ有効。空文字を含むそれ以外は無効 | gfx11 では整数値 `2` は不採用。それ以外の値はレジスタ重みカーネル |
| その他 / device property 取得失敗 | 無効 | 無効 | この経路に入らない |

`ok_device()` は gfx12 では「未設定なら有効、設定値の先頭が `0` なら無効」という判定です。gfx11 では明示値の先頭が `1` のときだけ有効で、未設定時は gfx1151 だけ既定で有効です。設定値 `0` は gfx11 / gfx12 の両方で無効になります（`src/dsv41/ds4_iq_hip.inc:254-270`）。

許可後の `launch()` は、未設定なら `0`、設定時は `std::atoi` の結果を静的変数に保存します。`atoi` は数値として読めない文字列を `0` とし、先頭の整数部分を変換します。従って gfx12 では `2` や `2tail` が共有メモリ重みカーネル、`1`・`10`・`true`・空文字はレジスタ重みカーネルになります。ただし `0` と `0tail` は先の許可判定で経路自体が無効です。gfx11 は先頭が `1` で始まる文字列だけが許可され、整数変換結果が `2` の値は通常この条件と両立しません（`src/dsv41/ds4_iq_hip.inc:260-267,305-334`）。

## 有効になる条件

- HIP ビルドで `STRATA_USE_HIP` が定義され、DSV41 IQ カーネルの `launch_set()` 経由であること。CUDA ビルドでは `hipk::launch()` の呼び出しがコンパイル対象になりません（`src/dsv41/ds4_iq_hip.inc:10-12`、`src/dsv41/ds4_iq.cu:1184-1195`）。
- デバイス名が gfx12 または gfx11 として認識され、上表の許可判定を通ること。通常の gfx11 では `=1` 等の opt-in が必要で、gfx1151 は未設定時に有効です（`src/dsv41/ds4_iq_hip.inc:254-270`）。
- 型が上記9種で、`a.max_rows > 16`、K が256の倍数、N が64の倍数、`ldx` が8の倍数、`ldo` が2の倍数、入力ポインターが16-byte aligned であること（`src/dsv41/ds4_iq_hip.inc:21-23,296-304`）。
- 呼び出し元で trellis 型に分岐せず、寸法の事前条件を満たして IQ set kernel に到達すること。gate/up は `a.tg`、down は `a.td` を dispatch します（`src/dsv41/ds4_iq.cu:1625-1660`）。

これらのいずれかを満たさない場合、`hipk::launch()` は `false` を返し、`launch_set()` は標準 `set_kernel` を起動します。従って有効な環境変数値だけでは WMMA カーネルの使用は保証されません（`src/dsv41/ds4_iq_hip.inc:297-304`、`src/dsv41/ds4_iq.cu:1186-1201`）。

## 実行時の詳細

`ok_device()` はデバイスごとの `static std::atomic<int> state[16]` に判定を保存し、各 device につき初回判定時に環境変数を読みます。別に、条件を通過した `launch<T, GU>()` ごとの `static const int var` が `atoi` 結果を初回呼び出し時に cache します。プロセス実行中に環境を変更しても、既に cache された device / template instantiation の判定は更新されません。後から初めて呼ばれる template instantiation ではその時点の環境を読み得ます（`src/dsv41/ds4_iq_hip.inc:237-270,296-308`）。

gfx12 では整数値 `2` が共有メモリに重みを展開する `set_kernel` を選び、その他の許可値は重みをレジスタに置く `runr` 系の WMMA カーネルを選びます。後者は `HIPK_CFG` によるタイル構成選択を持ちます。gfx11 は共有メモリ重みカーネルを使わず、許可された場合は `runr` 系になります（`src/dsv41/ds4_iq_hip.inc:305-334`）。

この環境変数を読んだこと自体を報告するログや、無効値に対する警告は確認できません。WMMA 経路が選べない場合は通常カーネルに続行します。WMMA kernel launch の直後は `cudaPeekAtLastError()` の結果を返し、失敗なら `launch_set()` は通常カーネル側へ進みます（`src/dsv41/ds4_iq_hip.inc:286-294`、`src/dsv41/ds4_iq.cu:1186-1201`）。

## 根拠

- 環境変数の全ソース参照: `src/dsv41/ds4_iq_hip.inc:260-266,305-306`。その他の一致は同ファイルのコメント、`src/dsv41/ds4_iq.cu:1188` のコメント、および `tests/dsv41/iq_expert_test.cpp:519` のテストコメントです。別の実読み取り箇所はありません。
- WMMA カーネルの型・入力条件・2系統の選択: `src/dsv41/ds4_iq_hip.inc:21-23,286-334`。
- HIP 条件と呼び出し元の標準カーネル fallback: `src/dsv41/ds4_iq_hip.inc:10-12,297-304`、`src/dsv41/ds4_iq.cu:1184-1201,1625-1660`。
- `docs/DETAILS.md` と `docs/AMD_HIP.md` には、この変数固有の動作説明や測定条件を確認できませんでした。性能や精度の効果はここでは主張しません。
