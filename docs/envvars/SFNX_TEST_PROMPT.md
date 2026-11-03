# `SFNX_TEST_PROMPT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

sFNX サーバーの測定用入力差し替えです。設定すると、画像を含まない各 `GEN` / `BGEN` テキスト要求で、要求本文の token ID 列を指定ファイル内の token ID 列に差し替えます。起動時に別変数 `SFNX_TEST_PROMPT_CONFIRM=1` が同時に設定されていなければ sFNX は起動を拒否します。通常の Strata エンジン全般ではなく、`src/split/tools/sfnx.cpp` の sFNX 実行ファイルだけに実装されています（`src/split/tools/sfnx.cpp:299-323,1015-1025`）。

## 値と判定

| 状態 | 動作 |
|---|---|
| `SFNX_TEST_PROMPT` 未設定 | 起動時検査を通過し、要求 token の差し替えもしません。 |
| 空文字を設定 | 設定済みとして起動時の確認を要求します。確認値が正しければ各テキスト要求で空のパスを開こうとし、`cannot open ` の要求エラーになります。 |
| 空でないパス、確認変数が未設定または値が `1` 以外 | 起動時に拒否します。 |
| 空でないパス、確認値が文字列として厳密に `1` | 起動し、各テキスト要求でそのパスを読みます。 |

確認値は `std::string(ok) != "1"` で比較されるため、`01`, `1 `, `true`, 空文字などは受け付けません（`src/split/tools/sfnx.cpp:1017-1024`）。パス文字列自体の trim、展開、別名解決はこの処理では行わず、そのまま `fopen(tp, "rb")` に渡します（同 `:301-303`）。

ファイルは、コード上では `uint32_t` を読み、その値分だけ seek し、続けて `uint32_t`、`int64_t` を読みます。先頭部分の読み取りと seek が成功し、token 数が `1..0x7fffffff` の場合にヘッダーを受け付け、その後に token 数分の `float` が読み取れることを要求します。各 float は `0 <= x < vocab` かつ `(int)x` に変換して戻した値と等しい場合だけ token ID として受け付けます。全体ファイル長の一致や、2つ目の `uint32_t` の内容は検査していません。これはこの箇所で確認できる検査内容であり、別形式仕様の主張ではありません（同 `:304-320`）。

- 開けない場合: `SFNX_TEST_PROMPT: cannot open <path>`。
- ヘッダー読取失敗、seek 失敗、token 数が範囲外: `SFNX_TEST_PROMPT: <path> has no valid tokens header`。
- 指定 token 数分の float を読めない場合: `SFNX_TEST_PROMPT: short file`。
- 語彙範囲外または整数でない float: `SFNX_TEST_PROMPT: <path> holds a value that is not a token id`。

根拠: `src/split/tools/sfnx.cpp:301-320`。

## 有効になる条件

- sFNX の `--serve` 実行経路であること。`main()` が引数を処理した後、モデル読み込みより前に確認変数を検査します（`src/split/tools/sfnx.cpp:72-104,1040-1058`）。通常の Strata サーバーや `fnx_run` に同じ処理は見つかりません。
- `SFNX_TEST_PROMPT` が設定されている場合、起動には `SFNX_TEST_PROMPT_CONFIRM` の厳密な値 `1` が必要です。確認値は起動時に一度検査され、欠落または不一致なら stderr に理由を出して終了コード 2 で終了します（同 `:1040-1049`）。
- 画像要求 `GENI` / `BGENI` は置換対象外です。要求パーサーは画像添付を先に処理し、`images` が false の場合にのみファイルを開きます。テキスト要求の `GEN` / `BGEN` は batch の有無にかかわらず対象です（同 `:222,298-303,975-990`）。
- 設定を受け付けてもファイル読み込みは要求ごとです。値を静的 cache する処理はありません。起動時に確認が済んだ後、実行中のプロセス内で `SFNX_TEST_PROMPT` が変更された場合、後続要求はその時点の値を再読します（同 `:301-303,1017-1025`）。
- sFNX の要求行にも CLI 引数にも、この変数より優先する prompt 指定はありません。テキスト要求では元の token ID 列も先にパース・語彙範囲検査され、その後、読み込んだ列で置換されます。置換後の長さは `max_new` と合わせて context 制限に照合されます（同 `:292-298,301-324,988-995`）。

OS/backend/build macro による別判定はこの実装箇所にはありません。sFNX エンジン自体の起動条件や選択条件はこの環境変数の値判定とは別です。

## 実行時の詳細

起動時の `check_test_prompt()` は、変数が未設定なら何もせず戻ります。設定済みなら確認変数を調べ、確認が正しければ stderr に `sfnx: SFNX_TEST_PROMPT: every text request reads <path> instead of its own tokens` を出します。確認が不足している場合は `SFNX_TEST_PROMPT=<path> replaces every text request's tokens (measurements only): set SFNX_TEST_PROMPT_CONFIRM=1 beside it, or unset it` という例外を投げ、`main()` が `sfnx: ` を付けて stderr に出し、モデル読み込み前に終了コード 2 を返します（`src/split/tools/sfnx.cpp:1017-1049`）。

各 `GEN` / `BGEN` では `parse_gen()` が環境値を読み、ファイルを開いて token 列を読み取ります。成功するとクライアント要求の `r.ids` を消去してファイル内 token に置き換え、stderr に `sfnx: SFNX_TEST_PROMPT: the request reads <path> (<count> tokens) instead` を出します（同 `:301-324`）。ファイル由来の例外は要求ループで捕捉され、標準出力のプロトコル応答 `ERR <理由>` となり、その要求を処理せず次の要求へ進みます（同 `:58-63,988-998`）。

## 根拠

- 変数の全参照と要求への差し替え、ファイル検証、要求ごとのログ: `src/split/tools/sfnx.cpp:299-324`。
- 確認変数の起動時検査と警告: `src/split/tools/sfnx.cpp:1015-1025`。
- 起動前の失敗と終了コード: `src/split/tools/sfnx.cpp:1040-1049`。
- 要求種別、画像要求の分岐、要求エラー応答: `src/split/tools/sfnx.cpp:58-63,975-998`。
- sFNX が個別の split engine である説明: `docs/SPLIT_ENGINE.md:1-5`。
