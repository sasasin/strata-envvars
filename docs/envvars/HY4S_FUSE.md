# `HY4S_FUSE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL 版 Hy4-Flash runner の `Runner::build_fuse()` で、複数の量子化行列ベクトル積 (GEMV) をまとめて実行する decode/verify 用の経路を有効・無効にします。既定は有効です。有効でも対象 tensor が対応形式・形状などの条件に合わない組は個別 GEMV に戻ります。CUDA/HIP runner や他のエンジンの融合を切り替える変数ではありません。読み取りと状態設定は `engine/src/hy4flash/sycl/sy_graph.h:859-872`、SYCL runner のビルドと実行入口は `engine/src/hy4flash/sycl/build_hy4_sycl.sh:1-5,26-40,64-69` および `engine/src/hy4flash/sycl/sy_main.cpp:1` にあります。

## 値と判定

`std::getenv("HY4S_FUSE")` の結果について、設定値の先頭 1 文字だけを調べます。数値変換や文字列全体の比較はしません。unset または空文字では `e[0] == '0'` が成立しないため有効です。先頭が文字 `0` なら値の残りに関係なく無効、それ以外は有効です（`sy_graph.h:859-872`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL Hy4-Flash runner (`strata-hy4-sycl`) | 有効 | 空文字、`1`、`true`、`false`、`off`、` 0` | `0`、`0anything`、`00` |

大文字小文字や空白の trim、整数としての妥当性検査はありません。`false` と `off` も先頭が `0` ではないので有効です。値は `Runner::init()` 中の `build_fuse()` で読み取られ（`sy_graph.h:489-490,617-620`）、`fuse_dec` に保存されます。runner 初期化後に環境を変更しても、その runner の設定は再評価されません。プロセス内で runner を作り直せば、新しい初期化時点の環境値が読み取られます。

## 有効になる条件

- SYCL 版 Hy4-Flash runner の `Runner` が初期化されること。通常の CLI 実行経路と `--serve` 経路の両方で `r.init()` が呼ばれます（`engine/src/hy4flash/sycl/sy_main.cpp:283-296`、`engine/src/hy4flash/sycl/sy_serve.h:258-269`）。
- trunk の attention 融合は処理時の `T` が 1〜8、`fuse_dec` が真、`dump` が偽で、各 layer の融合 descriptor が作れたときに使われます。layer 0 の MLP gate/up 融合にも同じ `T`・`dump` 条件と descriptor 条件があります（`engine/src/hy4flash/sycl/sy_graph.h:961-966,1053-1063`）。MoE sub-stage の融合も同じ条件に加え、その layer の全 descriptor が成立する必要があります（同 `:1077-1116`）。
- 各 descriptor に入る重みは repacked tensor であること、形式が `FMT_S4` / `FMT_S5` / `FMT_S8` のいずれかであること、shape が 2 次元であること、1 descriptor の job 数が 3 未満であることが必要です。追加 job は既存 job と同じ K 幅でなければ受理されません（`engine/src/hy4flash/sycl/sy_graph.h:843-857`）。attention の gate job は q/kv の 2 job が作れた場合に追加され、追加できなくても q/kv 2 job の融合は独立して可能です（同 `:880-885`）。他の descriptor 群のいずれかが不成立なら、その MoE layer の融合群は成立せず、個別経路を使います（同 `:891-895,1077-1116`）。
- DFly2 drafter も `r.fuse_dec` が真のとき、5 層の attention・MLP および hidden-correction 用 descriptor の構築を試みます。実際のドラフト計算には DFly2 が利用可能であることが必要です（`engine/src/hy4flash/sycl/sy_dfly2.h:555-575,583-589,608-640`）。CLI では `--draft dfly2` が drafter の初期化を要求し、サーバーでは draft 設定と chunk 条件に従って初期化します（`engine/src/hy4flash/sycl/sy_main.cpp:310-316`、`engine/src/hy4flash/sycl/sy_serve.h:253-277`）。
- `--dump` は CLI で `dump` を真にし、trunk の上記融合実行条件を外します（`engine/src/hy4flash/sycl/sy_main.cpp:166,283-285`）。ただし `build_fuse()` は `dump` を見ずに実行されるため、環境変数が有効なら descriptor 作成前の scratch 確保までは行います（`sy_graph.h:859-877`）。
- `HY4S_GRAPH` は command_graph の可否を別に決めます。`HY4S_FUSE` はその設定と独立して `build_fuse()` で判定され、共通の trunk 処理関数で利用されます（`engine/src/hy4flash/sycl/sy_graph.h:617-627,951-966`）。

## 実行時の詳細

`build_fuse()` は `Runner::init()` の中で一度 `HY4S_FUSE` を読み、無効なら descriptor 初期化後に早期 return します。有効なら fusion 用 scratch を確保し、model tensor ごとの descriptor を構築します（`engine/src/hy4flash/sycl/sy_graph.h:617-620,859-897`）。実行時には対象 sub-stage で条件が揃えば `k_gemv_multi()` を呼び、そうでなければ通常の `lin()`、`swiglu_h()`、必要な `f2h()` を含む個別段階へ進みます（同 `:951-966,1047-1116`）。

この設定は演算のまとめ方を変えます。環境変数による別の値優先順位や CLI による `fuse_dec` の上書きはありません。`--dump` は実行時の融合を抑止しますが、SYCL graph の有効・無効は別設定です。コードから融合有効時と個別経路の生成結果が bit 単位で一致するかは確認できないため、出力同一性はここでは断定しません。

## ログと測定値

`HY4S_FUSE` 自体の値、融合の on/off、descriptor 不成立について専用のログや警告は見つかりません。runner の一般的な初期化ログは `sy_graph.h:629-631` にありますが、そこに `HY4S_FUSE` の状態は含まれません。`docs/DETAILS.md` にこの変数に紐づく測定条件・性能値は確認できなかったため、性能値は記載しません。

## 根拠

- `engine/src/hy4flash/sycl/sy_graph.h:859-897` — 環境値の判定、descriptor 構築条件、fusion scratch。
- `engine/src/hy4flash/sycl/sy_graph.h:951-966,1047-1116` — attention / MLP / MoE での融合経路と fallback。
- `engine/src/hy4flash/sycl/sy_graph.h:489-490,617-627,629-631` — 初期化時期、graph 設定との独立、一般初期化ログ。
- `engine/src/hy4flash/sycl/sy_main.cpp:166,283-296,310-316`、`engine/src/hy4flash/sycl/sy_serve.h:253-277` — CLI / server 実行経路と `--dump`・DFly2 条件。
- `engine/src/hy4flash/sycl/sy_dfly2.h:555-575,583-589,608-640` — DFly2 fusion descriptor と使用経路。
- `engine/src/hy4flash/sycl/build_hy4_sycl.sh:1-5,26-40,64-69` — 対象 SYCL runner の build variant と実行ファイル。
