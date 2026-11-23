# `PROCESSOR_ARCHITEW6432`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Windows 上で、32 bit プロセスから見たプロセッサ種別ではなく、Windows がプロセスへ渡した実機側のアーキテクチャを優先して扱うために使われる。参照箇所は Windows 用 PowerShell インストーラーと terminal の `strata_control.sysinfo._windows_machine()` の二つで、前者は配布アーキテクチャ判定、後者は Control が使う host platform の判定に使う（`tools/packaging/install.ps1:104-106`、`terminal/strata_control/sysinfo.py:55-78`）。

## 値と判定

| 経路 | unset / 空文字 | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Windows terminal の `sysinfo._windows_machine()` | `.get(key, "").strip()` の結果が空なら `PROCESSOR_ARCHITECTURE` を確認し、それも空なら Python の `sysconfig.get_platform()` に fallback する | 空でない値をそのまま採用。`AMD64` / `x86_64` は `AMD64`、`ARM64` / `aarch64` は `ARM64`、既知の x86・ia64 別名も対応表で正規化する | 値自体を拒否する検証はない。未知の非空値は trim 後の文字列のまま返る。`" amd64 "` は `AMD64`、`"mystery"` は `mystery`、`"  "` は未設定扱い |
| Windows PowerShell インストーラー | `PROCESSOR_ARCHITEW6432` が未設定または PowerShell で false と評価される場合、`PROCESSOR_ARCHITECTURE` を使う | 選択された `$arch` が `AMD64` と等しい場合に続行する（PowerShell の既定の文字列比較は大文字小文字を区別しないため `amd64` も一致する） | 選択値が `AMD64` と一致しない場合は拒否する。空白付き `" AMD64 "` や `ARM64`、未知値は一致せず拒否される |

terminal 側は文字列を数値変換せず、strip 後に小文字化して別名辞書を引く。辞書にない値もエラーにせず返す。優先順位は `PROCESSOR_ARCHITEW6432`、`PROCESSOR_ARCHITECTURE`、Python の build tag の順で、最初の非空値が採用される（`terminal/strata_control/sysinfo.py:60-73`）。インストーラー側は先頭変数が PowerShell の false 値でない限りそれを選び、選択値が `AMD64` でなければ拒否する（`tools/packaging/install.ps1:104-105`）。

## 有効になる条件

- インストーラーでの判定は Windows 専用で、OS 判定を通過した後に実行される。OS が `Win32NT` でなければ、この変数を読む前に Windows installer ではない旨を `Die` で出して停止する（`tools/packaging/install.ps1:103-105`）。
- terminal 側の参照は `sys.platform.startswith("win")` の場合だけ使われる。それ以外の OS では `platform.machine()` の値を使い、この変数は参照されない（`terminal/strata_control/sysinfo.py:24-25, 76-78`）。
- terminal の `targets.host_platform()` は sysinfo の system と machine から `windows-amd64` 等を正規化し、engine resolver は `target` 引数が指定されていなければこの host platform を使う。明示的な `target` は host 判定を上書きする（`terminal/strata_control/targets.py:33-45`、`terminal/strata_control/engine_component.py:1136-1142`）。
- 対応 backend 表に Windows ARM64 は含まれず、Windows の CUDA / HIP / CPU 対応 target は `windows-x86_64` である。ARM64 または未対応の未知値が host target になれば、その target に一致する engine が見つからないなどの理由で engine 解決に失敗し得る（`terminal/strata_control/targets.py:22-30`、`terminal/strata_control/engine_component.py:1161-1168, 1200-1216`）。
- インストーラーには CLI のアーキテクチャ上書き経路はなく、`AMD64` を受け入れた後の配布 platform は `windows-x86_64` 固定である（`tools/packaging/install.ps1:104-106`）。

## 実行時の詳細

terminal の `_windows_machine()` は呼び出しごとに `os.environ.get()` を実行し、値を関数内やモジュール変数へ cache しない。従ってプロセス内で環境を変更した場合は次の呼び出しで反映される。`PROCESSOR_ARCHITEW6432` の非空値が `PROCESSOR_ARCHITECTURE` より優先され、両方が空の場合だけ Python build tag から `ARM64` / `AMD64` 等を推定する。build tag の取得が例外になれば空文字として扱い、`win32` または空 tag は `x86` を返す（`terminal/strata_control/sysinfo.py:55-78`）。

インストーラーはスクリプト実行時に一度 `$arch` を決める。`PROCESSOR_ARCHITEW6432` が false なら `$env:PROCESSOR_ARCHITECTURE` へ fallback し、選択値が `AMD64` と異なれば `$platform` 設定、manifest 取得およびダウンロードに進む前に停止する。受け入れ後は `$platform = 'windows-x86_64'` を使って manifest の行を選ぶ（`tools/packaging/install.ps1:104-106, 119-125`）。

## ログと測定値

インストーラーが `AMD64` 以外と判定した場合、`Die` は stderr に `strata installer: this computer ($arch) is a Windows on ARM PC. Strata needs an NVIDIA or AMD graphics card and has no engine for ARM processors, so it could not run a model here. Run this installer on a Windows PC with an Intel or AMD processor (x64) and one of those cards.` を出し、例外を投げて停止する。この判定は manifest 取得・ダウンロードより前にある（`tools/packaging/install.ps1:24, 104-105, 119-125`）。

terminal の sysinfo 自体はこの判定に関するログを出さず、host platform 文字列を呼び出し元へ返す。engine resolver で対象 engine がない場合は `EngineMissing` の理由に PC と一致しない package 等が入り、例外メッセージは `No engine for this PC was found ...` で始まる（`terminal/strata_control/sysinfo.py:76-78`、`terminal/strata_control/engine_component.py:70-88, 1161-1168, 1200-1216`）。Strata の資料にこの環境変数に関する測定値はない。

## 根拠

- Windows terminal の値取得、正規化、fallback: `terminal/strata_control/sysinfo.py:55-78`。
- terminal の OS / architecture host target 化と backend 対応表: `terminal/strata_control/targets.py:22-45`。
- engine target の既定、platform 照合、失敗経路: `terminal/strata_control/engine_component.py:1136-1144, 1161-1168, 1200-1216`。
- Windows installer の OS guard、値選択、x64 拒否、固定 platform、manifest 選択: `tools/packaging/install.ps1:103-106, 119-125`。
