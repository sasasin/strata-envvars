# `STRATA_DUMP_FIRST_LOGITS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

生成経路で最初の decode window が出した logits の先頭行をファイルへ保存する診断用フックです。サーバー経路では request ごとに最初の window の logits を保存し、複数 request の出力を比較できるよう連番の suffix を付けます。いずれも生成結果や推論計算の分岐を変えず、ファイル I/O と失敗時の stderr ログを追加します。

CUDA 実装は `src/program/generate.cpp`、SYCL 実装は `sycl/src/program/generate.cpp` にあります。候補名の直接参照は CUDA ファイルの generate / serve 各1箇所と SYCL ファイルの generate 1箇所です。CUDA の serve 部分にある同じ実装は、コメントにも「Diagnostics」として記されています。

## 値と判定

値の内容は parse されず、`getenv()` が `nullptr` かどうかだけで判定されます。

| 状態 | 通常生成 | サーバー |
|---|---|---|
| 未設定 | 出力しない | 出力しない |
| 設定あり（空文字を含む） | `wb` で値をファイル名として開く | 値に `.` と連番を付けた名前を `wb` で開く |

通常生成では設定値そのものがファイルパスです。サーバーでは `<値>.<n>` がパスとなり、`n` はこの処理内の static カウンターで 0 から増えます。空文字の場合も「設定あり」と判定されます。通常生成は空のパスを開こうとして失敗し、サーバーでは `.0` などの相対パスになります。値の先頭文字・大文字小文字・数値としての妥当性は検査されません。

## 有効になる条件

- 通常生成では `first_window` が true のときだけ確認します。このフラグは `native_pack` と同じ値で初期化されるため、native pack の decode 経路でのみ、この箇所の dump が実行されます。非 native pack は prompt の token loop が先に動くため、最初の verify window 到達時にはフラグが false です。
- サーバーでは各 request の decode loop で `first_window` が true の間に dump します。フラグはその request の最初の verify window の後に false になります。
- `--dump-logits` は別の CLI 機能であり、全生成位置などを選択して出力します。この環境変数による dump は最初の window の先頭 logits 行だけを対象にします。

## 実行時の詳細

通常生成では、最初の window の verify 完了後、`ver.copy_logits(0, row.data())` で vocab 数の float 行を取得し、環境変数の値をファイル名に `fopen(..., "wb")` で開いて `sizeof(float)` 単位で書きます。CUDA と SYCL の実装はこの点で同じです。出力はテキストではなく、float 値をそのまま並べたバイナリです。ファイルを開けない、logits をコピーできない、または全要素を書けない場合は `strata generate: STRATA_DUMP_FIRST_LOGITS: cannot write <path>` を stderr に出します。開けた場合は `fclose` します。

サーバーでは `getenv()` の結果を最初の window 分岐内の `static const char*` に保持します。そのため、最初にこの分岐へ到達した後でプロセス環境を変更しても、このポインターの値は再評価されません。設定されていれば `fl_n` を1増やしてから、`<値>.<n>` に先頭 logits 行を `wb` で書きます。したがって既存ファイルは同名の場合に上書きされ、番号は request ごとにリセットされずプロセス内で進みます。失敗時の stderr は `strata serve: STRATA_DUMP_FIRST_LOGITS: cannot write <path>` です。通常生成側は最初の window で `getenv()` を直接呼びます。

## 根拠

- CUDA 通常生成の `first_window` 初期値と native pack 条件: `src/program/generate.cpp:12968-12970`。dump の読み取り、コピー、書き込みとエラー表示: `src/program/generate.cpp:13100-13112`。
- SYCL 通常生成の同等箇所: `sycl/src/program/generate.cpp:12405-12417`。
- CUDA サーバーの request 単位の `first_window`: `src/program/generate.cpp:11104-11122`。最初の window の dump と連番: `src/program/generate.cpp:11907-11920`。
- `--dump-logits` が別に parse・設定される箇所: `src/program/generate.cpp:756,1835,5764-5781`。
- `docs/DETAILS.md` を含む `docs` 内では、この環境変数の説明は見つかりませんでした。
