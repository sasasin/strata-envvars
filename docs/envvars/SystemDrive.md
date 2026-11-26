# `SystemDrive`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Strata は `SystemDrive` を Windows のシステムドライブ名として複数の補助処理で参照する。エンジンでは Windows のページファイル設定にある `?:\pagefile.sys` を実ドライブのパスへ置き換え、ページファイルが今後増やせる commit 量の推定に使う。Terminal のセットアップでは `ExistingPageFiles` から自動管理ページファイルのドライブを得られない場合の既定ドライブを決め、ページファイル容量の警告材料にする。フォルダー検査では Windows のシステムフォルダー候補を組み立て、Vision サーバーでは画像 encoder 用一時ディレクトリの候補を選ぶ。いずれもモデルの選択や生成内容を直接指定する設定ではない。

根拠: `engine/include/strata/platform/commit.hpp:121-147`; `terminal/setup.py:1467-1491`; `terminal/strata_control/folders.py:31-41`; `terminal/serve/server.py:3039-3057`。

## 値と判定

この名前を読む処理は boolean/numeric parser を使わず、パスの一部として扱う。したがって `0`、`1`、`true` などに共通の有効・無効判定はない。

| 読み取り箇所・条件 | 未設定 | 空文字 | 設定値の扱い |
|---|---|---|---|
| エンジン `commit_growth`（Windows。かつ `STRATA_COMMIT_GROWTH` により早期 return しない場合） | バッファ初期値 `C:` を使う | API の戻り値は検査されず、空または取得できなかった場合の扱いを Strata は分岐しない | `GetEnvironmentVariableW` に最大 8 wchar の出力先を渡し、取得した `sysdrive` を `?:` の先頭に連結する。値の形式検証・大文字化なし。API の取得結果/長さによる分岐なし。 |
| Terminal `setup.py:page_file_setting`（Windows、`ExistingPageFiles` にドライブがない場合） | `"C:"` を既定にする | `or "C:"` により `"C:"` と同じ | 文字列の先頭 1 文字だけを取り、大文字化してドライブ文字にする。たとえば `d:\` は `D`、`xy` は `X`。 |
| `strata_control.folders._system_roots`（Windows） | `"C:"` を既定にし、`C:\Windows` 等を検査対象に加える | 設定値そのままを使い、追加候補は `\Windows` 等になる | 文字列全体を `SystemRoot` 等の他候補とともにルート候補へ連結する。空白除去やドライブ形式検証はしない。 |
| `Vision.work_dir`（OS 条件なし） | `"C:"` を既定にする | 設定値そのままなので候補は `\` | 文字列全体に `os.sep` を加え、`mkdtemp(dir=...)` の親候補にする。値の正規化・検証はしない。 |

Python の `os.environ.get` は各箇所で文字列をそのまま取得し、環境変数名や値の大小文字比較はありません。Windows では環境変数名の大文字小文字は OS の環境辞書の仕様に従います。エンジン側の固定長バッファより長い値について、Strata は API の返却長を調べず、切り詰めを処理するコードもありません。実際にどの文字列がバッファへ残るかは Windows API の結果に依存します。

根拠: `engine/include/strata/platform/commit.hpp:102-104,121-131`; `terminal/setup.py:1471-1489`; `terminal/strata_control/folders.py:31-41`; `terminal/serve/server.py:3040-3057`。

## 有効になる条件

- **エンジンの commit 推定:** `_WIN32` のビルドでのみ `commit_growth` の Windows 実装がコンパイルされる。さらに `STRATA_COMMIT_GROWTH` が設定され `std::atoi(value) == 0` になる場合（例: 空文字、`0`、`0anything`、数値に変換できない文字列）は先に `0` を返すため、`SystemDrive` は読まれない。未設定、または `atoi` が 0 以外になる値（例: `1`、`1anything`）なら Windows レジストリの `PagingFiles` が読めた場合に処理が続く。`?:` 形式の項目がない場合、`SystemDrive` はパスに使われない。
- **Terminal セットアップ:** `page_file_setting` は `WIN` のときだけ動作する。`PagingFiles` の取得失敗時は `None` を返す。`ExistingPageFiles` に有効なドライブ表記が一つでもあればそのドライブ群を使い、`SystemDrive` は参照しない。自動管理指定のページファイルがあり、既存ドライブ群が空のときに限って fallback に関わる。容量が 4 GB 未満ならセットアップがページファイルの警告を表示する経路がある。
- **フォルダー検査:** Windows で `folders.problem` からシステムルート候補を検査するときだけ、この値から追加ルートを作る。`SystemRoot`、`windir`、`ProgramFiles`、`ProgramFiles(x86)`、`ProgramW6432` の値も同時にルート候補になるため、そちらで判定されれば `SystemDrive` 由来の候補の影響はありません。
- **Vision 一時領域:** `Vision` の初期化時に `work_dir` が候補を順に試す。システム一時領域、カレントディレクトリが先で、SystemDrive のルートは3番目。候補を作成できない場合やパスに空白がある場合は次へ進み、最後に標準の一時領域を使う。

根拠: `engine/include/strata/platform/commit.hpp:102-131`; `terminal/setup.py:1471-1489,1499-1525,11928-11930`; `terminal/strata_control/folders.py:31-60`; `terminal/serve/server.py:3040-3057,3059-3062`。

## 実行時の詳細

- `commit_growth` は呼び出されるたびに `SystemDrive` を取得する。読み取りは Windows レジストリの `PagingFiles` を取得できた後で、`STRATA_COMMIT_GROWTH=0` 相当の早期 return より後段にある。結果は `?:` のパス置換と `GetDiskFreeSpaceExW` 等によるページファイル増加量の算出に使われ、その値は `commit_available` を介して Windows のメモリ/commit 予算に反映される。C++ 側に `SystemDrive` のキャッシュはない。複数箇所から `commit_growth` が呼ばれる（例: `engine/src/core/expert_source.cpp:414-427,604-617`; `engine/sycl/src/core/expert_source.cpp:245-258,362-375`）。
- Terminal の `page_file_setting` はセットアップ中のページファイル助言を作る際に呼ばれる（`terminal/setup.py:1499-1525,11928-11930`）。`SystemDrive` は関数呼び出し時に参照され、キャッシュされない。
- フォルダー検査は `problem` から `_system_roots` を呼ぶ都度環境を参照する。データフォルダー設定などの呼び出し元がシステムフォルダー判定を使う（例: `terminal/strata_control/folders.py:77-93`; `terminal/setup.py:7430-7436`; `terminal/strata_cli/launch/cmd.py:240-245`）。
- Vision の `work_dir` は `Vision.__init__` で一度呼ばれ、作った一時ディレクトリをその Vision インスタンスが使う。プロセス起動後に環境値を変更した場合、次回の関数呼び出し/インスタンス作成から再取得されるが、既存インスタンスの `self.dir` は変更されない（`terminal/serve/server.py:3040-3062`）。
- `tools/packaging/smoke_terminal.py:56-65` は Windows の隔離環境を組み立てる際に、親環境の `SystemDrive` を子プロセス環境へ転送し、未設定なら `C:` を渡す。これは packaging smoke tool 内の処理であり、一般実行時の Strata engine 設定ではない。

## ログと測定値

`SystemDrive` の値そのものを出すログや専用エラーは見当たらない。`commit_growth` の失敗条件（Windows API/レジストリ失敗等）は `0` を返すだけで、この関数内のログはない（`engine/include/strata/platform/commit.hpp:102-120,131-149`）。ただし Windows の `log_complement_memory` はメモリ状況を出力し、「page files may grow by ... more」を含める（`engine/src/core/expert_source.cpp:604-617`、SYCL は `engine/sycl/src/core/expert_source.cpp:362-375`）。この表示は `SystemDrive` の文字列や個別ドライブを示さない。

`folders.problem` が指定フォルダーをシステムフォルダーと判定した場合、呼び出し元が理由を返すかエラー表示に使う。たとえば CLI 起動経路では `ValueError` を作る（`terminal/strata_cli/launch/cmd.py:240-245`）。Vision の `work_dir` は候補の失敗・空白をログせず次候補へ進む（`terminal/serve/server.py:3046-3057`）。Terminal セットアップはページファイル容量が 4 GB 未満なら助言文を `warn` に渡す（`terminal/setup.py:11928-11930,1516-1525`）。

Strata の `docs/DETAILS.md` および関連設計資料に、`SystemDrive` の読み取りや値域についての説明は見つからなかった。測定値は記載しない。

## 根拠

- `engine/include/strata/platform/commit.hpp:102-149` — Windows 専用のページファイル増加量推定、`STRATA_COMMIT_GROWTH` の早期分岐と `SystemDrive` の `?:` 置換。
- `engine/src/core/expert_source.cpp:414-427,604-617`; `engine/sycl/src/core/expert_source.cpp:245-258,362-375` — commit 予算への接続とメモリ診断ログ。
- `terminal/setup.py:1467-1491,1499-1525,11928-11930` — セットアップのページファイル drive fallback、容量算出と警告経路。
- `terminal/strata_control/folders.py:31-60,77-93` — Windows システムルート候補とフォルダー判定。
- `terminal/setup.py:7430-7436`; `terminal/strata_cli/launch/cmd.py:240-245`; `terminal/strata_control/discovery.py:484-497` — フォルダー判定の呼び出し例。
- `terminal/serve/server.py:3039-3062` — Vision encoder 一時ディレクトリ候補の選択と初期化。
- `tools/packaging/smoke_terminal.py:56-81` — Windows smoke tool が隔離環境へ値を転送する処理。
