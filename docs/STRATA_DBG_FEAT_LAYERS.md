# STRATA_DBG_FEAT_LAYERS

調査対象: Strata main の HEAD 7695859aa13afb248bdb4d36f9b2e95707db079d（2026-10-12 時点）。対象リポジトリは調査開始時に main で、作業ツリーに変更はなかった。外部ライブラリの環境変数は対象外。

## 役割

研究用フック STRATA_DBG_FEAT=<file> が MoE 層・prompt chunk ごとのルーティング ID と重みを出力するとき、追加で router 入力 hidden state（bf16）を記録する層番号を選ぶ。STRATA_DBG_FEAT_LAYERS 自体はダンプを開始しない。STRATA_DBG_FEAT が必要で、これがなければ層リストを使った hidden state の出力も行われない。

このフックは strata_prefill の prompt prefill 経路にあり、decode や別の推論経路に対する設定ではない。値は通常の利用者向け設定ではなく、ソースコメントに RESEARCH HOOK と記された診断・研究用の機能である。

## 値と判定

値全体の妥当性検査はせず、カンマで分割した各要素を std::atoi に渡す。要素の数値変換結果が 0 以上 63 以下なら、その添字のフラグを true にする。重複指定は同じフラグを再度 true にするだけで、範囲外の値は無視される。

| 状態・要素 | 動作 |
|---|---|
| 変数 unset | 3,4,15,16,27,28,39,40 を使う |
| 空文字 | 空のリストとなり、hidden state を記録する層はない |
| カンマ区切りの整数 | 変換値が 0〜63 ならその層を選ぶ |
| 空要素・数値で始まらない要素 | atoi の結果が 0 となり、層 0 を選ぶ（例: 1,,2 や abc） |
| 数字の後ろに文字がある要素 | 数字として読める先頭部分で変換する（例: 12x は 12） |
| 先頭空白・符号 | atoi の変換規則に従う（例: -1 は範囲外、+2 は 2） |
| 変換値が負、または 64 以上 | 無視する |

文字列を真偽値や単一の層番号として解釈するものではない。パーサーは固定長 64 要素の bool 配列を作り、実際の layer l に対して featl[l & 63] を参照する。このため layer 番号が 64 以上のモデルでは 64 周期で同じ選択が適用される。

## 有効になる条件

- MoE 層で router の計算後に実行されるフックに到達する必要がある。
- STRATA_DBG_FEAT または STRATA_DBG_ROUTE_OVERRIDE のどちらかが設定されている場合にだけ、STRATA_DBG_FEAT_LAYERS を parse する。
- hidden state のファイル出力には STRATA_DBG_FEAT が設定され、かつそのパスを fopen(path, "wb") で開ける必要がある。STRATA_DBG_ROUTE_OVERRIDE だけの場合は layer リストが初期化されても、それを使ったファイル出力はしない。
- STRATA_DBG_FEAT と STRATA_DBG_ROUTE_OVERRIDE のどちらも unset ならフックの同期・転送・ファイル処理に入らない。

## 実行時の詳細

STRATA_DBG_FEAT、STRATA_DBG_ROUTE_OVERRIDE はフックの初回実行時に関数内 static として読み取られる。両方が unset ならその時点で処理を抜ける。いずれかが設定されている場合、同じ初回実行で STRATA_DBG_FEAT_LAYERS を一度だけ読み、unset なら既定リストに置き換える。以後の prompt 層・chunk で環境を変更しても再評価されない。

フックが動くたびに CUDA stream を同期する。STRATA_DBG_FEAT のファイルが開けた場合、記録にはまず {layer, position, T, flag} の4個の int32 header、続いて chunk の routed ID と重みを uint16 で書き込む。position は実際の prompt 位置ではなく、l & 63 ごとの static カウンターで、フックを通るたびに T ずつ増える。flag は featl[layer & 63] であり、1 の場合だけ router 入力 m.mixed_bf の T × N 個の bf16 値を追加する。したがって環境変数が決めるのは追加 hidden state を含める層で、routing ID・重みの記録範囲そのものではない。出力ファイルは wb で開くため既存ファイルは切り詰められる。ファイルを開けない場合は ff == nullptr となり、特徴量ダンプは行われない。

実装は fwrite の戻り値を検査せず、書き込み失敗を示す専用ログもない。ソース中の関連 Docs 説明は見つからなかったため、性能や出力の完全性についての測定値は記載しない。

## 根拠

- CMakeLists.txt:586-603 — src/prefill/prefill.cpp を含む strata_prefill ライブラリと strata 実行ファイルの構成。
- src/program/generate.cpp:12460-12489 — prefill の初期化と prompt 入力に対する prefill.run() 呼び出し。
- src/prefill/prefill.cpp:2860-2872 — MoE router の計算後にある研究用フックの説明。
- src/prefill/prefill.cpp:2873-2885 — 関連する2変数の static 読み取り、条件判定、既定リスト、カンマ分割と atoi による選択。
- src/prefill/prefill.cpp:2904-2921 — chunk ごとの同期、header・ID・重み・選択層の hidden state の出力。
- src/prefill/prefill.cpp:2923-2927 — 同じブロック内で行うルーティング上書き。STRATA_DBG_ROUTE_OVERRIDE はこのフックを有効にするもう一つの条件である。
