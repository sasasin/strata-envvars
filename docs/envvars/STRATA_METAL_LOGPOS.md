# `STRATA_METAL_LOGPOS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal の decode window が保持する logits から、次に入力された token の log-probability と上位 64 token を指定ファイルへ追記する、テスト・調査用フックです。通常のモデル計算や token 選択を設定値で変更する処理ではありません。`Window::finish` から呼ばれる `Window::logpos` がファイル出力を行います（`engine/metal/src/engine/window.cpp:570-580,1822-1853,2066-2107`）。

## 値と判定

| 条件 | 未設定 | 値の扱い | 例 |
|---|---|---|---|
| Metal decode window | 読み取った `path` が null のため出力しない | 文字列を変換せず `std::fopen(path, "ab")` に渡す | `0`、`1`、`true` はフラグではなく、それぞれその名前のパス。空文字も設定済みだが空パスでの open を試みる |

数値 parse、真偽値 parse、空白除去、大文字小文字比較、値域検査、既定パスへの fallback はありません。`fopen` が失敗した場合は出力せず、Strata は警告やエラーを出しません（`engine/metal/src/engine/window.cpp:1822-1826`）。CLI 引数や設定ファイルからこの値を上書きする処理も見つかりません。

## 有効になる条件

- `engine/metal` の Strata Metal engine をビルドし、decode window の `window_run` 経路を使うこと。Metal build は macOS 専用で、`STRATA_METAL_ENGINE` が有効な場合に engine を構成します（`engine/metal/CMakeLists.txt:1-2,18-20,103-111`）。他 backend にこの変数の読み取り箇所はありません。
- 値が null でなく、指定したパスを `"ab"` モードで開けること（`engine/metal/src/engine/window.cpp:1823-1826`）。
- `logpos` が `head == true` で呼ばれること。`STRATA_LOGPOS` が設定されている場合、`window_run` は通常の `head` 引数にかかわらず Metal window に `head=true` を渡します。これは別変数による条件であり、本変数自身は head を有効化しません（`engine/metal/src/engine/window.cpp:3650-3656`）。
- 行データを作るには `Tn == 1` の head window が必要です。位置が連続する後続 head window が来ると、前回の logits と今回の `tokens[0]` から行を書きます（`engine/metal/src/engine/window.cpp:1827-1853`）。

## 実行時の詳細

`Window::logpos` 内の関数ローカル `static const char*` が、最初に関数へ入ったとき `std::getenv` を一度実行して値を保持します。そのため、それ以降にプロセス環境を変えても読み直しません。ファイルは head window の呼び出し時に遅延して `"ab"` で開かれ、成功した `FILE*` は当該 `Window` が存続する間再利用されます。window の破棄時に close します（`engine/metal/src/engine/window.cpp:1822-1826,2041-2045`）。

`Tn == 1` の head window ごとに `lm_` の語彙全体をコピーし、log-sum-exp を計算して argmax と上位 64 件を保持します。次の head window の `pos0` が保存済み位置 `lp_pos_ + 1` と一致すると、次の入力 token `tokens[0]` を対象として行を出力します。行はタブ区切りで、位置（最初に処理した位置からの差）、target token ID、その log-probability、argmax ID、固定の `0` を4列、続けて `id:log-probability` の上位64件です。各 log-probability は logits から正規化して出し、行ごとに改行と `fflush` を行います（`engine/metal/src/engine/window.cpp:1827-1853`）。

対象位置の直後に head window が来なければ、その保留行は出ません。後続 window が複数 token なら直前行を出力した後、その window 自体の logits は記録せず、位置が飛んだ場合も保留行を破棄します。最後の保留行を flush する destructor 処理もありません（`engine/metal/src/engine/window.cpp:1827-1836,2041-2045`）。このログ処理は `finish` の出力 token を書き換えず、行列計算や sampler の選択を変更する分岐もありません（`engine/metal/src/engine/window.cpp:2104-2123`）。

## ログと測定値

本変数のための stderr/stdout メッセージ、open 失敗の警告、終了コード変更はありません。観測結果は指定先に追記される TSV 行です。Strata の `docs/QUANTS.md` は別の `STRATA_LOGPOS` による品質測定形式を説明していますが、`STRATA_METAL_LOGPOS` 固有の測定結果や通常利用向け仕様は記載していません（`docs/QUANTS.md:54-65`）。

## 根拠

- `engine/metal/src/engine/window.cpp:570-580` — ログ状態と用途コメント。
- `engine/metal/src/engine/window.cpp:1822-1853` — 値読み取り、open、行の作成・出力。
- `engine/metal/src/engine/window.cpp:2041-2045,2066-2123` — close、呼び出し位置、通常の出力 token との関係。
- `engine/metal/src/engine/window.cpp:3650-3656` — 別変数 `STRATA_LOGPOS` が head 条件を変える経路。
- `engine/metal/CMakeLists.txt:1-2,18-20,103-111` — Metal backend の build 範囲。
