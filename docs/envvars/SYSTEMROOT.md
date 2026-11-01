# `SYSTEMROOT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の作業ツリーは `main...origin/main` で未コミット変更なし。Windows の慣例に合わせ、同じ環境変数の大小文字違い `SystemRoot` も検索・確認した。

## 役割

Windows のシステムディレクトリを組み立てるために使われる。Strata host は `tar.exe` / `where.exe` の場所を決め、Control と MCP installer はモデル用データを置けないシステムフォルダーを判定する。エンジン起動に失敗した場合は DLL の所在診断にも使う。CUDA/HIP/SYCL の計算設定ではない。

## 値と判定

読み取り方は経路ごとに異なる。数値変換や文字列正規化は行わない。

| 経路 | 未設定・空文字 | 優先順位・効果 |
|---|---|---|
| Host の Windows ツールパス | `SystemRoot` と `SYSTEMROOT` が空または未設定なら `windir`、それも空なら `C:\Windows` | `SystemRoot` → `SYSTEMROOT` → `windir` → `C:\Windows`。選んだ文字列の末尾に `System32\tar.exe` または `System32\where.exe` を連結する。JavaScript の `||` 判定なので空文字は未設定同様。各呼び出し時に環境オブジェクトを参照する。(`apps/host/server/platform-paths.mjs:35-47`) |
| Control の保存先検証 | `SystemRoot` が空ならシステムルート一覧に加えない | Windows で `SystemRoot`, `windir`, `ProgramFiles`, `ProgramFiles(x86)`, `ProgramW6432` を順に追加し、別途 `SystemDrive`（既定 `C:`）由来のルートも追加する。検証対象がユーザーのホーム外でいずれかのルート内なら「system folder」として拒否する。(`strata_control/folders.py:27-37,63-80`) |
| MCP installer の保存先検証 | `SystemRoot` が空なら一覧から除外 | 同じく `windir` などと並べてシステムフォルダー一覧に加える。`data_dir` がその内側なら ToolError `data_dir ... is inside a system folder`。(`tools/strata_mcp.py:483-489,2234-2246`) |
| エンジン DLL 診断 | `SystemRoot` が空または未設定なら `C:\Windows` | `System32` とルート自体を DLL 検索候補にする。(`serve/loader_diag.py:67-78`) |
| Host のフォルダー選択・保護ファイル | 未設定または空文字なら `C:\Windows` | JavaScript の `||` fallback。Windows の folder chooser は `SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe` を起動する。秘密ファイルの ACL 操作は `SystemRoot\System32` の `whoami.exe` / `icacls.exe` を使う。(`apps/host/server/folder-dialog.mjs:76-95`, `apps/host/server/private-file.mjs:6-25`) |
| Chat 作業フォルダーの拒否 | 未設定なら null 合体演算子で `C:\Windows`。空文字は fallback されず空文字のまま | 値を小文字化し、そのパス自身または配下をプロジェクトフォルダーとして拒否する。(`apps/host/server/chat-files.mjs:17-26,46-53`) |
| Terminal の PowerShell installer | `$env:SystemRoot` をそのまま使う | `SystemRoot\System32\tar.exe` を先に `Get-Command` し、見つからない場合は PATH の `tar.exe`、さらに無ければ `Expand-Archive` に進む。ここでは `C:\Windows` の fallback はない。(`packaging/install.ps1:71-77,94-96`) |

`apps/desktop/scripts/stage-control.py` は `os.environ.get("SYSTEMROOT", "")` を読み、`--check` 時に起動する同梱 Python の環境へ `SYSTEMROOT` として渡す。未設定なら空文字を渡す（親の環境全体を渡すわけではない）。これは bundle の確認用スクリプト経路である。(`apps/desktop/scripts/stage-control.py:145-169`)

## 有効になる条件

