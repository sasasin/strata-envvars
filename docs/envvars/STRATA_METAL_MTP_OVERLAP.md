# `STRATA_METAL_MTP_OVERLAP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Metal backend の MTP prompt prefill で、各 prompt chunk の drafter K/V 計算を非同期に投入し、次の chunk の通常処理と重ねます。無効時は drafter K/V の計算完了を待つ同期経路になります。これは prompt prefill の overlap であり、MTP の draft token を決める処理や通常の decode window の計算方法を切り替える変数ではありません。

## 値と判定

`Window` のメンバー初期化時に `std::getenv` の結果を文字列全体で `"0"` と比較します。数値 parse はせず、値が設定されているかだけで有効化する判定でもありません。

| 値 | `mtp_ovl_` |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 有効 |
| 文字列がちょうど `0` | 無効 |
| `00`、`0anything`、`false`、` 0`、その他の文字列 | 有効 |

空白除去、大文字小文字変換、数値としての妥当性検査はありません。CLI 引数による上書きはありません。`STRATA_METAL_PROMPT` などは prompt 実行経路を選びますが、この値そのものを上書きしません。

根拠: `metal/src/engine/window.cpp:570-575`。

## 有効になる条件

この実装は `STRATA_GPU_METAL` のビルドで使う Metal window のコードです。overlap 実行には、さらに次の条件が必要です。

- MTP が使用され、prompt chunk ごとに drafter の K/V prefill が呼ばれること。Metal では `Prefill::draft_kv` は常に「Metal window が draft layer を処理する」として decline し、その後 `mtp.prefill` に進みます。
- prompt が `Window::prompt` の chunk 経路を通り、chunk callback が呼ばれること。`STRATA_METAL_PROMPT=window`、streaming 経路、または通常 prompt の最小行数未満では、この `Window::prompt` 経路になりません。
- `mtp_ovl_` が有効で、MTP がロード済みであること。前者が有効な場合に限り prompt buffer の `R2` が確保されます。
- MTP prefill が `pb_.R` をソースとして使い、`mrope_on()` が false であること。

上記以外はこの変数による非同期実行になりません。特に M-RoPE の prompt は `cx_->run_graph(ds)` の同期実行に進みます。MTP を使わない場合にも効果はありません。

根拠: `src/prefill/prefill.cpp:2134-2140,7682-7690`; `src/program/generate.cpp:19339-19350`; `metal/src/engine/window.cpp:3391-3422,2538-2559`; `metal/src/engine/prompt_chain.inc:437-459`。

## 実行時の詳細

判定値は `Window` インスタンスの `mtp_ovl_` メンバーに保存されます。Metal window はプロセス内で必要になったとき一度作られる singleton なので、通常は window 作成時に読み取られ、その window の存続中は環境変数を変更しても反映されません。window を破棄して再作成すれば再評価されます。根拠: `metal/src/engine/window.cpp:573,3252-3271`。

適用対象の prompt chunk では、MTP prefill の dispatch を `run_graph_async` で第 2 command queue に submit します。次の prompt chunk は別の residual buffer (`pb_.R2`) を使って通常処理を進めます。drafter の cache と scratch は共有するため、次の MTP prefill を始める前に前 chunk の処理を `mtp_wait()` で待ちます。prompt の終了時または途中 return 時も `MtpJoin` の destructor が残った非同期処理を待ちます。無効時や条件不成立時は同じ dispatch を `run_graph` で同期実行します。

この環境変数専用の警告・ログはありません。`STRATA_METAL_TRACE` または `STRATA_METAL_PROFILE` が有効なら prompt の計時行に drafter rows の所要時間が含まれます。Metal command buffer が失敗した場合は、待機時に `mtl: command buffer failed: ...` を stderr に出して終了コード 5 で終了します。これは async queue の一般的な command buffer 失敗処理で、環境変数固有のエラーではありません。

根拠: `metal/src/engine/window.cpp:573-575,2540-2559`; `metal/src/engine/prompt_chain.inc:49-70,437-464`; `metal/src/mtl_rt.mm:1022-1047`。

## 根拠

- 候補名の実参照は `metal/src/engine/window.cpp:573` の `std::getenv` のみです。同ファイル `:572` のコメントは値の意味を説明しますが、判定の根拠は `:573` の式です。
- Metal MTP prefill は `src/core/mtp.cpp:1564-1569` から `strata::metal_engine::mtp_prefill` に接続され、`metal/src/engine/window.cpp:3424-3426` から `Window::mtp_prefill` に委譲されます。
- `STRATA_METAL_MTP_OVERLAP` について性能測定値は記載していません。
