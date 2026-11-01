# `STRATA_PLE_CHECK`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

PLE（n-gram table）の読み取りで、行をデコードした結果に非有限値または絶対値 `1e5` 超があったとき、元ファイルからその行を再読込し、direct reader が渡したバイト列とファイルの内容を比較する診断スイッチです。値を修正したり読み取りを再試行したりする機能ではありません。

診断の実装は `PleTable` にあり、実際に呼ばれるのは PLE の direct I/O 経路です。未設定時は無効です（`src/kernels/ngram.cpp:248-255,535-556,585-600,603-654`）。

## 値と判定

値の文字列全体は検証せず、`std::atoi` の結果が 0 以外なら有効です（`src/kernels/ngram.cpp:253-255`）。したがって、未設定・空文字・数値変換できない文字列は無効になり、`1` や `-1` は有効になります。`atoi` は先頭の空白と符号を許し、数字の後ろに続く文字列は判定に使いません。たとえば `1tail` は有効、`0tail` は無効です。

判定結果は `static const bool` に保存され、プロセス内で最初に `check_on()` が呼ばれたとき一度だけ評価されます。その後に環境値を変更しても反映されません。CLI 引数や別の環境変数による上書きは、この実装にはありません（`src/kernels/ngram.cpp:253-255`）。

## 有効になる条件

- 診断値が有効であること。
- PLE テーブルが `PleIo::Direct` で読まれていること。direct モードでは、開いたときにファイルパスとテーブルのファイル内オフセットを保存し、メモリマップを解放して `PleReader` を開きます（`src/kernels/ngram.cpp:390-408`）。
- デコードされた 160 要素の行に、最初の非有限値または `fabs(value) > 1e5` の値があること（`src/kernels/ngram.cpp:257-265`）。

診断呼び出しは direct モードの `read_row`、`collect`、`gather_batch`（prefetch 経由を含む）にあります。mmap 経路の `read_row` と `collect` は診断を呼びません（`src/kernels/ngram.cpp:535-556,585-600,603-654`）。このため、変数が有効でも mmap で読んでいる場合にはこの診断は動きません。

## 実行時の詳細

異常値を見つけた行について、実装は `table_offset + row * row_bytes` からファイルを開き直して行全体を読みます。標準エラーに `strata ple check:` と、経路名、行番号、ファイルオフセット、ページ内オフセット、異常値の要素番号と値を出します。再読込できなければ `the file could not be re-read` を出します。同じバイト列なら `the delivered bytes ARE the file's bytes`、異なる場合は最初に異なるバイト位置と双方の値、および先頭 8 バイトを表示します（`src/kernels/ngram.cpp:259-296`）。

テーブルごとの報告上限は 8 件です。条件を満たす行がなければ出力はありません。比較のためにファイルを再読込するだけで、ログ後も呼び出し元へ異常値を返し続けます。チェック用の再読込に失敗した場合も、ここからエラー終了や呼び出し失敗にはしません（`src/kernels/ngram.cpp:259-296`）。

リリースノートは、この診断を #3602 の調査用として紹介し、疑わしい行を再読込して出力すると記載しています（`docs/release-notes-0.2.7.md:52`）。上記の有効条件と出力内容は、対象 commit の実装に基づきます。

## 根拠

- 値の取得、`atoi` 判定、初回評価後の cache: `src/kernels/ngram.cpp:253-255`
- direct I/O 時のパスとオフセット設定: `src/kernels/ngram.cpp:390-408`
- 異常判定、再読込、比較、報告上限、標準エラー出力: `src/kernels/ngram.cpp:257-296`
- `read_row` / `collect` / `gather_batch` の direct 経路での呼び出しと mmap 経路: `src/kernels/ngram.cpp:535-556,585-600,603-654`
- リリースノートの説明: `docs/release-notes-0.2.7.md:52`
