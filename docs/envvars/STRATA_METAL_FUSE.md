# `STRATA_METAL_FUSE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal の decode window で二つの処理を融合するスイッチ。既定では有効で、GDN step kernel が後段の `xprep` 用データも書き、選択予算内の window では QSA の score と top-k dispatch を省く。`=0` にすると GDN 後の `xprep` を別 dispatch として実行し、QSA の score/top-k を常に実行する。Metal の `Window` がこのフラグを保持し、window の dispatch 列を組み立てる（`engine/metal/src/engine/window.cpp:497-505,1171-1202,1251-1265`）。

## 値と判定

`Window` のメンバー初期化子で `std::getenv` を調べ、設定値全体を `std::string(...) == "0"` で比較する。したがって未設定なら ON、設定されていて値が厳密に `0` の場合だけ OFF。空文字、`00`、`0anything`、`1`、`true`、`false`、前後に空白のある ` 0` はすべて ON になる。数値変換、先頭文字判定、大文字小文字変換は行わない（`engine/metal/src/engine/window.cpp:505`）。

| 条件 | unset | OFF になる値 | ON になる値の例 |
|---|---|---|---|
| Metal `Window` | ON | `0` のみ | 空文字、`00`、`0anything`、`1`、`true`、`false`、` 0` |

## 有効になる条件

- Metal backend の `strata` または `window_probe` が `Window` を生成して decode window を使う場合に適用される。Metal の CMake project は Apple 以外では configure を拒否し、`window.cpp` は `strata_metal_kernels` のソースに含まれる（`engine/metal/CMakeLists.txt:14-20,150-179`）。
- GDN 出力の融合は `fuse_` が ON のときに GDN dispatch の `plane` を非ゼロにし、OFF のときは `xprep` dispatch を追加する（`engine/metal/src/engine/window.cpp:1171-1202`; `engine/metal/kernels/gdn.metal:47-49,167-179`）。
- QSA の score/top-k 省略は、さらに window の終端位置 `pos0 + ntok`（実行側では `pos0 + Tn`）がコンパイル済み `G_BUD` 以下の場合に限る。`G_BUD` は選択 budget で `geo::BUD` に対応し、`geo.h` では geometry の `idx_top_k + 3` と定義される（`engine/metal/src/engine/window.cpp:1251-1265,1516-1521`; `engine/metal/src/engine/geo.h:45`）。予算を超えた window は `STRATA_METAL_FUSE` が ON でも score/top-k を実行する。
- 他の環境変数や CLI 引数による上書き・優先順位はこの変数の読み取り箇所にはない。サーバーか CLI かによる別判定もない。

## 実行時の詳細

環境値は `window_create()` が singleton の `Window` を初めて生成するときに、メンバー初期化で読み取られる。以後は `fuse_` の値を使うため、同一 `Window` の稼働中に環境を変更しても反映されない。`window_destroy()` で破棄されてから再生成された場合は、新しい `Window` の初期化時に再読込される（`engine/metal/src/engine/window.cpp:505,3605-3624`）。

融合 ON の GDN dispatch は `XY_.b` を出力先に渡し、OFF は `yg_` を渡して後続に `xprep` を追加する。kernel は `plane` が非ゼロなら通常の `y` に加えて packed planes を書く（`engine/metal/src/engine/window.cpp:1171-1202`; `engine/metal/kernels/gdn.metal:47-49,165-179`）。QSA では、予算内の場合に `qsa_score` と `qsa_topk2` の dispatch を省き、初期化時に `qids_` に設定された identity cell list を使う。いったん予算外の選択を行った後、再び予算内に戻る経路では `qids_` を identity に戻す（`engine/metal/src/engine/window.cpp:905-906,1243-1265,1516-1521`）。

## ログと測定値

この環境変数を読んだこと、OFF になったこと、または値が無効であることを知らせるログやエラー分岐は見当たらない。`0` 以外はすべて ON として扱われるため、値の parse failure もない（`engine/metal/src/engine/window.cpp:505`）。`docs/MAC.md` は `STRATA_METAL_FUSE=0` を「二つの decode fusion を止める（same tokens, slower）」と説明しているが、調査対象のコードから新たな性能測定値は確認できない（`docs/MAC.md:261-273`）。

## 根拠

- 読み取り・既定判定: `engine/metal/src/engine/window.cpp:497-505`
- Metal build と実行ファイルへの組込み: `engine/metal/CMakeLists.txt:14-20,150-179`
- GDN 融合と fallback dispatch: `engine/metal/src/engine/window.cpp:1171-1202`; `engine/metal/kernels/gdn.metal:47-49,165-179`
- QSA の選択予算、dispatch 省略、identity list の維持: `engine/metal/src/engine/window.cpp:905-906,1243-1265,1516-1521`; `engine/metal/src/engine/geo.h:45`
- 読み取り時期と singleton の生成・破棄: `engine/metal/src/engine/window.cpp:3605-3624`
- ソース説明との照合: `docs/MAC.md:261-273`
