# `FNX_PF_SEQ_START`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

sFNX の CUDA/HIP split engine が prompt ring と attention exchange で使う sequence counter の初期値を指定する、テスト用フックです。`prefill_alloc()` の最後で全カードの `p.seq` と `p.att_seq[0..1]` をこの値に設定します。各 ring sum / attention exchange は counter を増やした値を同期 flag の番号として使います。通常は 0 から始まります。値を変えると同期番号の開始位置だけが変わり、prompt の計算内容を選ぶ設定ではありません（`engine/src/split/src/prefill.cu:724-725`, `775-776`, `832-852`, `1226-1229`; `engine/src/split/src/engine.hpp:258-263`）。

この読み取りは `strata-split-*` の CUDA/HIP build が含む `prefill.cu` にあります。CMake は同じ engine source を CUDA または HIP として各 split target に組み込みます（`engine/src/split/CMakeLists.txt:76-92`, `120-143`）。コードコメントも「(a test)」と位置付けています（`engine/src/split/src/engine.hpp:258-263`）。

## 値と判定

`env_int("FNX_PF_SEQ_START", 0)` が環境変数を読みます。`env_int` は unset の場合だけ既定値を返し、設定時は符号付き十進整数全体を `strtoll` で読みます。未設定なら `0`、空文字や整数でない文字列なら `FNX_PF_SEQ_START: '<値>' is not a whole number` の例外です。任意の `+` / `-` と数字のみを許し、先頭・末尾の空白、数字の後ろの文字（例 `0anything`）、空文字、`+` / `-` 単独は拒否します。`long long` に収まらない値も parse エラーです（`engine/src/split/src/env.hpp:15-21`, `33-40`）。

| 条件 | unset | 有効値 | 無効値 |
|---|---:|---|---|
| split engine の CUDA/HIP build | `0` | `0..4294967295`（両端を含む整数。例: `0`, `+1`, `4294967295`） | parse できない値は上記の整数エラー。parse できても負値または `4294967296` 以上は `FNX_PF_SEQ_START: want 0..4294967295, got <値>` の範囲エラー（`engine/src/split/src/prefill.cu:1226-1229`） |

数値は全体を検査し、基数は 10、大文字小文字の区別はありません。`true` / `false` は整数ではないため無効です。範囲検査後に `unsigned` に変換します（`engine/src/split/src/env.hpp:15-21`, `engine/src/split/src/prefill.cu:1226-1229`）。

## 有効になる条件

- sFNX split engine の `Engine` が構築され、prompt path の `prefill_alloc()` に到達すること。engine constructor はこの関数を呼びます（`engine/src/split/src/engine.cu:317-318`）。
- 値が範囲内であること。範囲外や整数として不正な設定は初期化を例外で中断します（`engine/src/split/src/prefill.cu:1226-1229`）。
- 対象コードでは CUDA/HIP のどちらにも読み取りがあります。サーバーか CLI か、モデルの状態、カード数による別の値判定はありません（`engine/src/split/CMakeLists.txt:76-92`, `120-143`; `engine/src/split/src/prefill.cu:1226-1229`）。別の CLI 引数や環境変数による上書きもこの読み取り経路にはありません。
- `0x80000000` 以上も設定値としての範囲内ですが、次の `prefill()` 冒頭で counter が `PF_SEQ_RESET` 以上と判定されると、フラグをクリアして counter を 0 に戻します。その経路では指定値からの開始は最初の prompt read 前にリセットされます（`engine/src/split/src/engine.hpp:258-263`; `engine/src/split/src/prefill.cu:1300-1306`）。

## 実行時の詳細

値は `Engine` ごとに `prefill_alloc()` の実行中に一度読み取られ、全カードの ring sum counter `p.seq` と attention counter `p.att_seq[0]`, `p.att_seq[1]` の初期値になります。ring sum と attention exchange はそれぞれ `++p.seq` を同期 flag の sequence として使います（`engine/src/split/src/prefill.cu:724-725`, `775-776`, `832-852`, `1226-1229`）。環境変数を Engine 作成後に変更しても、その Engine の counter には反映されません。新しい Engine の作成時にはその時点の環境を読みます。

初期化時には各カードを同期し、ring flags と attention flags をゼロにしてから全カードの counter を設定します（HIP では small-chunk sum flags もクリアします）。`prefill()` は各呼び出しの冒頭で `p.seq >= 1u << 31` を確認し、該当時は stderr にリセット理由を出して `pf_seq_reset(0)` を行います（`engine/src/split/src/prefill.cu:832-852`, `1300-1306`）。このため高い開始値は有効値として受理されても、最初の prompt read で通常の 0 開始に戻る場合があります。

## ログと測定値

正常な初期化値を設定しただけでは、この変数専用の成功ログはありません。整数 parse エラーと範囲エラーは例外文言を持ちます（`engine/src/split/src/env.hpp:33-40`; `engine/src/split/src/prefill.cu:1226-1229`）。prompt counter が `1u << 31` 以上になった後の `prefill()` では stderr に `fnx: prompt ring sequence numbers at %u: flags zeroed, numbers from 0 again` と出して 0 にリセットします（`engine/src/split/src/prefill.cu:1300-1306`）。

`sfnx` の Engine 初期化中に例外が起きた場合、stdout に `ERR <例外文言>`、stderr に `sfnx: failed: <例外文言>` を出して終了コード 1 で終了します（`engine/src/split/tools/sfnx.cpp:1097-1102`, `1123-1136`）。

## 根拠

- 候補名の唯一の実コード読み取り、範囲判定、counter 初期化: `engine/src/split/src/prefill.cu:1226-1229`
- 整数 parse と unset / 空文字処理: `engine/src/split/src/env.hpp:15-21`, `33-40`
- flags のクリアと counter 設定: `engine/src/split/src/prefill.cu:832-852`
- ring / attention exchange の sequence 使用と overflow reset: `engine/src/split/src/prefill.cu:724-725`, `775-776`, `1300-1306`
- prompt path の初期化時期と build 対象: `engine/src/split/src/engine.cu:317-318`; `engine/src/split/CMakeLists.txt:76-92`, `120-143`
- `sfnx` の例外表示と終了経路: `engine/src/split/tools/sfnx.cpp:1097-1102`, `1123-1136`
