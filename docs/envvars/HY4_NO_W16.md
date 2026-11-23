# `HY4_NO_W16`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP の HY4 runner が RDNA4（実行時に gfx12 と判定される GPU）で一部の行列積に使う、重みを FP16 に一度展開して GEMM する経路を無効にするためのスイッチ。`Runner::lin()` はこの経路が許可されない場合、通常の `linear_h()` に処理を渡す。変数の値を計算や出力へ渡すのではなく、設定されているかどうかだけで経路を選ぶ（`engine/src/hy4flash/run/hy4_graph.hip.h:1332-1347`）。

これは全 backend 共通の設定ではない。判定コードは `HY4_MMA && !HY4_CUDA` のビルドにだけ含まれ、CUDA ビルドおよび MMA 無効ビルドではこの変数を参照しない（`engine/src/hy4flash/run/hy4_graph.hip.h:1337-1345`）。

## 値と判定

`getenv("HY4_NO_W16")` の null 判定だけを行う。文字列の変換や内容比較はないため、未設定なら抑止せず、何らかの値が設定されていれば抑止する。明示的な空文字、`0`、`1`、`true`、任意の文字列はいずれも「設定あり」で同じ結果になる。数値境界や無効値時の fallback はない（`engine/src/hy4flash/run/hy4_graph.hip.h:1337-1340`）。

| 条件 | unset | 設定ありの例 | `HY4_NO_W16` が未設定でも W16 経路が使われない例 |
|---|---|---|---|
| `HY4_MMA && !HY4_CUDA` のビルド | 追加条件を満たせば許可候補 | 空文字、`0`、`1`、`true` を含め常に抑止 | gfx12 以外、scratch buffer が null、`M < 256`、`FMT_Q8ROW`、`HY4_INT8_WMMA` の `atoi` 結果が非 0、または重みサイズが 48 MiB 超 |
| それ以外のビルド | 変数を読まない | 変数を読まない | W16 経路の判定自体がコンパイル対象外 |

読み取り式は `static const bool` 初期化子なので、対応ビルドでは `lin()` の最初の呼び出し時に一度評価され、その後の環境変更は反映されない。gfx12 判定も `is_gfx12_device()` 内の関数ローカル `static` で一度だけ評価される（`engine/src/hy4flash/run/hy4_graph.hip.h:1332-1340`、`engine/src/hy4flash/run/sk_int8_rdna4.hip.h:45-53`）。

## 有効になる条件

`HY4_NO_W16` を unset にしただけでは切り替わらず、次の条件がすべて必要。

- `HY4_MMA` が有効で `HY4_CUDA` が無効のビルドであること。RDNA2 の gfx103x は `HY4_MMA` を無効にする定義がある（`engine/src/hy4flash/run/hy4_gpu.h:335-351`）。
- 実行デバイスの arch 名が `gfx12` で始まること。デバイス取得またはプロパティ取得に失敗した場合は gfx12 判定が false になる（`engine/src/hy4flash/run/sk_int8_rdna4.hip.h:45-53`）。
- 呼び出し側から `w16` scratch buffer が渡され、`M >= 256` であること。attention と MLP の主な呼び出し側では `!dump && Tc >= 2048` のときだけ buffer を渡す（`engine/src/hy4flash/run/hy4_graph.hip.h:2091-2100, 2683-2695`）。
- 対象重みの形式が `FMT_Q8ROW` ではなく、`HY4_INT8_WMMA` の `atoi` 結果が 0 であること。`HY4_INT8_WMMA` は未設定なら 0、設定時は `atoi` で評価される（`engine/src/hy4flash/run/hy4_graph.hip.h:1340`、`engine/src/hy4flash/run/sk_int8_rdna4.hip.h:55-62`）。
- `t.rows() * t.cols() * 2` が 48 MiB 以下であること（`engine/src/hy4flash/run/hy4_graph.hip.h:1339-1341`）。

呼び出し側が `linear_h_multi()` で複数投影をまとめて処理する場合や、`lin()` に scratch buffer を渡さない場合、このスイッチが W16 経路を変える呼び出しにはならない。たとえば attention の fused 経路では q/kv/gate を `linear_h_multi()` で処理する（`engine/src/hy4flash/run/hy4_graph.hip.h:2088-2100`）。

## 実行時の詳細

W16 経路が成立すると、`linear_h_dequant_f16()` が対応する S1.25 / S1.5 / S2〜S6 / S8 形式の重みを FP16 scratch に展開し、その後 gfx12 用 FP16 GEMM kernel を起動して早期 return する。関数内の switch にない形式は `linear_h_gemm()` に fallback する（`engine/src/hy4flash/run/skwmma.hip.h:1280-1299`）。

`HY4_NO_W16` が設定されている、または前節のいずれかの条件が成立しない場合、`Runner::lin()` は `linear_h()` を呼ぶ。したがって、この変数が変えるのは条件に合う個々の投影の実装経路であり、モデル全体の全行列積を一律に切り替えるものではない（`engine/src/hy4flash/run/hy4_graph.hip.h:1338-1347`）。コード上、`HY4_NO_W16` による CLI 引数の優先順位、子プロセスへの個別転送、実行中の再読み込みはない。

## ログと測定値

この変数の読み取りや有効・無効判定に伴う専用ログ、警告、終了・失敗経路は見つからない。`docs/DETAILS.md` にも `HY4_NO_W16` の説明や、この変数を指定した場合の測定値は見つからなかった。ソースコメントは W16 経路を gfx12 の重みを一度 FP16 に展開する最適化として説明するが、同コメントの説明以上の性能値はこの文書では主張しない（`engine/src/hy4flash/run/hy4_graph.hip.h:1338-1341`）。

## 根拠

- `engine/src/hy4flash/run/hy4_graph.hip.h:1332-1347` — 読み取り、キャッシュ、条件分岐と通常経路への fallback。
- `engine/src/hy4flash/run/hy4_graph.hip.h:2088-2100, 2683-2695` — 呼び出し側の scratch buffer 条件と fused 経路。
- `engine/src/hy4flash/run/sk_int8_rdna4.hip.h:45-62` — gfx12 実行時判定と `HY4_INT8_WMMA` の読み取り。
- `engine/src/hy4flash/run/hy4_gpu.h:335-357` — RDNA2、gfx12 のビルド macro 条件。
- `engine/src/hy4flash/run/skwmma.hip.h:1280-1299` — FP16 展開と GEMM kernel、未対応形式の fallback。
