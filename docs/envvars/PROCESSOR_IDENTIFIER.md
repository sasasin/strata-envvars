# `PROCESSOR_IDENTIFIER`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（2026-11-17 時点）。

## 役割

Windows 上の Strata Control が CPU の説明文字列を取得するときの入力です。`strata_control.sysinfo.processor()` は Windows でこの環境変数を読み、前後の空白を除いた文字列を返します。CPU 機能の有効化や backend 選択を切り替えるフラグではありません（`strata_control/sysinfo.py:85-89`）。

この値は測定履歴の machine identity の `processor` 欄に入り、異なる値の測定記録を同一機械の記録として比較しないための識別情報になります（`strata_control/tune_history.py:84-96,99-117`）。CPU 情報を作る別経路では、Windows レジストリまたは PowerShell から CPU 名を得られるとそちらが優先されます（`strata_control/tune_machine.py:132-167`; `setup.py:1471-1498`）。

## 値と判定

| 条件 | unset | 設定時に返る値 | 空文字・無効値 |
|---|---|---|---|
| Windows (`sysinfo.processor()`) | `""` | 値の前後の空白を `strip()` で除いた文字列 | 空文字または空白だけなら `""`。それ以外は内容を検証せず、そのまま返す |
| Windows 以外 (`sysinfo.processor()`) | この変数を読まない | `platform.processor()` の戻り値 | この変数は判定に関与しない |

文字列全体の比較、数値変換、真偽値判定はありません。従って `"0"`、`"false"`、大小文字の異なる文字列も、空白除去後に空でなければ CPU 説明として返ります。上限・下限や無効値時の別値への変換もありません（`strata_control/sysinfo.py:85-89`）。

## 有効になる条件

- OS が Windows で、Strata Control の `sysinfo.processor()` を呼ぶ経路であること。Windows 以外では `PROCESSOR_IDENTIFIER` を参照せず `platform.processor()` を使います（`strata_control/sysinfo.py:85-89`）。
- 値を読むだけの経路では未設定・空文字とも空の CPU 名になります。`tune_machine.cpu()` はその場合に `sysinfo.machine()` を仮の名前として使いますが、Windows ではレジストリ `ProcessorNameString` を取得できればその値に置き換えます（`strata_control/tune_machine.py:132-167`）。
- セットアップの `cpu_info()` も Windows では最初にこの値を候補にしますが、PowerShell の `(Get-CimInstance Win32_Processor).Name` が空でなければそちらで上書きします。AVX2/AVX-512 の判定は別の processor feature / CPUID 判定であり、この文字列を見ません（`setup.py:1471-1498`）。
- CLI 引数、別の環境変数、backend、サーバーモードによる値の優先順位や有効化条件はありません。

## 実行時の詳細

値は `processor()` の呼び出しごとに `os.environ.get("PROCESSOR_IDENTIFIER", "")` で取得し、その場で `strip()` します。モジュール読み込み時の固定 cache はありません。そのため、同一プロセス内で環境辞書が変わってから再度呼び出せば新しい値を読みます（`strata_control/sysinfo.py:85-89`）。子プロセスへの転送・上書きはこの変数を扱う Strata コードでは確認できません。

CPU 名は `tune_machine.hardware_identity()` の hard identity に記録されます。ただし Windows では前述のレジストリ取得成功時に環境変数由来の値は置き換わります。測定履歴の identity では `processor()` の戻り値が記録され、比較キーの一部になります。この記録値の差は machine identity の差として扱われます（`strata_control/tune_machine.py:132-167,264-277`; `strata_control/tune_history.py:84-96,99-117`）。

## ログと測定値

この変数の値を理由に出す専用ログ、警告、終了・失敗経路はありません。Control の履歴・機械情報で `processor` 欄として観測できます（`strata_control/tune_history.py:84-96`; `strata_control/tuning.py:801-812`）。セットアップの CPU 表示では PowerShell が空でない名前を返す場合、その名前が表示候補になります（`setup.py:1471-1480,7524-7528`）。測定値の記載はありません。

## 根拠

- `strata_control/sysinfo.py:85-89` — Windows 限定の環境変数読み取り、空文字既定、空白除去。
- `strata_control/tune_history.py:84-117` — processor 欄の machine identity への記録と比較キーへの格納。
- `strata_control/tune_machine.py:132-167,264-277` — CPU 名の fallback、Windows レジストリ優先、preset hardware identity。
- `setup.py:1471-1498,5129-5136,6334-6344` — CPU 表示名の Windows 上書きと ISA 判定が CPU 機能ビットに基づくこと。
