# `WINDIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の Strata 作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

Strata の Windows 向けコードが Windows ディレクトリの場所を参照したり、Windows のシステム領域をデータ保存先として拒否したりするために使います。また、Web アプリが起動するエージェント子プロセスへ、許可された環境変数として値を渡します。GPU backend やモデル計算の設定ではありません。

## 値と判定

| 読み取り箇所 | 未設定 | 空文字 | 設定値の扱い |
|---|---|---|---|
| `strata_cli/consoleinfo.py` | `C:\\Windows` を代用 | 空文字をそのまま使い、`Fonts` を相対パスとして調べる | 値をパスとして `Fonts` を連結し、Cascadia Mono のファイルを探す。数値変換・内容検証なし |
| `strata_control/folders.py` | システムルート一覧に追加しない | falsy のため追加しない | `SystemRoot`、`windir` などとともに、データフォルダー拒否判定のルートへ追加 |
| `tools/strata_mcp.py` | システムフォルダー一覧に追加しない | falsy のため一覧から除外 | `SystemRoot`、`ProgramFiles` などとともに、インストール時の保存先検査に使う |
| `apps/host/server/platform-paths.mjs` | `SystemRoot` / `SYSTEMROOT` が空または未設定なら `C:\\Windows` を代用 | `SystemRoot` / `SYSTEMROOT` / `windir` の候補から空文字を飛ばし、すべて空なら `C:\\Windows` | 優先順 `SystemRoot` → `SYSTEMROOT` → `windir` で Windows のシステムツールのパスを組み立てる |
| `apps/host/server/agent/harness-runtime.mjs` | コピー元にキーがなければ子プロセスにも渡さない | 値が空でもキー名が許可リストに合えば空文字をコピー | 値の変換なし。許可リストに含まれる名前を値ごと子プロセス環境へコピー |

Windows の環境変数名は大文字小文字を区別しないため、Python 側で `windir` と綴られた参照も同じ Windows 変数を指します。JavaScript の許可リストは `/i` 付きで名前の大小文字を区別しません。値そのものの大小文字変換はありません。

## 有効になる条件

- `consoleinfo.cascadia_installed()` は Windows (`os.name == "nt"`) 以外で直ちに `False` を返します。Windows でも、レジストリの Fonts キーに Cascadia Mono が見つかるとそこで `True` を返すため、`WINDIR` によるファイル探索へ進みません。レジストリ探索後に該当項目がなく、例外もなく処理が続いた場合だけ、`WINDIR` または既定値の `Fonts` を検索します。
- `strata_control.folders._system_roots()` は Windows 以外では `WINDIR` を読みません。Windows では `SystemRoot` と `windir` を含む複数の既知ルートを集めます。`problem()` は指定先がいずれかのルート内で、実行ユーザーのホーム内ではない場合にシステムフォルダーとして拒否します。`setup.py` のデータフォルダー選択、および Terminal の `--data-dir` 検査から呼ばれます。
- `tools/strata_mcp.py` の `system_folders()` は `WIN` の場合だけ Windows 環境のルートを調べます。`check_data_dir()` が新しい保存先を検査する経路で使われ、指定先が検出したシステムフォルダー内なら `ToolError("data_dir ... is inside a system folder")` になります。`data_dir` を指定しない場合はこの検査を呼ばず、既定の保存先を使います。
- `platform-paths.mjs` のシステムルート解決は `tarBinary()` と `whichCommand()` が Windows (`platform === 'win32'`) 用のコマンドパスを作る場合に使われます。`tarBinary()` はエンジンアーカイブ展開時に呼ばれ、`whichCommand()` はホストの `which()` 経由で呼ばれます。環境値が選ばれると `System32\\tar.exe` または `System32\\where.exe` のパスに使われます。
- エージェント環境の継承は `HarnessProcess.start()` が子プロセスを起動するときに行います。`agentEnvironment()` は `externalEnvironment(base)` の各キーを許可名で絞り、許可された値をコピーします。AppImage の場合は `externalEnvironment()` が記録された元環境を優先して使います。ここでは `WINDIR` の値をパース・変更しません。

## 実行時の詳細

