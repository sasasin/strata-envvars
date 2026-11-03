# `STRATA_METAL_NFCHECK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Metal engine の window 完了時に、head window の logits を走査して非有限値（NaN / ±infinity）を数え、有限値の最大絶対値を集計する診断用フックです。ソースコメントでは test tooling 用とされています。結果は stderr に出力されますが、この検査は logits や token を書き換えず、非有限値を検出しても失敗扱いにしません。

## 値と判定

数値や文字列の parse はなく、`std::getenv()` が null かどうかだけを判定します。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む、何らかの値が設定済み | 有効 |

`1` はコメント上の例ですが、`0`、`false` なども設定されていれば同じく有効です。値の範囲、大小文字、前後空白は検査されません。`Window::finish()` 内の `static const bool` に初回評価結果を保持するため、プロセス内でこの関数が最初に呼ばれた後の環境変更は反映されません。初回呼び出しが `head == false` の場合も、その呼び出しで値を読み取ります。

根拠: `metal/src/engine/window.cpp:1790-1794`。

## 有効になる条件

- Metal engine の通常の `Window::run()` が正常に window を完了し、`rows_` が false であること。`run()` はキャッシュ hit / miss のどちらでも `finish()` を呼びますが、`rows_` が true の経路は `finish_rows()` を呼びます。
- その `finish()` 呼び出しで `head == true` であること。値判定自体は先に行われますが、`head == false` なら走査・カウンター更新・NFCHECK ログは行いません。

window サイズや context 範囲の検査、PLE table gather、stream arena 初期化など `run()` 内で失敗して `false` を返す経路では `finish()` に到達せず、この検査も実行されません。この変数を読む箇所には追加の OS / build macro / CLI 引数 / 他環境変数条件はありません。Metal engine のコード経路に限られます。

根拠: `metal/src/engine/window.cpp:1346-1350,1370,1411-1413,1468-1494,1792-1794`。

## 実行時の詳細

`finish()` は head window ごとに `lm_` の各 token 行・各 vocabulary 要素を調べます。`std::isfinite()` が false の要素数を window ごとに数え、有限値については累積の `maxabs` を更新します。非有限値がある window は、該当する最初の5 window まで、stderr に `strata metal: NFCHECK non-finite logits: ...` と件数・window token 数・位置を出します。head window の累積件数は、500 window ごと（5000 window を含む）に stderr の `strata metal: NFCHECK ... largest |logit| ...` 行へ出ます。

集計変数は関数内 static なので window 間で累積し、リセット処理はこの箇所にありません。検査は `finish()` の token 出力処理より前ですが、走査結果で `out`、`tokout_`、`lm_` を変更せず、`finish()` の戻り値も通常どおり true です。したがって、観測できる影響は計算量の追加と上記 stderr 出力です。`run()` が先行段階で失敗する場合は NFCHECK のログは出ません。

根拠: `metal/src/engine/window.cpp:1792-1818`。

## 根拠

- 環境変数の読み取り、head 条件、static カウンター、logits 走査と出力: `metal/src/engine/window.cpp:1790-1813`。
- `finish()` の完了処理と戻り値: `metal/src/engine/window.cpp:1777-1780,1815-1833`。
- `Window::run()` の範囲チェック・早期失敗と、通常／batch rows 完了経路の分岐: `metal/src/engine/window.cpp:1346-1350,1411-1413,1491-1494`。
- 対象名の全リポジトリ参照を検索した結果、実読み取りは `metal/src/engine/window.cpp:1792` の1箇所です。ほかの参照は同ファイルの説明コメントと、この処理の stderr 文字列です。
