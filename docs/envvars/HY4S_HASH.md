# `HY4S_HASH`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

`HY4S_HASH` は Hy4-Flash の SYCL runner で中間テンソルの診断ハッシュ収集を有効にする。値そのものは解釈せず、環境変数が設定されているかだけを `Runner::init()` で調べる。設定されていれば GPU 上に 65,536 個の `uint64_t` 用バッファを確保し、forward chunk 内の指定テンソルのハッシュを stderr に出す（`engine/src/hy4flash/sycl/sy_graph.h:489-515,723-758,797-800,1074-1116`）。この機能は生成値を選んだり、モデル計算の値を置き換えたりする分岐ではなく、診断用の追加計算・ログを行う。

## 値と判定

`Runner::init()` は `std::getenv("HY4S_HASH")` の null / 非 null だけを判定し、非 null のときに確保を行う（`engine/src/hy4flash/sycl/sy_graph.h:489-515`）。空文字も「設定あり」として有効で、文字列比較、数値変換、空白除去、大小文字判定はない。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Hy4-Flash SYCL runner | ハッシュ用バッファを確保せず、ハッシュ収集もしない | 空文字、`0`、`1`、`true`、その他どの文字列でも、環境変数が存在すれば有効 | 実行時に「無効値」と判定される設定文字列はない。環境変数が存在しない場合のみ無効 |

CUDA/HIP runner など、別実装に同じ名前の読み取り箇所は見つからなかった（ソース全体の `HY4S_HASH` 参照は `engine/src/hy4flash/sycl/sy_graph.h:514` のみ）。

## 有効になる条件

- `strata-hy4-sycl` の Hy4-Flash SYCL 実行経路で `Runner::init()` が呼ばれる必要がある。SYCL ビルドスクリプトは `sy_main.cpp` をコンパイルし、通常推論では `sy_main.cpp` が `Runner` を作成して `r.init()` を呼び、`--serve` では `hy4s_serve_main()` が同じ `Runner` を作成して初期化する（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:62-68`; `engine/src/hy4flash/sycl/sy_main.cpp:283-295`; `engine/src/hy4flash/sycl/sy_serve.h:262-267`）。
- `HY4S_HASH` は `Runner::init()` 時点で評価される。その時に設定されていなければ後から設定しても有効にならず、設定されていた場合も後から解除しても確保済みバッファと `d_hash` は残る（`engine/src/hy4flash/sycl/sy_graph.h:489-515,724-727`）。
- device バッファの確保に失敗すると `dalloc` が `dalloc: out of device memory (%zu bytes)` を stderr に出し、終了コード 3 でプロセスを終了する（この確保サイズは 524,288 bytes）。`engine/src/hy4flash/sycl/sy_common.h:262-270`。

## 実行時の詳細

`d_hash` があると、各 forward chunk の層ループで `maybe_dump()` 経由の対象（Engram 適用後、attention 後、MLP 後の残差 `x`）と、MoE 層の router logits / weights / indices、routed down 出力、routed up の各中間値などに対して GPU ハッシュを計算する（`engine/src/hy4flash/sycl/sy_graph.h:723-750,797-800,1407-1422,1074-1116`）。ハッシュはテンソルの `float` ビット列を GPU kernel 内で混合・加算して `uint64_t` にまとめる。名前は `c<位置> <テンソル名>` として蓄積し、chunk 処理末尾で待機・device から host へコピーして `[hash] <名前> <16桁16進値>` の形式で出力し、名前リストを消去する（`engine/src/hy4flash/sycl/sy_graph.h:726-758,1422`）。1 chunk で記録する名前は 60,000 件までで、それを超える分は `tap_hash()` が無視する（`engine/src/hy4flash/sycl/sy_graph.h:726-729`）。

ハッシュが有効だと `forward_chunk()` の command_graph replay 条件 `!d_hash` を満たさないため、その経路では eager な層ごとの処理に進む（`engine/src/hy4flash/sycl/sy_graph.h:1382-1392`）。これは通常の forward chunk の graph replay を避ける条件であり、ファイル内の別条件で動く head 処理や DFly2 の graph 経路まで一律に停止するチェックではない（`engine/src/hy4flash/sycl/sy_graph.h:1435-1454`; `engine/src/hy4flash/sycl/sy_dfly2.h:692-706,917-930`）。ハッシュ収集以外のモデル計算結果や生成 token を変える処理は、この変数の読み取り経路にはない。

## ログと測定値

各 chunk の診断値は stderr に `[hash] <名前> <16桁16進値>` と出る（`engine/src/hy4flash/sycl/sy_graph.h:751-758`）。未設定時はハッシュログを出さない。メモリ確保失敗時の stderr と終了コードは前節のとおり（`engine/src/hy4flash/sycl/sy_common.h:262-270`）。`docs/DETAILS.md` に `HY4S_HASH` 固有の測定値・説明は見つからなかった。

## 根拠

- `engine/src/hy4flash/sycl/sy_graph.h:489-515` — `Runner::init()` 内の唯一の環境読み取りとバッファ確保。
- `engine/src/hy4flash/sycl/sy_graph.h:723-758,797-800,1074-1116,1407-1422` — ハッシュ kernel、対象値、出力と呼び出し時期。
- `engine/src/hy4flash/sycl/sy_graph.h:1382-1392,1435-1454`; `engine/src/hy4flash/sycl/sy_dfly2.h:692-706,917-930` — forward chunk、head、DFly2 の graph 条件。
- `engine/src/hy4flash/sycl/sy_common.h:262-270` — device allocation の失敗ログと終了処理。
- `engine/src/hy4flash/sycl/sy_main.cpp:283-295`; `engine/src/hy4flash/sycl/sy_serve.h:262-267`; `engine/src/hy4flash/sycl/build_hy4_sycl.sh:62-68` — 通常推論・serve の runner 初期化とビルド対象。
