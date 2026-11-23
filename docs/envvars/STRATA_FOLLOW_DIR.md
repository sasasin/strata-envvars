# `STRATA_FOLLOW_DIR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA/HIP の serve 要求処理で、prompt の token ID 列から計算した hash に対応するファイルがあれば、その内容を生成 continuation として使う測定用スイッチです。verifier が選んだ token の代わりにファイル中の token ID を出力・commit するため、通常の生成結果を再現する設定ではなく、指定した continuation を評価する経路です。処理は要求開始時に `engine/src/program/generate.cpp` で行われます（`engine/src/program/generate.cpp:21603-21625, 22048-22056, 22912-22920`）。

この名前の実行時読み取りは `std::getenv` 1 箇所です。候補一覧の「flag」という分類とは異なり、空でない値は真偽値ではなくディレクトリパスとして使われます。`engine/src/program/generate.cpp` の serve 要求ループに実装されており、同じ名前を読む SYCL 実装は確認できません（`engine/src/program/generate.cpp:21608-21625`; `engine/sycl/src/program/generate.cpp` には `STRATA_FOLLOW` はありますが `STRATA_FOLLOW_DIR` の読み取りはありません）。

## 値と判定

`std::getenv` の戻り値が null でなく、先頭文字が NUL でない場合だけパスとして保持します。値全体の比較、trim、大小文字変換、数値変換はありません。空文字は無効です。`0` や `false` も空でなければディレクトリ名として有効です。既定のディレクトリはなく、未設定または空文字ならこの変数による forced continuation はありません（`engine/src/program/generate.cpp:21608, 21617-21626`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP の serve 要求ループ | prompt hash ファイルを探さない | `/tmp/follow`、`0`、`false`（文字列をディレクトリとして使用） | 空文字 |

対象名の読み取り箇所は関数内 `static` 初期化子です。プロセスが最初にこの要求処理へ到達した時点で一度評価されるため、その後プロセス内で環境を変更しても反映されません（`engine/src/program/generate.cpp:21608`）。

## 有効になる条件

- `engine/src/program/generate.cpp` の CUDA/HIP serve 要求処理が実行されること。該当箇所は要求ごとに `DONE` 応答を出す生成経路内です（`engine/src/program/generate.cpp:23445-23479`）。
- 要求の prompt token ID 列 `ids` に対する hash 名のファイルが読み取れ、その先頭行から少なくとも 1 個の数字列を token ID として取り出せること。ファイルがない、開けない、空、または先頭行に数字がない場合は forced continuation になりません（`engine/src/program/generate.cpp:21617-21626`）。
- 要求順で読む `STRATA_FOLLOW` の当該要求に空でない token 列がないこと。`STRATA_FOLLOW` から token 列が選ばれて `fol` が非 null の場合、`STRATA_FOLLOW_DIR` のファイルは読まれません。`STRATA_FOLLOW` の該当行が空なら `fol` は null のままなので、ディレクトリ側を試します（`engine/src/program/generate.cpp:21580-21601, 21617-21626`）。
- 別の CLI 引数がこのディレクトリ値を上書きする処理はありません。強制再生後の token は通常の生成出力と同じ出力・commit 経路へ入ります（`engine/src/program/generate.cpp:22048-22056, 22912-22924, 23005-23015`）。

## 実行時の詳細

環境変数の読み取り値を static に保持した後、要求ごとに `ids` の各 token ID を順番に hash します。コードコメントは FNV-1a 64 bit と説明しています。実装の初期値は `1469598103934665603` で、各 token で XOR 後に `1099511628211` を乗算します。結果は 16 桁の小文字 16 進数にし、`<値>/<hash>.txt` を開きます。パスは単純な文字列連結で、相対パスの場合はプロセスの作業ディレクトリ基準です（`engine/src/program/generate.cpp:21603-21619`）。

ファイルの先頭行だけを読みます。行を左から走査し、ASCII 数字の連続部分ごとに `std::atoi` した値を `int32_t` にして並べます。区切りはカンマでなくてもよく、数字以外の文字は読み飛ばします。そのため `-5` は `5` として、`0anything` は `0` として取り込まれます。符号、範囲、token ID としての妥当性、行全体の形式は検証されません。数字列がない場合は空の列となり forced continuation は使われません（`engine/src/program/generate.cpp:21620-21626`）。

選ばれた forced continuation の範囲内では、各 verifier window の出力 token を対応する列の token に置き換えます。窓の後続入力と forced token の一致を使って speculative draft の受理数も決まります。forced 列を使い切った位置以降は、範囲検査により verifier の出力をそのまま使います（`engine/src/program/generate.cpp:22048-22056, 22912-22924`）。この変数による読込失敗や空列に対する警告・終了処理はなく、通常の生成経路を続けます（`engine/src/program/generate.cpp:21617-21626`）。

## ログと測定値

forced continuation が選ばれ、比較対象となる行が 1 行以上ある場合、要求の完了処理で stderr に次の形式を出します。`<行数>` と `<一致数>` は整数、最後は一致率です。

```text
strata follow: <行数> rows on the forced text, <一致数> of their picks were the forced token (<一致率>%)
```

これは forced text 上で verifier が選んだ token と強制 token の一致を数える診断です。ファイルを開けなかった場合、forced 列が空の場合、または集計対象行がなければ、この行は出ません。パスの有効化、ファイル読込失敗、parse 失敗専用のログはありません（`engine/src/program/generate.cpp:23459-23468`）。調査対象の `docs/DETAILS.md` にこの変数の性能測定値は見当たりません。

## 根拠

- `engine/src/program/generate.cpp:21603-21626` — 用途、static 読み取り、prompt hash、ファイル読込、token ID 抽出。
- `engine/src/program/generate.cpp:21580-21601, 21617-21627` — `STRATA_FOLLOW` の優先とディレクトリ側の有効判定。
- `engine/src/program/generate.cpp:22048-22056, 22912-22924` — forced token の置換と verifier window の処理。
- `engine/src/program/generate.cpp:23459-23468` — 完了時の一致診断ログ。
