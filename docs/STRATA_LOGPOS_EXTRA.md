# `STRATA_LOGPOS_EXTRA`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_LOGPOS` が有効な verify-window の測定出力に、追加で記録する語彙 ID を指定します。各行には、実際の次トークンの log-probability に加え、この追加 ID の log-probability と、その ID を語彙から除外して再正規化した実際の次トークンの log-probability が出力されます。値がプロンプト処理や生成時の token 選択を変える分岐はありません。

## 値と判定

| 値 | 扱い |
|---|---|
| 未設定 | `248046` を使用。実装コメントはこの ID を `<|im_end|>` と記載している。 |
| 設定あり | `std::atoi` の戻り値を `int32_t` に変換して使用。整数全体の厳密な検証はしない。 |
| 空文字、数字で始まらない文字列 | `atoi` の結果は `0`。 |
| 数字の後ろに文字がある文字列 | 数字として読める先頭部分を使い、後続文字は無視する（例: `123tail` は `123`）。先頭の空白や符号も `atoi` の規則に従う。 |
| 負数またはモデルの語彙範囲外 | ID の範囲チェックで追加 token は適用されず、追加 log-probability と除外後 log-probability の列は `nan` になる。 |

数値変換のオーバーフロー値に対する `atoi` の結果はコードで定義・検査されていません。語彙範囲内の値かを設定時に検証したり、fallback したりする処理もありません。

## 有効になる条件

`STRATA_LOGPOS_EXTRA` 単独では出力を有効にしません。`STRATA_LOGPOS` が設定され、その値で `fopen(path, "ab")` が成功して `logpos` が開けた場合にだけ `window_logprobs()` が呼ばれます。`STRATA_LOGPOS` が未設定、またはパスが空・無効などでファイルを開けなければ、追加 ID を含むログ出力は行われません。open 失敗自体を知らせる専用ログはこの箇所にはありません。

パイプラインの prompt verify 経路では、`STRATA_LOGPOS` が設定されていると並列の `read_windows_pl()` 経路を避け、通常の verify-window loop に進みます。空文字や開けないパスでも環境変数が設定済みならこの分岐判定は同じですが、ログ出力関数は `logpos != nullptr` のときだけ呼ばれます。`STRATA_LOGPOS_EXTRA` はこのパイプライン経路の選択には使われません。

## 実行時の詳細

CUDA/HIP と SYCL の `generate.cpp` は、verify-window loop 内の関数ローカル `static const int32_t` として値を初回評価時に取得します。したがって、最初の該当 window の評価後にプロセス環境を書き換えても再読込されません。読み取り自体は `STRATA_LOGPOS` のファイルが開けたかどうかにかかわらず static 初期化箇所に到達すれば行われますが、値が結果に反映されるのはファイルが開けて `window_logprobs()` が実行される場合だけです。

`window_logprobs()` は各 window の head logits をホスト側へコピーし、各行について全語彙の log-sum-exp を計算します。出力はタブ区切りで、基本列は `pos`, `target`, `logprob`, `top`, `top_logprob`, `hit`, `extra_logprob`, `target_logprob_without_extra` です。`extra_logprob` は指定 ID の確率、`target_logprob_without_extra` はその ID を除いた語彙上で target を再正規化した確率です。target 自体が追加 ID の場合、除外後の target 確率は `nan` になります。各 window の後に出力を flush します。

追加 ID が語彙範囲内であるかの確認は各行の出力時に行います。設定値が不正でも処理を終了させる専用エラーはなく、無効 ID なら追加関連列が `nan` になります。一方、head logits がない場合や CUDA のコピーに失敗した場合には `window_logprobs: no head logits for this window` または `window_logprobs: the head logits copy failed` がエラー文字列に設定され、呼び出し元の prompt 処理が失敗します。SYCL 版では SYCL 例外を `window_logprobs: <例外内容>` に変換します。

## 文書との照合

`docs/UNSLOTH_Q4.md` は `STRATA_LOGPOS` と `STRATA_LOGPOS_TOPK` を使った verify-window の比較測定を説明していますが、`STRATA_LOGPOS_EXTRA` の値や列の説明は見つかりませんでした。したがって、この文書の値判定と出力列の説明は HEAD の実装に基づきます。性能・正確性の測定値は本変数について記載されていません。

## 根拠

- `src/program/generate.cpp:10648-10650,10679-10693`: パイプライン経路の選択、`STRATA_LOGPOS` ファイルを開く処理、`STRATA_LOGPOS_EXTRA` の既定値・変換、ログ関数呼び出し。
- `sycl/src/program/generate.cpp:9964-9966,9989-10003`: SYCL 実装の同等箇所。
- `include/strata/core/verify.hpp:278-285`: `window_logprobs()` の出力列と layer split 時の転送についての宣言コメント。
- `src/core/verify.cpp:2438-2491`: CUDA/HIP 側の語彙範囲判定、log-probability 計算、列出力と flush。
- `sycl/src/core/verify.cpp:2558-2612`: SYCL 側の対応処理と例外変換。
- `docs/UNSLOTH_Q4.md:192-198,224-226`: `STRATA_LOGPOS` による測定方法の説明。