- Host の `tarBinary()` / `whichCommand()` は `platform === 'win32'` のときだけシステムルートを使う。`tarBinary()` はエンジンアーカイブ展開時に呼ばれる。`whichCommand()` は Host の `which()` から呼ばれる。POSIX ではそれぞれ `/usr/bin/tar` と `/usr/bin/env which` を使い、`SYSTEMROOT` は参照しない。(`apps/host/server/platform-paths.mjs:39-47`, `apps/host/server/engine-install.mjs:153-160`, `apps/host/server/util.mjs:54-58`)
- Windows の folder chooser は選んだ Shell パスで PowerShell を起動する。起動に失敗した場合は「Windows PowerShell was not found.」または「The folder chooser could not open.」を返し、`noDialog` の場合は手入力を促す。Windows で秘密ファイルを保護するときは `whoami.exe` / `icacls.exe` を使う。(`apps/host/server/folder-dialog.mjs:76-95`, `apps/host/server/private-file.mjs:6-25`)
- Chat の `refusedFolder()` は Windows で選択済み `SystemRoot` パス配下を拒否し、`createChatFolders().set()` が `folder-refused` エラーとして返す。Program Files / ProgramData も環境変数に関係なく固定パターンで拒否する。(`apps/host/server/chat-files.mjs:17-26,46-53`)
- Control / MCP の保存先検証では Windows のときのみ `_system_roots()` / `system_folders()` が `SystemRoot` を列挙する。Windows 以外は固定の POSIX パス一覧を使う。(`strata_control/folders.py:27-37`, `tools/strata_mcp.py:483-489`)
- DLL 診断はエンジン起動失敗のうち Windows loader failure status で、対象実行ファイル名がある場合に限る。`missing_note()` が失敗 DLL を特定できた場合、起動エラー文に `The engine is missing a file it needs (...)` を加える。診断全体が例外を出しても `start_exit_note()` は握りつぶす。(`serve/server.py:620-641`, `serve/loader_diag.py:97-105`)
- Coding Harness の子プロセス環境では `SYSTEMROOT` は `KEEP` の許可名に含まれ、secret 名でなければ環境のフィルターを通る。これは値を解析する処理ではなく、ホスト環境（AppImage の場合は元の環境）の値を子へ残す処理である。追加環境 `extra` は後から同名キーを上書きする。(`apps/host/server/agent/harness-runtime.mjs:20-36,75-83`, `apps/host/server/external-env.mjs:64-71`)

## 実行時の詳細

Host 側では `tarBinary()` が Windows で `SystemRoot` 系の値から `tar.exe` を作り、engine installer がそのパスで展開コマンドを実行する。コマンド起動や展開で失敗すると installer の状態を `error` にし、`state.error = err.message`、`stage = 'Engine install failed'` としてイベントを送信した後、例外を再送出する。環境値自体を検査する専用ログはない。(`apps/host/server/platform-paths.mjs:35-42`, `apps/host/server/engine-install.mjs:153-178`)

保存先検証は `SystemRoot` をシステム領域一覧に足すだけで、変数値のパースや cache はしない。Control の `problem()` は拒否理由を返し、その文面は `words()` が結合する。MCP の `check_data_dir` は該当時に `ToolError` を投げる。ユーザーが別の環境変数 `windir` などを設定していれば、その値も別ルートとして併用され、`SystemRoot` を置き換えない。(`strata_control/folders.py:27-37,63-80,103-104`, `tools/strata_mcp.py:483-489,2234-2246`)

## 根拠

- `apps/host/server/platform-paths.mjs:35-47` — host の優先順位、空文字 fallback、Windows 限定のツールパス。
- `apps/host/server/folder-dialog.mjs:76-95`, `apps/host/server/private-file.mjs:6-25`, `apps/host/server/chat-files.mjs:17-26,46-53` — Shell 起動、秘密ファイル保護ツールの場所、Chat 作業フォルダーの拒否。
- `apps/host/server/engine-install.mjs:153-178`, `apps/host/server/util.mjs:54-58` — パスの呼び出し元と失敗結果。
- `strata_control/folders.py:27-37,63-80,103-104` — Control の Windows system-root 判定と利用者向け拒否文。
- `tools/strata_mcp.py:483-489,2234-2246` — 同梱 MCP installer のシステムフォルダー拒否。
- `serve/server.py:620-641`, `serve/loader_diag.py:67-105` — 起動エラー時に限った DLL 診断と出力文。
- `packaging/install.ps1:71-77,94-96` — Terminal installer の tar 選択と fallback。
- `apps/desktop/scripts/stage-control.py:145-169`, `apps/host/server/agent/harness-runtime.mjs:20-36,75-83`, `apps/host/server/external-env.mjs:64-71` — staging の明示転送と Harness の環境フィルター。
