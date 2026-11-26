# `STRATA_STALL_STACKS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Windows で stall report を出すとき、呼出しスレッド以外のプロセス内スレッドを一時停止してスタックを採取し、その report に追記する診断用スイッチ。生成内容や GPU 処理を制御するものではない。実装は `stall_report` と `stall_stacks` 名前空間にある（`engine/src/program/generate.cpp:1979-2097,2110-2112`）。

Windows 以外では環境変数を読むコードもスタック採取・表示コードもコンパイルされず、この変数は効果を持たない（`engine/src/program/generate.cpp:1979,2093-2097,2110-2112`）。

## 値と判定

Windows の `stall_report` 呼出し時に `std::getenv` で値を取り、未設定でないことと先頭文字が `'1'` であることだけを判定する。文字列全体の数値変換・比較はしない（`engine/src/program/generate.cpp:2093-2097`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Windows | 無効 | `1`, `10`, `1anything`（先頭文字が `1`） | 空文字、`0`, `true`, ` 1`, `01` |
| Windows 以外 | 無効（読み取りなし） | なし | すべて（このコード経路では参照されない） |

空文字は `getenv` が非 null を返しても `e[0]` が `'1'` でないため無効。大文字小文字、後続文字、数値としての妥当性、空白は検証せず、先頭1文字だけを見る。CLI 引数や別の環境変数による上書きはない（`engine/src/program/generate.cpp:2093-2097`）。

## 有効になる条件

- OS が Windows であること。ほかの OS では関連コードが `_WIN32` 条件内にあるため読み取られない（`engine/src/program/generate.cpp:1979,2093-2097,2110-2112`）。
- `stall_report` が呼び出されること。通常は serve の進捗 watchdog が停止判定したときで、`STRATA_WATCHDOG_S` 等の条件を満たして watchdog が動作する必要がある（`engine/src/program/generate.cpp:16261-16277,16297-16321`）。speculative generate 経路では `STRATA_SPEC_WATCH` が正の `atoi` 値として読まれ、その監視が停止判定した場合にも report を呼ぶ（`engine/src/program/generate.cpp:24915-24936`）。
- 値の先頭文字が `1` であること。これを満たすと採取を行い、report 内にスレッドスタック節を出す（`engine/src/program/generate.cpp:2093-2097,2110-2112`）。
- 採取できるスレッドだけが出力される。スナップショット作成失敗時は採取を終え、スレッドを開けない・停止できない場合はそのスレッドを飛ばす。独立した理由ログはない（`engine/src/program/generate.cpp:2011-2027`）。

## 実行時の詳細

値は `stall_report` のたびに読み直され、関数内 static cache はない。したがってプロセスの環境値が呼出し間に変更されれば次の report で再判定される（`engine/src/program/generate.cpp:2093-2097`）。

有効時、スタック採取を report の本文生成より先に行う。プロセス内の他スレッドを列挙し、自スレッドを除いた最大256スレッドを対象にする。各スレッドはスタック取得の間だけ suspend され、最大32フレームまで unwind した後 resume される。スレッドの列挙・停止・context 取得などに失敗した場合、失敗したスレッドは省略される（`engine/src/program/generate.cpp:1984-1990,1992-2053`）。

その後の report では `thread stacks ...` の見出し、thread ID、フレームを出す。フレームは innermost first。`strata.exe` のシンボル名は `dbghelp` が利用でき、実行ファイルの隣に PDB がある場合に限り解決を試みる。他モジュールは module 名と相対 offset、module を特定できないものはアドレスを出す（`engine/src/program/generate.cpp:2056-2088`）。

このスイッチは report のテキストスタック採取・表示にだけ使われる。Windows の stall report は値に関係なく後段で `strata-stall-<pid>.dmp` の作成も試みる（`engine/src/program/generate.cpp:2153-2171`）。

## ログと測定値

有効時のテキスト出力は stall report の stderr に入り、見出しは実装上 `  thread stacks (STRATA_STALL_STACKS=1; innermost first; strata.exe frames named from its PDB when it is beside the exe):`（`engine/src/program/generate.cpp:2068-2088`）。report を起こす serve watchdog は `strata serve: no progress for ...` を出して report を書き、GPU wait 解放を試みた後 `std::abort()` する。speculative generate の watchdog も `strata generate: no progress for ...` と report を出し、同様に abort する（`engine/src/program/generate.cpp:16313-16321,24929-24934`）。

`docs/DETAILS.md:1544` は watchdog の stall report と Windows の dump を案内するが、この環境変数によるスタック追記の値判定までは記載していない。測定値の記載はない。

## 根拠

- `engine/src/program/generate.cpp:1979-2097` — Windows 専用の採取処理と環境変数判定。
- `engine/src/program/generate.cpp:2056-2088,2110-2112` — スタックの表示と report への挿入。
- `engine/src/program/generate.cpp:16261-16321,24915-24936` — report を呼ぶ監視経路と終了処理。
- `engine/src/program/generate.cpp:2153-2171` — 環境変数とは独立した Windows dump 作成処理。
- `docs/DETAILS.md:1544` — stall report に関する利用者向け資料。
