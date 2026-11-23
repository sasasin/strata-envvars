# `STRATA_DUMP_TOKENS_DIR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

serve の要求ごとに、強制再生されていない生成 token ID を、prompt の token ID 列から計算した hash を名前にしたファイルへ記録する測定用スイッチです。通常は未設定で無効です。値はフラグとして parse されず、空でない場合は出力先ディレクトリの文字列として使われます。dump 自体は token の選択・出力を置き換えません。処理は `engine/src/program/generate.cpp` の serve 要求ループにあります（21603-21615、21627-21628、22309-22313、23005-23010行）。

## 値と判定

`std::getenv` の結果が null でなく、先頭文字が `\0` でない場合だけ値を保持します。値全体の比較、数値変換、trim、大小文字判定はありません。空文字は無効ですが、`0`、`false`、空白を含む文字列など空でない値はすべてディレクトリ名として有効です。設定されていても、要求が強制再生中ならその要求では dump されません（`engine/src/program/generate.cpp:21609-21609, 21627-21627`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| serve 要求ループ | dump 先なし | `/tmp/tokens`、`0`、`false`（いずれもその文字列をディレクトリ名として使用） | 空文字 |

## 有効になる条件

- `engine/src/program/generate.cpp` の serve 要求処理が実行される必要があります。このコードは prompt の `ids`、serve 要求の decode ループ、`DONE` 応答処理と同じ要求スコープにあります（21603-21615、23445-23479行）。
- その要求が `STRATA_FOLLOW` または `STRATA_FOLLOW_DIR` による強制再生中でないことが必要です。先に要求順の `STRATA_FOLLOW` データが選ばれている場合、prompt hash で `STRATA_FOLLOW_DIR` のファイルが見つかり token ID が読み込まれた場合は `fol != nullptr` となり、`dump_on` は false です（21575-21601、21617-21628行）。
- `dump_ids` に記録対象 token があり、要求が cancel されずに完了処理まで到達する必要があります。cancel 時はファイル出力しません（23459行）。
- 指定ディレクトリは事前に存在し、書き込み可能である必要があります。Strata はディレクトリを作成しません。`fopen` が失敗してもエラーを出さず、その要求のファイルを作成しません（23459-23464行）。
- 他の CLI 引数や環境変数がこの値を上書きする処理はありません。強制再生変数は出力を抑止する相互作用があります。

## 実行時の詳細

値は関数内 `static` 初期化子で最初にこの要求処理へ到達したときに一度読み取られます。以後の要求でも同じ値を使い、プロセス実行中に環境を変更しても再読込しません（`engine/src/program/generate.cpp:21609`）。prompt key は要求の `ids` 全体を FNV-1a 64 bit で hash し、16桁の小文字 16 進数にして作ります（21612-21615行）。

強制再生されていない要求では、通常の decode ループが stdout に出す token ID と同じ値を `dump_ids` に追加します。最後に cancel されず、1 個以上の ID があれば `<値>/<prompt-key>.txt` を `"w"` で開き、ID をカンマ区切りで一行に書きます。先行する `/` を含めた単純な文字列連結なので、相対パスはプロセスの作業ディレクトリ基準です。既存ファイルは `"w"` で開かれ、上書きされます（`engine/src/program/generate.cpp:22309-22313, 23005-23010, 23459-23464`）。

## ログと測定値

この変数専用の有効ログ、無効値警告、ファイル作成失敗ログはありません。書込先を開けない場合も `fopen` の戻り値を条件分岐するだけで、警告や終了にはつながりません（`engine/src/program/generate.cpp:23459-23464`）。token は通常どおり stdout の `T <id>` 行にも出力されます（22309-22313、23005-23010行）。この変数による性能値や token 同一性の測定値は、調査対象の `docs/DETAILS.md` には見当たりません。

## 根拠

- `engine/src/program/generate.cpp:21603-21615` — 測定用途の説明、変数の読み取り、prompt hash。
- `engine/src/program/generate.cpp:21575-21628` — `STRATA_FOLLOW` / `STRATA_FOLLOW_DIR` との優先関係と dump の有効判定。
- `engine/src/program/generate.cpp:22048-22056, 22309-22313, 22912-22920, 23005-23010` — 強制 token の適用と、非強制時の生成 token 収集。
- `engine/src/program/generate.cpp:23459-23464` — cancel 判定後のファイル書き込み。
