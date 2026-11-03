# `STRATA_DUMP_WINDOW_TOP2`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL 版 `strata` の speculative generation で、検証した各 window の各 row について、logits の上位 2 token ID と logits をテキストファイルへ出力する診断用フックです。真偽値の切り替えではなく、環境変数の値を出力先パスとして使います。参照は `sycl/src/program/generate.cpp` にのみあります。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未設定 | 出力処理を実行しません。 |
| 設定あり（空文字を含む） | 設定有無で処理に入ります。値を `fopen(path, "w")` に渡します。空文字ではファイルを開けず、出力は行われません。 |
| 有効なファイルパス | 初回にファイルを write モードで開き、window ごとの上位 2 件を書き込みます。既存ファイルは `"w"` により切り詰められます。 |
| 開けないパス | `fopen` が null となり、行出力をせず、Strata 独自の警告・エラーも出しません。 |

数値変換や値域検査はありません。CLI 引数や別環境変数によるパスの上書きは、この箇所にはありません。環境変数は各 window で設定有無を確認しますが、ファイルポインタは関数内の `static` 変数に保存されます。したがって、最初の open 後に値を別のパスへ変えても open 済みのファイルが使われます。値を unset にするとその window の出力ブロック自体が実行されず、再設定すると保存済みポインタへの書き込みが再開します。

## 有効になる条件

- SYCL 版 `strata` をビルドして実行する必要があります。このソースは `sycl/src/program/generate.cpp` にあり、SYCL の CMake target `strata` に組み込まれます。SYCL セットアップは Linux 以外では利用不可として扱います。
- speculative generation の window loop に入り、`ver.run(...)` が成功した後に実行されます。通常の非 speculative 経路や、検証が失敗して return する経路ではここに到達しません。
- 値が設定されていても、出力ファイルを開けなければ記録されません。出力先に関する CLI 引数や他環境変数との優先順位はありません。

## 実行時の詳細

各 window の検証成功後、`ver.vocab()` 分の logits を row ごとに `ver.copy_logits(t, ...)` で取得します。コピーに失敗した row があると残りの row の処理を止めます。各 row では logits を走査して上位 2 件を選び、次の列順で一行を書きます（空白区切り）。

`position T row token_id_1 logit_1 token_id_2 logit_2`

`position` は `p + t`、`T` は window 幅、`row` は 0 始まりの `t` です。logits は小数点以下 5 桁で出力します。各 window の後に `fflush` します。Strata はファイル open や書き込み失敗をログに出さず、終了コードにも反映しません。このコードはファイルを明示的には `fclose` しません。

## 根拠

- `sycl/src/program/generate.cpp:13058-13103` — speculative generation 側の条件と verifier の初期化。
- `sycl/src/program/generate.cpp:13454-13477` — 検証後の環境変数確認、`fopen(..., "w")`、logits の取得と上位 2 件の出力、flush。
- `sycl/CMakeLists.txt:284-286` — `sycl/src/program/generate.cpp` を含む SYCL `strata` 実行ファイル target。
- `sycl/setup_intel.py:99-103` — SYCL build の実行条件として Linux 以外を拒否。
