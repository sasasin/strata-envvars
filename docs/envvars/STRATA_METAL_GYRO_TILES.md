# `STRATA_METAL_GYRO_TILES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal engine の `Window::gemv` が Gyro 判定済みモデルの複数 token window を処理するとき、条件に合う dense weight GEMV のタイル設定を Gyro 向けに変更する最適化を有効にする。未設定を含め既定で有効で、`=0` はこのタイル変更を止める。変数はモデル選択や Gyro の expert 処理そのものを切り替えるものではない。Gyro 判定はモデルの `blk.0.ffn_gate_exps.weight` tensor type が `144` 以上かで設定される（`engine/metal/src/engine/window.cpp:789`）。

## 値と判定

関数内 `static const bool` の初回評価で `std::getenv` を調べ、変数が存在し、値全体が文字列 `"0"` と等しい場合に限って false になる。未設定、空文字、`1`、`true`、`false`、`00`、`0anything`、前後に空白のある ` 0` はいずれも `"0"` と一致せず true。数値変換、trim、大文字小文字変換はしない。`getenv` の null 判定と `std::string` の完全一致である（`engine/metal/src/engine/window.cpp:1027`）。

| 条件 | unset | タイル変更を有効にする設定値 | タイル変更を無効にする値 |
|---|---|---|---|
| Metal engine の GEMV | 有効 | 空文字、`1`、`true`、`00`、`0anything`、` 0` など `"0"` 以外 | `0` のみ |

## 有効になる条件

- Metal engine の `Window::gemv` を通ること。読み取りはこの Metal 実装にあり、他の backend の GEMV にはこの分岐はない（`engine/metal/src/engine/window.cpp:1-3,1019-1028`）。
- `blk.0.ffn_gate_exps.weight` が存在し、その tensor type が `144` 以上で Gyro dense 判定が有効になること（`engine/metal/src/engine/window.cpp:789`）。
- GEMV window の `ntok` が `2` 以上であること。1 token ではこの変数による tile override は適用しない（`engine/metal/src/engine/window.cpp:1028`）。
- 条件を満たしても、追加変更は `Q5_K` かつ `n_in == 2560 && n_out >= 6144`、`Q5_K` かつ `n_in == 6144`、または `Q8_0` かつ `n_in == 640` の場合だけ。ほかの tensor type / shape（`Q6_K` を含む）では、この分岐による上書きはない（`engine/metal/src/engine/window.cpp:1032-1034`）。
- `STRATA_METAL_GEMV_NR` はこの処理の後に評価される。`ntok > 1`、その値を `atoi` した結果が `2`、かつ `n_out >= 2048` なら `Rr`、`S`、`K` をさらに変更しうる。したがって最終 tile はこの別設定との組合せで決まる（`engine/metal/src/engine/window.cpp:1036-1044`）。

## 実行時の詳細

`Window::gemv` は tensor の shape と type から標準の `L/Rr/S/K` を選び、その後この設定と Gyro 条件に合う場合に限って tile parameters を上書きする。Gyro override は上記の Q5_K shape で `L=2, Rr=1, S=4, K=1`、Q8_0 shape で `L=4, Rr=2, S=4, K=1` を選ぶ。その値から `gemv[_16]_<type>_<L>_<Rr>_<S>_<K>` pipeline 名、出力 grid、threadgroup 数が決まって dispatch に積まれる（`engine/metal/src/engine/window.cpp:1021-1061`）。タイルは lane sums の順序を変えるとソースコメントにあるため、数値結果が従来と同一とは断定できない（同:1029-1034）。この環境変数を読む箇所では重み・入力を別形式へ変換していない。

環境変数は `Window::gemv` 内の関数ローカル `static` として初回 GEMV 呼び出し時に一度読み、以降の呼び出しは保存値を使う。プロセス起動後でも初回読み取り前なら値を参照するが、初回評価後の環境変更は反映されない。window dispatch graph も同じ shape の cache hit 時に再利用される（`engine/metal/src/engine/window.cpp:1027,1523-1558,1561-1576`）。CLI 引数や別設定によるこの変数自体の上書きはコード上見つからない。`STRATA_METAL_GEMV_NR` の追加調整は前節のとおり。

## ログと測定値

この変数の評価結果や選択 tile を知らせる専用ログ、警告、エラーは見当たらない。ソースコメントには、`gemv_parity --one` の M4・2 token 条件で、Q5_K `2560→10240` が tile `(16,1,4,1)` の `261 us` から `(2,1,4,1)` の `210 us`、ほか `2560→6144` が `158→129 us`、`6144→2560` が `162→139 us`、`2560→12288` が `313→247 us`、共有 down Q8_0 `640→2560` が `(4,2,4,1)` で `36→19 us` と記録されている（`engine/metal/src/engine/window.cpp:1029-1034`）。これはソースコメントの測定記録であり、モデル名、OS、反復回数などはそこに記載されていないため、他条件の性能や出力一致を示す値としては扱えない。

## 根拠

- `engine/metal/src/engine/window.cpp:789` — Gyro dense 判定に使う tensor と type 条件。
- `engine/metal/src/engine/window.cpp:1019-1061` — GEMV 標準 tile、環境変数判定、適用 shape、pipeline と dispatch の組み立て。
- `engine/metal/src/engine/window.cpp:1523-1558,1561-1576` — dispatch graph の cache hit / 作成経路。