`strata_cli/consoleinfo.py:114-115` は、Fonts レジストリから Cascadia Mono を見つけられなかった場合に `WINDIR` を参照します。`classic_style()` は、Windows の従来型コンソールで明示的な glyph 強制設定がなく、現在のフォントが Cascadia Mono でもないときに `cascadia_installed()` を呼びます。見つかった場合はフォント切り替えを試し、結果に応じて全 Unicode 表示か従来表示かを決めます。この style はモジュールの `_cached` に保存され、以後の `classic_style()` 呼び出しでは再評価されません。主な呼び出し元は Monitor と launch widgets です。ファイルが見つからない場合は `False` となり、通常のフォント切り替え経路を通らず従来表示になります。環境変数の値に関するログ出力はありません。

`strata_control/folders.py:27-37,63-80` は、Windows では `SystemRoot` と `windir` をそれぞれ列挙して値が truthy のものだけルートに加えます。別途 `SystemDrive` が未設定なら `C:` とし、Windows と Program Files の既定パスも加えます。`problem()` はパスがそのルート内にあるかを検査します。`setup.py:6378-6395,6478-6487` では `--data-dir` 等で指定された保存先が不適切なら失敗し、過去に保存した設定値が不適切なら警告を出して既定の保存先へ戻します。`strata_cli/launch/cmd.py:226-231` も不適切な `--data-dir` を `ValueError` にします。

`tools/strata_mcp.py:483-489,2225-2249` の `system_folders()` も Windows では `SystemRoot` と小文字綴りの `windir` を含む環境値を集めますが、空値は除外し、`WINDIR` 専用の既定値は設けません。MCP の `strata_install` で明示された `data_dir` に対する検査に使われます。`check_data_dir()` は UNC パス、相対パス、`..` を含むパス、命名条件、親フォルダーの存在も別途検査します。システム領域内のパスは上記の `ToolError` で拒否されます。

`apps/host/server/platform-paths.mjs:35-46` の `systemRoot()` は truthy な候補を順に選ぶため、空文字は次候補へ進み、すべて未設定または空なら `C:\\Windows` になります。呼び出し元の `apps/host/server/engine-install.mjs:160` は `tarBinary()` のパスでアーカイブを展開し、`apps/host/server/util.mjs:55-56` は `whichCommand()` のコマンドを実行します。Strata は環境値からコマンドパスを組み立てるだけで、環境変数の妥当性確認や独自の診断ログは行いません。

`apps/host/server/agent/harness-runtime.mjs:20-36,75-83` では `WINDIR` は子プロセスへ渡してよい環境名の正規表現に含まれています。`agentEnvironment()` は `externalEnvironment(base)` からの値をコピーし、`HarnessProcess.start()` がその結果を `spawn()` に渡します。起動ごとに環境を組み立てるため、読み取り結果の静的キャッシュはありません。`extra` は最後に展開され、同名キーがあればコピー値を上書きできます。

なお `apps/desktop/src-tauri/nsis/installer.nsi:713` にも `$WINDIR` という表記がありますが、これは NSIS スクリプト内の Windows ディレクトリ変数として PowerShell のパスを作る箇所であり、Strata の `getenv` / `os.environ` による環境変数読み取りではありません。`metal/src/mtl_rt.mm:1075` は `newIndirectCommandBuffer` 内の部分一致で、環境変数への参照ではありません。

## 根拠

- Cascadia Mono の検索・既定値: `strata_cli/consoleinfo.py:95-115,161-178`。Monitor と launch widgets の利用: `strata_cli/monitor.py:141-143`、`strata_cli/launch/widgets.py:43-55`。
- データ保存先の保護: `strata_control/folders.py:27-46,63-80`、`setup.py:6378-6395,6478-6487`、`strata_cli/launch/cmd.py:226-231`。
- MCP インストール先の保護: `tools/strata_mcp.py:483-489,2225-2249,2364-2364`。
- Windows システムツールのパス: `apps/host/server/platform-paths.mjs:35-46`、`apps/host/server/engine-install.mjs:160`、`apps/host/server/util.mjs:55-56`。
- 子プロセスへの環境継承: `apps/host/server/agent/harness-runtime.mjs:20-36,75-83`、元環境の選択: `apps/host/server/external-env.mjs:28-40,64-71`。
