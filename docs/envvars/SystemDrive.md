# `SystemDrive`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査対象 checkout の開始時状態は `main...origin/main` で、未コミット変更はありません。

## 役割

Windows でシステムドライブのルートを組み立てるために使われます。具体的には、モデル保存先のシステムフォルダー判定、Vision encoder の一時作業ディレクトリ候補、ページファイル情報の表示用推定、および DSV41 engine の Windows commit 余力計算に関係します。Strata が `SystemDrive` の一般的な値形式を検証する処理はありません。

## 値と判定

各呼び出し箇所が独立して値を読み、空文字や未設定の扱いは異なります。

| 箇所 | 未設定・空文字 | 値の使い方 |
|---|---|---|
| `strata_control/folders.py` | 未設定は `C:`。空文字はそのまま使われ、結果として `\Windows` などの候補を作る | 値に `\\Windows`、`\\Program Files`、`\\Program Files (x86)` を連結する。形式・ドライブ文字を検証しない |
| `serve/server.py` | 未設定は `C:`。空文字もそのまま使う | `os.sep` を連結して一時ディレクトリ候補にする。値を trim、parse、検証しない |
| `setup.py` | 未設定または空文字は `C:` に置換 | 先頭 1 文字を大文字化し、ドライブ文字として使う。残りの文字列は無視し、形式を検証しない |
| `include/strata/platform/commit.hpp` | バッファは `C:` で初期化されてから Windows API に読み取りを依頼する。戻り値を検査しない | `?:` 形式のページファイルパスの `?` を読み取った値に置換する。Strata 独自の parse、正規化、範囲検証はない |

数値変換や範囲境界はありません。値が不正な形式でも各箇所で文字列として連結・置換され、後続のパス/API 処理が失敗する場合があります。

環境変数の判定値を保持する cache はありません。Python の各関数呼び出し、C++ の各 `commit_growth()` 呼び出しでその時点のプロセス環境を参照します。

## 有効になる条件

- `strata_control/folders.py` では `os.name == "nt"` のときだけ `SystemDrive` を読みます。`problem()` は setup の `data_folder()` および `data_folder_in_place()` から呼ばれ、保存先が Windows の既知のシステム領域内かを判定します。ユーザーの home 以下はシステム領域判定から除外されます（`strata_control/folders.py:27-37,63-80`; `setup.py:6545-6563,6645-6654`）。
- `setup.py` のページファイル表示も Windows の場合だけ動きます。レジストリの `ExistingPageFiles` から実際のドライブが得られないときに限り、`SystemDrive` から自動管理ページファイルの対象ドライブを推定します。`STRATA_COMMIT_GROWTH=0` は C++ 側の別の commit 余力計算を無効にしますが、setup のページファイル表示には関与しません（`setup.py:1209-1224,1241-1255`; `include/strata/platform/commit.hpp:31-34`）。
- C++ の読み取りは `_WIN32` の `commit_growth()` 内にあります。DSV41 Windows 実装の `commit()` がこれを呼び、システム管理ページファイルの将来の増加余地を算出します。Linux など `_WIN32` 以外ではこの `commit_growth()` は `0` を返し、`SystemDrive` は読みません（`include/strata/platform/commit.hpp:31-32,50-60,79-82`; `src/dsv41/ds4_os.hpp:656-674`）。
- Vision encoder のディレクトリ選択は `Vision` が作られる経路で実行され、モデル設定に Vision がある場合に限られます。OS 判定はなく `SystemDrive` を参照し、最初にシステム temp、次に作業ディレクトリを試した後の候補として使います（`serve/server.py:2945-2963,9738-9755`）。

## 実行時の詳細

### 保存先の検査

Windows では `folders.problem()` が `SystemDrive` を読むたびにシステムルート候補を作ります。setup が指定された `--data-dir` を使う場合、その候補に含まれる保存先は `fail()` に渡され、「system folder」として保存を拒否します。以前保存した保存先が使えない場合は警告し、既定の `Strata-data` に戻します。`SystemDrive` の値だけを理由とする専用ログはありません（`strata_control/folders.py:27-37,78-80`; `setup.py:6557-6564,6651-6654`）。

### ページファイル

Windows setup の `page_file_setting()` はレジストリの `PagingFiles` と `ExistingPageFiles` を読みます。`ExistingPageFiles` にドライブが一つも列挙されなかった場合、未設定または空の `SystemDrive` は `C:` として扱い、それ以外は値の先頭文字を大文字にして自動管理ページファイルのドライブ候補にします。そのドライブの空き容量と `pagefile.sys` の現在サイズを調べ、`page_file_gb()` が 4 GB 未満と判断した場合は setup がページファイル警告を表示します。ここでの値はページファイル設定の推定に使われ、他の `ExistingPageFiles` エントリーを上書きしません（`setup.py:1157-1166,1189-1206,1209-1233,1241-1255,10016-10018`）。

### DSV41 の Windows commit 余力

`commit_growth()` はページファイル設定を Windows レジストリから読み、`?:` で始まるエントリーを `SystemDrive` とその後ろのパスで置き換えて、対象 volume の空き容量などから増加可能量を計算します。計算結果は DSV41 の `commit().avail` に現在の `ullAvailPageFile` と足されます。Strata は値をログに出しません。`STRATA_COMMIT_GROWTH` が文字列 `0` に `atoi` 変換される場合は早期 return するため、この経路では `SystemDrive` を読みません（`include/strata/platform/commit.hpp:31-33,40-77`; `src/dsv41/ds4_os.hpp:662-674`）。

### Vision encoder の一時領域

`Vision.work_dir()` は `SystemDrive` と OS のパス区切り文字から一時ディレクトリ候補を構成します。`tempfile.mkdtemp()` に失敗した候補は次へ進み、作成したディレクトリのパスに空白があれば削除を試みて次へ進みます。これらの候補が使えない場合はシステム temp 配下に空白を許す最終候補を作ります。`SystemDrive` 自体の失敗をログや終了理由にはしません（`serve/server.py:2945-2963`）。

`packaging/smoke_terminal.py:56-65` には別途、Windows smoke 用の子プロセス環境を作る処理があります。親環境の `SystemDrive` を取得し、未設定なら `C:` を子環境に設定します。これは smoke harness の環境組み立てであり、通常の Strata 実行時設定を変える処理ではありません。

## 根拠

- Windows のシステム保存先候補とパス検査: `strata_control/folders.py:27-37,63-80`; setup の呼び出し・失敗/既定値経路: `setup.py:6545-6564,6645-6654`。
- setup のページファイル取得・既定ドライブ・警告: `setup.py:1157-1183,1209-1233,1241-1255,10016-10018`。
- Windows C++ commit 余力のドライブ置換と DSV41 呼び出し: `include/strata/platform/commit.hpp:31-33,50-78`; `src/dsv41/ds4_os.hpp:656-674`。
- Vision encoder の一時作業ディレクトリと生成経路: `serve/server.py:2945-2963,9738-9755`。
- Windows smoke harness の環境転送: `packaging/smoke_terminal.py:56-65`。
