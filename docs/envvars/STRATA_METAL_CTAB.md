# `STRATA_METAL_CTAB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal backend の routed expert gate/up kernel で、i-quant のグリッドと sign table を threadgroup memory にコピーして参照する代わりに、定数配列から参照する経路を選びます。Metal の decode window と、ロード済み MTP draft layer の gate/up dispatch が対象です。`quant.metal` はこの切替で同じ table 値を使うと説明しています。変わるのは table の読み方で、環境変数による Strata 側の値変換や別の量子化形式への切替ではありません（`engine/metal/src/engine/window.cpp:150-158,1372-1383,2833-2844`; `engine/metal/kernels/quant.metal:104-115,409-435`）。

## 値と判定

`metal_ctab()` は `std::getenv` の結果を `std::string` にして、文字列全体がちょうど `"0"` かどうかを比較します。未設定または `"0"` 以外なら ON です。空文字も ON になり、数値変換・空白除去・大文字小文字変換・形式検証はありません（`engine/metal/src/engine/window.cpp:152-157`）。

| 条件（build / 経路） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Metal engine の `moe_gu` dispatch（通常の decode window、および MTP draft layer） | ON | `1`, `true`, `00`, 空文字 | `0` |
| `moe_gu16` を使う特別な経路 | CTAB 設定は pipeline に渡されず、この変数では切り替わらない | 該当なし | 該当なし |

「無効」は値のパースエラーではなく、`"0"` のときに CTAB 経路を OFF にする意味です。たとえば `0anything`、` 0`、`false` は文字列全体が `"0"` ではないため ON です。`moe_gu16` の条件は、`f16_enc_ && !stream_ && tg_.type == ref::Q2_0 && dq2 && !had_gu(l) && !had_dn(l)` です。この場合は gate/up pipeline の作成に function constant 23 を渡さず、通常の CTAB 分岐に入りません（`engine/metal/src/engine/window.cpp:1353,1372-1383`）。

## 有効になる条件

- `STRATA_GPU_METAL` でビルドされ、Metal engine が含まれている必要があります。CMake は Metal engine のビルドに Apple Metal C++ headers を要求し、Metal backend を定義します（`engine/metal/CMakeLists.txt:82-109,150-177`）。共有 verifier はこの build 条件下で Metal window に処理を渡します（`engine/src/core/verify.cpp:99-107,978-992,3792-3806`）。
- 実行が Metal window の routed expert gate/up `moe_gu` dispatch に到達する必要があります。通常 decode では各層の routed gate/up dispatch に設定値を適用します（`engine/metal/src/engine/window.cpp:1330-1353,1372-1383`）。
- MTP draft layer の経路では draft layer がロードされ、その routed gate/up dispatch が実行される場合に適用されます。MTP は独立した draft model / layer の経路です（`engine/metal/src/engine/window.cpp:292-296,2497-2505,2833-2844`）。
- `moe_gu16` の特殊経路では設定値は使われません（`engine/metal/src/engine/window.cpp:1353,1372-1383`）。また、この変数は prompt 用 kernel library の pipeline 作成箇所には現れず、対象は上記の `window.cpp` の gate/up dispatch です（同ファイル `:1372-1383,2833-2844`; `engine/metal/src/engine/msl_libs.h:25-29,39-42`）。
- i-quant の grid / sign table を使わない重み形式では、CTAB の lookup 分岐自体に差はありません。対応する i-quant table accessors は `quant.metal` にあります（`engine/metal/kernels/quant.metal:104-115,409-435`）。

## 実行時の詳細

値は `metal_ctab()` 内の関数ローカル `static const bool` 初期化子で初回に読み取られ、その後プロセス内で cache されます。環境を実行中に変更しても反映されません。通常 decode の gate/up pipeline は function constant 23 と `#ct` を含む pipeline key を使い、MTP draft layer も同じ function constant と key suffix を設定します。ストリーミング中の通常 decode は、追加の function constant 20 と `#arena` を同時に設定します（`engine/metal/src/engine/window.cpp:152-157,1378-1383,2833-2840`）。

`quant.metal` では CTAB ON の場合、i-quant grid と IQ2_XS sign table を constant arrays から読み、threadgroup table のロードを省略します。OFF の場合は threadgroup table をロードする処理が使われます。カーネルコメントは両経路が同じ値を使い、CTAB 経路は threadgroup 開始時の table load と barrier wait を省くとしています（`engine/metal/kernels/quant.metal:104-115,409-435`）。Strata 側には、この変数専用の CLI 引数、別環境変数による上書き、警告や失敗時 fallback は見当たりません。

## ログと測定値

この変数の判定や有効化を表示するログはありません。`window.cpp` のコメントには「M5 Max で 3-7% faster」とありますが、該当コメントにモデル、量子化、測定区間、試行回数などの条件は記されていません。そのため、これはソースコメントに記載された範囲の主張であり、他機種・モデル・実行経路に一般化できる測定値ではありません（`engine/metal/src/engine/window.cpp:150-151`）。

## 根拠

- 環境変数の読み取りと値判定: `engine/metal/src/engine/window.cpp:150-158`
- 通常 decode の routed gate/up pipeline: `engine/metal/src/engine/window.cpp:1330-1353,1372-1383`
- MTP draft layer の routed gate/up pipeline: `engine/metal/src/engine/window.cpp:2497-2505,2800-2844`
- Metal function constant と i-quant table access: `engine/metal/kernels/quant.metal:100-115,409-435`
- Metal backend / engine の build 条件: `engine/metal/CMakeLists.txt:82-109,150-177`; Metal window への verifier handoff: `engine/src/core/verify.cpp:99-107,978-992,3792-3806`
