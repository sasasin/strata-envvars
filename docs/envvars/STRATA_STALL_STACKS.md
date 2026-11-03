# `STRATA_STALL_STACKS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

Windows 版 Strata の stall report に、報告時点での他スレッドの call stack を追加します。通常の推論処理や stall の検出条件は変えず、report の診断情報を増やします。スタック採取コードも `generate.cpp` 内の `_WIN32` 条件下にあります。そのため、Linux など Windows 以外のビルドではこの名前を環境から読みません（`src/program/generate.cpp:1712-1717,1826-1830`）。

## 値と判定

値は文字列全体として parse せず、`getenv()` が返す文字列の先頭文字だけを `'1'` と比較します（`src/program/generate.cpp:1826-1829`）。

| 状態 | 結果（Windows の stall report） |
|---|---|
| 未設定 | スタックを採取・出力しない |
| 空文字 | 先頭文字が `'1'` でないため採取・出力しない |
| 先頭文字が `1`（例: `1`, `10`, `1anything`） | 採取・出力する |
| その他の先頭文字（例: `0`, `true`, 空白 + `1`） | 採取・出力しない |

大文字小文字や数値としての妥当性は関係しません。値を CLI 引数や別設定から上書きする処理はこのコードにありません。

## 有効になる条件

- Windows ビルドであること。スタック採取と環境変数判定の両方が `_WIN32` ガード内です（`src/program/generate.cpp:1712-1717,1826-1830`）。
- stall report が実際に呼ばれること。通常の serve watchdog は `STRATA_WATCHDOG_S`（未設定時 60 秒）の間 progress がなく、ファイル tier の読み取り猶予や明示的な progress allowance でも解除されない場合に report を出して engine を abort します（`src/program/generate.cpp:13223-13234,13345-13379`）。`STRATA_SPEC_WATCH` が正数なら、その診断 watchdog も停滞時に report 後 abort します（`src/program/generate.cpp:20049-20069`）。この変数自体は stall を検出したり、report を発生させたりしません。

## 実行時の詳細

各 `stall_report()` 呼び出し時に環境を読み直します。結果は関数内の通常のローカル `const bool` で、static cache ではありません。従って、同一プロセスでも次の report では再評価されます（`src/program/generate.cpp:1826-1830`）。

有効時、Strata は現在のスレッドを除く同一プロセスのスレッドを列挙し、最大 256 件を対象にします。各 thread を一時停止して thread context から最大 32 frame の instruction address を静的配列へ記録し、thread を再開してから report に出力します。thread の open / suspend / context 取得に失敗した場合はその thread を飛ばすか、取得できた部分だけを記録します（`src/program/generate.cpp:1717-1723,1744-1786`）。

report には `thread stacks (STRATA_STALL_STACKS=1; innermost first; ...)` の見出し、thread ID、各 frame の module-relative offset または address が出ます。`strata.exe` の frame は、実行ファイルの隣に PDB がある場合に名前を引けるよう Strata が `dbghelp.dll` の symbol API を呼び出します。他 module は module 名と offset で表示します（`src/program/generate.cpp:1789-1822,1843-1845`）。スタックの採取・表示に失敗した場合の専用エラー文はなく、個別 thread の失敗は黙ってスキップされます。

通常の watchdog 経由では report の後に stderr を flush し、GPU wait を解放して `abort()` します。`STRATA_SPEC_WATCH` 経由も同様に report の後に abort します。変数が無効でも stall report 自体、通常の進捗情報、後続終了動作は残ります（`src/program/generate.cpp:13371-13379,20064-20069`）。

## 根拠

- 環境判定と report への接続: `src/program/generate.cpp:1826-1845`
- Windows 限定スタック採取、thread/frame 上限と unwind: `src/program/generate.cpp:1712-1787`
- stack の表示と symbol lookup: `src/program/generate.cpp:1789-1822`
- serve watchdog の既定値と report・abort: `src/program/generate.cpp:13223-13379`
- `STRATA_SPEC_WATCH` による追加 watchdog: `src/program/generate.cpp:20049-20069`
- stall のユーザー向け概要: `docs/DETAILS.md:1333`
