# `STRATA_METAL_CTAB`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Metal backend の MoE expert 行列積カーネルで、IQ 量子化テーブルを threadgroup memory にコピーして読むか、Metal function constant `QUANT_CTAB` を通じて既存の定数配列から読むかを選びます。既定は有効です。対象のテーブル値は同じであり、切り替わるのはテーブルの読み方です。

## 値と判定

`metal_ctab()` は `std::getenv("STRATA_METAL_CTAB")` の結果を `std::string` にして、文字列全体がちょうど `"0"` か比較します。数値変換、前後空白の除去、先頭文字だけの判定はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 有効 |
| 空文字 | 有効 |
| `0` | 無効 |
| `00`、`0 `、`0anything` | 有効 |
| `1`、`false`、その他の文字列 | 有効 |

判定結果は関数内の `static const bool` に保存されます。プロセス内で最初に `metal_ctab()` が呼ばれた時点の値が使われ、その後にプロセス環境を変更しても再評価されません。

根拠: `metal/src/engine/window.cpp:67-73`。

## 有効になる条件

- Metal backend の `metal/src/engine/window.cpp` が実行される経路に限られます。CUDA/HIP/CPU backend に対する制御ではありません。
- MoE の routed expert gate/up と down カーネルで、この関数定数が使われます。通常の `Window::layer()` 経路では `QUANT_CTAB` を gate/up と down の両方へ渡します。単一 token 用の別経路では gate/up に渡しますが、down の dispatch には渡していません。
- カーネルが IQ2/IQ3 系のテーブルを読むときに差が現れます。`load_tab` はこれらの形式について、有効時には threadgroup テーブルのコピーを省き、無効時には定数配列から threadgroup テーブルへコピーします。ヘルパー関数は有効時に定数配列を、無効時に threadgroup テーブルを参照します。他の量子化形式はこの分岐対象ではありません。

根拠: `metal/src/engine/window.cpp:657-675,842-868,1811-1827`; `metal/kernels/quant.metal:65-76,95-118`; `metal/kernels/moe.metal:206-219,273-284`。

## 実行時の詳細

通常の `Window::layer()` は gate/up カーネルの pipeline 定数に index 23 の bool を設定し、キャッシュキーにも有効時の `#ct` を加えます。down カーネルにも同じ定数オブジェクトとキー接尾辞を渡します。単一 token 用の MoE 経路も gate/up の pipeline に index 23 を設定します。pipeline は `Window::P()` の `pcache_` にキー単位で保存されます。

Metal shader 側では `QUANT_CTAB` が定数として定義されます。有効なら IQ2_XXS、IQ2_XS、IQ2_S、IQ3_XXS、IQ3_S の `load_tab` specialization がテーブルコピーを行わず、参照関数が Metal 側の定数テーブルを読みます。無効ならテーブルを threadgroup にコピーしてから参照します。カーネル呼び出し側には `threadgroup_barrier` が明示的に残っているため、環境変数が有効な場合に barrier 自体も必ず消える、とはコードから言えません。

`window.cpp:66` のコメントは M5 Max で 3–7% 高速だったと記していますが、測定条件や手順を示す資料は今回確認した `docs/DETAILS.md` には見つかりませんでした。この値は実装コメントの記載として扱い、一般的な性能向上の保証とはしません。

根拠: `metal/src/engine/window.cpp:148-155,842-868,1811-1827`; `metal/kernels/quant.metal:65-76,95-118`; `metal/kernels/moe.metal:206-219,246-284`。

## 根拠

- 環境変数の読み取りと既定値: `metal/src/engine/window.cpp:65-73`
- 通常の decode window での pipeline 設定: `metal/src/engine/window.cpp:842-868`
- 単一 token 経路での pipeline 設定: `metal/src/engine/window.cpp:1811-1827`
- function constant と IQ テーブル参照: `metal/kernels/quant.metal:65-76`
- IQ2/IQ3 テーブルの threadgroup コピー: `metal/kernels/quant.metal:95-118`
- MoE gate/up と down の table load: `metal/kernels/moe.metal:206-219,273-284`
- Metal backend の compile definition: `metal/CMakeLists.txt:60`
