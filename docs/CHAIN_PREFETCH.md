# CHAIN_PREFETCH

調査対象: Strata main の HEAD 477ac13cbe8e582c20484871ce459d20d82df09d（2026-10-17 時点）。

## 役割

この名前を環境変数として読むのは、Metal の単一 decode step 計測プログラム metal/tests/token_chain.cpp だけです。設定されていると、次の HC read で使う重み範囲を slc_touch dispatch で先に読み、後続の計測 dispatch 列に加えます。Strata の通常の engine / server 実行で使う設定ではありません。

## 値と判定

| 状態 | 結果 |
|---|---|
| 未設定 | prefetch を追加しない |
| 空文字を含む任意の設定値 | prefetch を追加する |

std::getenv("CHAIN_PREFETCH") != nullptr だけで判定し、値を文字列・数値として parse しません。そのため CHAIN_PREFETCH=0 も有効です。main() の引数処理より前に一度読み、実行中の再読み取りはありません（metal/tests/token_chain.cpp:59-83,178-180）。

## 有効になる条件

- Metal テスト用 token_chain が実行されること。ソース冒頭に記された用途は、GGUF の実重みを使って Metal kernel の1 decode step を計時することです。活性値は合成値で、数値検証ではありません（metal/tests/token_chain.cpp:1-8）。
- gr_read() が final read ではない場合に、次の read の _down, _inject, _up tensor 範囲（最終 output_hc の場合は _down, _up）を pending に積みます。--only や --skip の絞り込みで dispatch が除外される場合、共通 push() が ds に追加しません（metal/tests/token_chain.cpp:162-170,360-381）。
- 後続の gemv2() が呼ばれた時、pending が空でなければ push_prefetch() が範囲ごとに slc_touch dispatch を追加して pending を空にします（metal/tests/token_chain.cpp:194-206,207-230）。

この変数はビルド時の Metal backend 選択や通常の Strata CLI/server 動作を切り替えません。HEAD 全体の完全一致検索では、このテストプログラム以外に CHAIN_PREFETCH の参照はありません。テスト専用コードは製品動作の根拠から除外するという調査範囲に従い、以下の dispatch 挙動を通常の Strata engine に一般化しません。

## 実行時の詳細

push_prefetch() は各範囲の byte 数を16で割った語数を n16 として slc_touch に渡し、256 thread の threadgroup と (n16 + 1023) / 1024 の grid を設定します。Metal kernel は範囲から uint4 を読み、4要素の XOR を計算します。XOR が 0x9e3779b9u と一致した場合だけ sink に書き込みます。kernel コメントは、次の kernel が使う重みを SLC に置く目的と記しています（metal/tests/token_chain.cpp:194-205; metal/kernels/glue.metal:49-63）。

計測プログラムは command dispatch 数と weight/state bytes を出し、実行時間を計測します。prefetch を有効にすると、その dispatch は prefetch class として追加され、各範囲の byte 数も集計に加算されます（metal/tests/token_chain.cpp:194-205,646-659）。HEAD の docs/DETAILS.md にこの環境変数の説明や測定結果は見当たりません。性能向上や通常推論の出力への影響は、このコードからは確認できません。

## 根拠

- metal/tests/token_chain.cpp:1-8,59-83,178-180 — テスト計測プログラムの目的、設定有無の判定と評価時期。
- metal/tests/token_chain.cpp:162-170,194-230,360-381,646-659 — prefetch 対象範囲の選択、dispatch 登録と計測集計。
- metal/kernels/glue.metal:49-63 — slc_touch kernel の読み取り処理。
- HEAD での完全一致検索 — 参照は metal/tests/token_chain.cpp:180 のみ。docs/DETAILS.md に CHAIN_PREFETCH 固有の説明なし。
