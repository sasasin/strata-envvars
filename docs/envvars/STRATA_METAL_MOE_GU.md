# `STRATA_METAL_MOE_GU`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Metal の `Window::layer` が MoE gate/up カーネルに使うタイル形状（1 行あたりの lane 数 `L`、lane あたりの行数 `R`、simdgroup 数 `S`）を上書きする診断・調整用の値である。既定の形状で計算される `moe_gu_...` の代わりに、値から組み立てた別の関数名を選び、同時に threadgroup 数と MoE の `gx_gu` を変更する。ルーティングや gate/up の計算そのものを別の処理に置き換える変数ではない（`engine/metal/src/engine/window.cpp:1333-1355,1372-1399`）。

## 値と判定

共通 parser が `std::getenv(name)` の結果を `sscanf(e, "%d,%d,%d", ...)` に渡し、3 個すべての整数変換が成功した場合だけ設定値として扱う。値全体の消費や整数の範囲・正値・タイルとしての妥当性は検証しない。空白は `%d` の変換規則に従い、区切りのカンマは書式どおり必要。3 個目の整数より後ろは読み取り結果に影響しない。`std::getenv` が null（未設定）または変換数が 3 未満なら既定値を使う。空文字、`1`、`1,2` は無効。例えば `32,1,4` と `32,1,4junk` は parser 上は有効、`32,1,0` も parser 上は受理されるが、後者のような値が安全とは限らない（`engine/metal/src/engine/window.cpp:1343-1351,1353-1355`）。

| 条件 | unset / parser が失敗 | parser が成功した値 | 受理後の制限 |
|---|---|---|---|
| Metal `Window::layer`、gate/up の重み型が `tq_` でない | `gl=32, gr=1, gs=4`、または `tq_` なら後述の既定値 | `L,R,S` をそのまま代入 | parser に正値・範囲・対応カーネルの検査なし |
| `tq_`（`tg_.type >= 144`） | `gl=16, gr=2, gs=4` | 値は parse されるが gate/up 形状への代入は行わない | 常に既定形状 |

受理値から関数名 `moe_gu_<type>_<L>_<R>_<S>`（fp16 条件下では `moe_gu16_...`）を作る。Metal カーネルにその組み合わせの実体がなければ pipeline 作成時に `mtl: no function ...` を stderr に出し、終了コード 3 で終了する。例えば数値として受理されても、コンパイル済みの組み合わせである保証はない（`engine/metal/src/engine/window.cpp:1353,1372-1383`; `engine/metal/src/mtl_rt.mm:229-255`; `engine/metal/kernels/moe.metal:439-454,595-600`）。

## 有効になる条件

- Metal backend の `Window::layer` が MoE 層を組み立てること。参照箇所は Metal 固有実装 `engine/metal/src/engine/window.cpp` にある（同ファイル `:1-3,1153-1156,1576-1577,1614`）。
- gate/up 重み型が `tg_.type < 144` であること。`tq_` の場合、環境変数は読み取られても形状上書きは無視される（`engine/metal/src/engine/window.cpp:1333-1337,1349-1351`）。
- 設定形状に対応する関数名が Metal ライブラリに存在し、threadgroup サイズが GPU の上限内であること。未登録関数は終了コード 3、threadgroup 上限超過は Strata の診断を stderr に出して終了コード 6 となる（`engine/metal/src/engine/window.cpp:1372-1399`; `engine/metal/src/mtl_rt.mm:252-265,287-296`）。
- `STRATA_METAL_F16` による fp16 経路でも、常駐モデルなど `m16` の条件を満たす場合は `moe_gu16_...` 名を組み立てる。GU 値の上書き条件自体は `!tq_` であり、別の有効値チェックはない（`engine/metal/src/engine/window.cpp:1353,1372-1389`; fp16 カーネルの登録は `engine/metal/kernels/moe.metal:474-475,595-600`）。
- `m16` は `f16_enc_ && !stream_ && tg_.type == Q2_0 && dq2 && !had_gu(l) && !had_dn(l)` の条件であり、`f16_enc_` は `STRATA_METAL_F16` の判定に加えて head 実行・非 stream・非 batch rows の条件を持つ（`engine/metal/src/engine/window.cpp:1353,1563-1564`）。
- 別の MTP draft MoE 経路（`engine/metal/src/engine/window.cpp:2799-2816,2833-2844`）は形状をローカル定数にしており、この環境変数の読み取りは見つからない。
- 参照元には CLI 引数との優先順位や、別の環境変数による GU 形状の上書きはない。`STRATA_METAL_F16` は fp16 kernel 名の選択条件に関係するが、GU 形状の parse 値を上書きしない（`engine/metal/src/engine/window.cpp:1343-1351,1353,1372-1383`）。

## 実行時の詳細

読み取りは `Window::layer` の MoE 層処理中、gate/up と down の既定形状を決めた直後に行う。`gu_e` と `gu_o` は関数ブロックスコープの `static` であり、最初にこの箇所へ到達したときの環境値と parse 結果をプロセス内で保持する。したがって起動後に環境を変更しても、以降の層や window には反映されない（`engine/metal/src/engine/window.cpp:1337-1351`）。

値が適用されると、`gl/gr/gs` は kernel 関数名、`gx_gu = NFF / (gs * (32 / gl) * gr)`、および dispatch の `tg[0] = 32 * gs` に使われる。その後 `P(...)` が名前に対応する pipeline を取得し、gate/up dispatch を構築する。形状はモデルの MoE 層ごとに同じ初回 parse 結果を利用するが、`tq_` 層は各層で代入をスキップする（`engine/metal/src/engine/window.cpp:1349-1355,1372-1399`）。

範囲検査がないため、ゼロ値では `gx_gu` の計算でゼロ除算になり得る。0 以外でも `gl` が 32 を超えると整数式 `32 / gl` は 0 となり、形状や `gx_gu` が意図しない値になり得る。これは受理値に対する明示的な Strata fallback ではない。コンパイル済み関数名の不一致や threadgroup 上限超過は前節の終了経路となる（`engine/metal/src/engine/window.cpp:1353-1355,1372-1399`; `engine/metal/src/mtl_rt.mm:252-296`）。

## ログと測定値

この変数自体を読み取ったことや値を採用したことを示すログはない。設定値で生成した関数名が見つからない場合は `mtl: no function <関数名> <詳細>` を stderr に出して終了コード 3、pipeline state の作成失敗は `mtl: pipeline <関数名>: <詳細>` を出して終了コード 3。threadgroup 上限超過は `strata metal: the kernel ... can run at most ...` で始まる診断を stderr に出し、終了コード 6 となる（`engine/metal/src/mtl_rt.mm:252-265,287-296`）。この変数の値に関する測定値は、調査対象ソース・`docs/DETAILS.md` で確認できなかった。

## 根拠

- `engine/metal/src/engine/window.cpp:1333-1355` — 既定値、`sscanf` parser、static cache、`tq_` 除外、`gx_gu` の計算。
- `engine/metal/src/engine/window.cpp:1372-1399` — カーネル名への反映と gate/up dispatch の threadgroup サイズ。
- `engine/metal/src/engine/window.cpp:1353,1563-1564` — fp16 kernel 選択に関係するモデル・window 状態。
- `engine/metal/src/engine/window.cpp:2799-2844` — 別の draft MoE 経路が独自の定数形状を使う箇所。
- `engine/metal/kernels/moe.metal:439-454,595-600` — Metal 側で登録されるタイル形状の組み合わせ。
- `engine/metal/src/mtl_rt.mm:229-265,287-296` — 関数名・pipeline の失敗と threadgroup 上限超過時のログ・終了処理。
