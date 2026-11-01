# `DS4_MM_YALT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal の DS4 expert down GEMM 経路で、入力 half 行列 `hin` を wrap し、ローカル変数 `hy` / `by` に代入する分岐を有効にします。ただし現行コードでは、これらのローカル変数は後続処理に渡されません。dispatch は引き続き `g_mm_ys` に出力し、そのバッファからエンジンの `yout` へコピーします。したがって、ソース上で確認できるのは `hin` の wrap とローカル変数への代入までであり、出力先を切り替える動作は確認できません。

## 値と判定

`std::getenv("DS4_MM_YALT")` の null 判定だけです。文字列の内容は変換・比較しません。

| 状態 | 分岐 |
|---|---|
| 未設定 | 通らない |
| 設定あり | 通る。空文字や `0` を含め、値の内容は問わない |

既定では分岐を通りません。CLI 引数や設定ファイル、他の環境変数による優先順位や fallback は、この変数については実装されていません。根拠: `metal/src/engine/ds4_finish.cpp:2575-2595`。

## 有効になる条件

- `STRATA_METAL` が定義されたビルドで、`set_down()` が Metal host の `iq_set_dn()` を呼び出すこと。呼び出しは `a.hbounds != nullptr` の場合に限られます（`src/dsv41/ds4_iq.cu:1604-1608`）。
- `mm_set()` が早期 return せず down 側の分岐に進むこと。`n_exp` と `total_rows` が正で、量子化 type が対応し、`n_embd` と `n_ff` が 256 の倍数、さらに `ldh == n_ff` と `ldy == n_embd` である必要があります（`metal/src/engine/ds4_finish.cpp:2476-2484`）。`mm_prepare()` が失敗した場合も、この変数を読む前に `false` を返します。
- 値を読み直すのは `mm_set()` が down 側に入るたびです。`static` cache はありません。gate/up 側ではこの分岐を通りません（`metal/src/engine/ds4_finish.cpp:2575-2595`）。

## 実行時の詳細

変数が設定されていると、コードは `hy = hh` とし、`hh`（`hin` の `strata::gpu::host_view`）を `total_rows * n_ff * 2` bytes で `wrap()` した結果を `by` に代入します。直後に `DS4_MM_EXP1` が設定されていれば、さらに `by` と `hy` を別の割り当てで上書きします（`metal/src/engine/ds4_finish.cpp:2576-2595`）。

しかし、down kernel の引数はこの `by` / `hy` ではなく `g_mm_ys` を渡します。kernel はその第2 buffer に結果を書き、実行後のコピーも `g_mm_ys` から `yout` に行います。そのため、`DS4_MM_YALT` 単独では計算結果の出力先を変更しません（`metal/src/engine/ds4_finish.cpp:2590-2597,2617-2633`; kernel 引数: `metal/src/engine/msl/ds4_mm.metal:88-92`）。

分岐内の `wrap()` 呼び出しは残ります。wrap に失敗すると `mtl: wrap %zu failed` を stderr に出して終了コード 4 で終了する経路があります。また、対象がランタイム所有 allocation 内になく、`DS4_WRAP_LOG` が設定されている場合は fallback の診断ログが出ます（`metal/src/mtl_rt.mm:623-667`）。`by` は dispatch に使われず、ここで `Context::free()` にも渡されません。

この変数について `docs/DETAILS.md` を含む Strata の説明資料に記載は見つかりませんでした。実装中の効果は上記のソースから確認できる範囲に限ります。

## 根拠

- 変数の読み取りとローカル代入: `metal/src/engine/ds4_finish.cpp:2575-2595`
- DS4 down 実装への Metal host 経路: `src/dsv41/ds4_iq.cu:1604-1608`
- down kernel dispatch と出力コピー: `metal/src/engine/ds4_finish.cpp:2590-2633`
- kernel が受ける出力 buffer: `metal/src/engine/msl/ds4_mm.metal:88-92`
- `wrap()` のログ・失敗経路: `metal/src/mtl_rt.mm:623-667`
