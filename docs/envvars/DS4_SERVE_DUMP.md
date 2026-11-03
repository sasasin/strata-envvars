# `DS4_SERVE_DUMP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata-dsv41 --serve` の単一会話サーバー経路で、各リクエストの logits を float32 バイナリファイルへ書き出すテスト用フックです。リクエスト *i* の prompt 最終行と、その後の decode step の logits 行を `<prefix>.<i>.f32` に書き出します（ファイルはリクエスト開始時に `wb` で開くため、既存ファイルは切り詰められます）。コードコメントは、異なるプロセス・履歴間の logits を byte 単位で比較する用途としています。

## 値と判定

`serve()` の開始時に `std::getenv("DS4_SERVE_DUMP")` を一度呼び、返り値が null かどうかだけを保持します。値を数値や真偽値に変換せず、文字列全体の検証も行いません。

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | `dump_prefix == nullptr` となり、このフックは出力ファイルを開かない |
| 設定あり（空文字を含む） | リクエストごとに `<値>.<番号>.f32` を開こうとする。空文字なら `.1.f32` など |

要求値が有効なパスかは事前検査されません。`fopen` が失敗して `nullptr` を返しても明示的なログやエラーはなく、その後の書き込みは `dump_f != nullptr` の条件でスキップされます。`fwrite` の戻り値も確認されません。

## 有効になる条件

- `strata-dsv41` 実行ファイルに含まれる `src/dsv41/ds4_main.cpp` の `--serve` 経路で読み取られます。通常の非 serve CLI 経路ではこの環境変数を参照しません。
- `serve()` 内で dump ファイルを開く箇所は `while (!multi)` の単一会話ループ内にあります。`--parallel` により複数会話 (`multi`) の経路へ入る場合、そのループを通らず dump は行われません。
- prompt 処理に成功し、decode リクエストを開始する段階でファイルを開きます。prompt 読み取りが失敗・キャンセルされたリクエストではここに到達せず、ファイルを作りません。
- 別の環境変数や CLI 引数との値の優先順位はありません。`--dump-logits` は非 serve の別用途であり、このフックの prefix を上書きしません。

## 実行時の詳細

`serve()` に入った時点で prefix を一度取得するため、同一プロセスで後から環境値が変わっても再読込されません。単一会話ループでは、各リクエストの prompt 読み込み後に、それまでの `dump_f` を閉じ、要求番号を 1 増やして `<prefix>.<番号>.f32` を `wb` で開きます。開いた直後に `dump_rows()` を呼ぶので、prompt 最終行の logits を出力します。decode の `round()` 成功後にも `dump_rows()` が呼ばれ、各 decode step の logits を同じファイルへ書きます。`dump_rows()` は `dump_f` が非 null で、かつ `m.logits(dump_lg)` が成功した場合に限り、`dump_lg` の全要素を 4 byte 単位で書き込みます。

各リクエストの終わりには開いているファイルを `fflush` します。次の dump 対象リクエスト開始時には前のファイルを閉じます。`fopen` の失敗、logits 取得失敗、短い書き込みに対する専用ログ・リクエスト失敗・終了処理は実装されていません。

## 根拠

- `src/dsv41/ds4_main.cpp:527-535` — 用途コメント、prefix の取得、logits 取得条件と float32 書き込み。
- `src/dsv41/ds4_main.cpp:1355-1364,1375-1391` — 単一会話ループ、prompt 成功後のファイル open と prompt logits 記録。
- `src/dsv41/ds4_main.cpp:1444-1467` — decode round 成功後の記録とリクエスト終端時の flush。
- `src/dsv41/ds4_main.cpp:2577-2584,2613-2629` — `--dump-logits` と `--serve` の引数処理、および serve 時の `serve()` 呼び出し。
- `CMakeLists.txt:931-957` — DeepSeek-V4.1 用 `strata-dsv41` 実行ファイルへの `src/dsv41/ds4_main.cpp` の組み込み。
