# `STRATA_METAL_LOGPOS`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal engine の decode window が得た logits から、次の連続した window の先頭 token の対数確率と、その時点の top 64 token の対数確率をファイルに追記する診断・テスト用フックです。ソースコメントでは KL harness の行形式に合わせた test tooling とされています。通常の生成設定を選ぶための変数ではありません。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | 出力しない。 |
| 設定済みの任意の文字列 | 文字列をパスとして使用する。数値や特定文字列の parse はしない。空文字も「設定済み」だが、空パスへの `fopen` が失敗するため出力されない。 |

`std::getenv` の結果を `Window::logpos` 内の `static const char*` に初回呼び出し時に保存します。そのため、その読み取り後に環境を変更してもパスは再取得されません。各 `Window` は最初の出力対象呼び出し時に `fopen(path, "ab")` し、同じファイルを追記モードで使います。ファイルを開けなかった場合は何も出力せず、エラーもログしません。

## 有効になる条件

- Metal backend の `Window::finish` から呼ばれる `Window::logpos` が実行されること。
- `STRATA_METAL_LOGPOS` が設定されていること。
- その window の `head` が true であること。`STRATA_METAL_LOGPOS` 自体は `head` を有効にしません。Metal の `window_run` は別変数 `STRATA_LOGPOS` が設定されていれば全 window で `head` を強制します（ここでも値の内容ではなく設定の有無を見ます）。
- ログ対象として保存する logits は `Tn == 1` の window に限られます。head が true でも複数 token の window は logits 行を保存しません。

このため、`STRATA_METAL_LOGPOS` だけを設定しても、呼び出し元が `head=false` の経路では出力されません。prompt の複数 token window もこの変数では記録対象になりません。

## 実行時の詳細

1-token かつ head 有効の window で、`lm_` の語彙全体の logits をコピーし、log-sum-exp、argmax、logit 上位64件を保存して次回出力用に保留します。次の head 有効 window があり、その `pos0` が保留中の位置のちょうど1つ後なら、次 window の `tokens[0]` を target として1行を書きます。行はタブ区切りで、位置（最初に記録した位置からの相対値）、target token ID、target の log probability、argmax ID、固定の4個のゼロ、続いて上位64件の `token_id:log_probability` です。対数確率は logits から計算し、小数点以下6桁で出力します。各行の後に改行と `fflush` を行います。

次の head window が連続位置でない場合、保留中の logits 行は出力されず、新しい保留値に置き換えられます。最後の window の保留値は、後続 window が来ない限り出力されません。ファイルは `Window` の破棄時に閉じられます。

## 根拠

- `metal/src/engine/window.cpp:304-314`: test tooling と出力内容の意図、保持状態とメソッド宣言。
- `metal/src/engine/window.cpp:1223-1255`: 環境変数の読み取り、追記 open、連続位置判定、1-token 条件、logits からの log-probability/top 64 計算、行出力と flush。
- `metal/src/engine/window.cpp:1302-1304,1319-1330`: window 破棄時のファイル close と finish からの呼び出し。
- `metal/src/engine/window.cpp:2491-2495`: `STRATA_LOGPOS` の設定有無で head を強制する処理。

対象ソース中にこの変数を説明する別の設計資料は見つかりませんでした。用途と形式の説明は実装コメントおよびコードに基づきます。
