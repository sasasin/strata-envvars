# `STRATA_METAL_LAZY_FOLD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal backend の複数 token window を commit したとき、保持 prefix の GDN state への fold を commit 内で実行するか、次の window の GPU command graph 冒頭まで遅らせるかを切り替える。既定は遅延実行で、値が文字列 `0` のときだけ遅延を無効にする。これは `Window::commit` の分岐であり、Metal 以外の backend にはこの読み取りはない（`engine/src/core/verify.cpp:4527-4529`, `engine/metal/src/engine/window.cpp:2459-2478`）。

## 値と判定

`Window::commit` 内の関数ローカル `static const bool` が `std::getenv` で値を取得し、設定値全体を `std::string` にして `"0"` と完全一致するか判定する。変換や数値 parse はしない。unset、空文字、`1`、`true`、`false`、`00`、`0anything`、前後に空白のある ` 0` はすべて lazy=true。大文字小文字の変換もない。文字列が正確に `0` の場合だけ lazy=false（`engine/metal/src/engine/window.cpp:2462-2471`）。

| 実行経路 | unset | lazy を無効にする値 | lazy のままになる例 |
|---|---|---|---|
| `STRATA_GPU_METAL` の Metal verifier で `last_T_ > 1` の commit | 有効（遅延 fold） | 完全一致の `0` | 空文字、`1`、`true`、`00`、`0anything` |
| Metal 以外、または `last_T_ <= 1` の commit | この分岐で評価されない | この分岐で評価されない | この分岐で評価されない |

## 有効になる条件

- `STRATA_GPU_METAL` が定義された verifier 経路であること。共通 verifier はその場合に Metal `window_commit` へ委譲し、環境変数の読み取りは Metal `Window::commit` にだけある（`engine/src/core/verify.cpp:4527-4529`, `engine/metal/src/engine/window.cpp:2466`）。
- commit 対象 window の `last_T_` が 1 より大きいこと。この条件の外では環境変数を評価せず、fold の切替も行わない（`engine/metal/src/engine/window.cpp:2460-2467`）。
- 有効値のうち `0` 以外なら遅延が選ばれる。CLI 引数や別の環境変数による上書きはこの判定箇所にはない（`engine/metal/src/engine/window.cpp:2466-2477`）。

## 実行時の詳細

通常の遅延経路では、commit は `n_keep` を `pend_fold_` に記録してから GDN history parity を切り替え、保持 token の PLE history と session の token pair を更新する。直後の window 実行時に pending 数を取り出してクリアし、fold dispatch を次 window の dispatch graph 冒頭に追加して実行する。window の cache key にも pending fold 数が含まれるため、fold の有無・数で異なる graph を使う（`engine/metal/src/engine/window.cpp:1523-1528`, `1566-1569`, `2468-2492`）。

値が正確に `0` なら、commit 内で fold dispatch を作成し `cx_->run_graph` を呼んでから history parity を切り替える（`engine/metal/src/engine/window.cpp:2471-2478`）。遅延中でも次の decode window より先に prompt chunk が走る場合は、その先頭で pending fold を実行してから chunk 処理に進む。checkpoint 保存でも pending fold を flush してから状態を保存する（`engine/metal/src/engine/window.cpp:2354-2362`, `3131-3146`）。

値は `static` 初期化時に一度だけ評価され、初期化は `last_T_ > 1` の commit に初めて到達したときに起きる。その後プロセス内で環境を変更しても切替は反映されない。値を読む専用ログはなく、この設定専用の警告・エラーも見つからなかった。commit の範囲外エラーは `metal window: commit count out of range` を返すが、値の判定とは独立している（`engine/metal/src/engine/window.cpp:2459-2467`）。

## 根拠

- Metal backend への verifier commit 委譲: `engine/src/core/verify.cpp:4527-4529`
- 値判定、pending 設定または即時 fold、history parity と session 状態更新: `engine/metal/src/engine/window.cpp:2459-2493`
- pending fold の次 window graph への組み込みと cache key: `engine/metal/src/engine/window.cpp:1523-1528`, `1566-1569`
- checkpoint save と prompt chunk における pending fold の flush: `engine/metal/src/engine/window.cpp:2354-2362`, `3131-3146`
