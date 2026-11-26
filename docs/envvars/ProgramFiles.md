# `ProgramFiles`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Windows の標準インストール場所を探すために読む環境変数です。アプリの cloudflared 探索と Terminal CLI の cloudflared 探索では候補ディレクトリを組み立て、フォルダー判定では Windows のシステム領域に含まれるかを判定し、Terminal の Monitor は NVML DLL の候補パスを組み立てます。Strata が `ProgramFiles` を設定・変更する処理は確認できません。

アプリの agent file tracker は `ProgramFiles` を除外フォルダー一覧にも加えます。チャットの workspace 内にそのフォルダーがある場合、tracker はそこを走査せず、生成物として報告しません（`app/host/server/agent/agent-bridge.mjs:181-190,529-535`、`app/host/server/agent/deliverables.mjs:90-123`）。

加えて、Windows 用の開発・配布スクリプトが Visual Studio の場所を探すために参照します。これらは利用者向け実行時設定ではなく、ビルドや開発チェックの経路です（`tools/packaging/build_cuda_windows.py:43-45`、`tools/packaging/build_vision_windows.bat:40-44`、`tools/check:161-189`）。

## 値と判定

| 読み取り箇所・条件 | 未設定 | 設定時の扱い |
|---|---|---|
| アプリの cloudflared 探索、Windows (`app/host/server/cloudflared-find.mjs:43-48,58-64`) | `ProgramFiles` は `C:\\Program Files` を使う | 空文字を含め値をそのまま root として候補パスに連結。文字列の検証・正規化・大小文字判定はせず、Windows パスとして候補を作る |
| Terminal CLI の cloudflared 探索、Windows (`terminal/strata_cli/launch/access.py:122-146`) | `C:\\Program Files` を使う | 空文字を含め値をそのまま `Path(root) / "cloudflared" / name` に使う。検証・正規化なし |
| 保存先のシステム領域判定、Windows (`terminal/strata_control/folders.py:31-41`) | 値なしとして root 一覧に加えない | 空文字は偽として無視し、非空値を root に加える。パス比較時は `normcase(normpath(...))` を使う |
| MCP のデータ保存先チェック、Windows (`terminal/tools/strata_mcp.py:566-572`) | 値なしとして root 一覧に加えない | 空文字は後段で除外し、非空値を正規化して system folder 一覧に加える |
| Monitor の NVML DLL 探索、Windows (`terminal/serve/telemetry.py:41-52`) | `C:\\Program Files` を使う | 空文字を含め値を `NVIDIA Corporation\\NVSMI\\nvml.dll` の親 root に使う。値の検証なし |
| Windows 開発・配布スクリプト | Python の `os.environ.get` では各箇所に記載の既定パスを使う。batch は `%ProgramFiles%` を展開する | Python は未設定時だけ既定値。batch は環境変数の通常の展開結果を使う。値の追加検証なし |

これらは bool や数値として parse されません。`1`、`0`、`true`、`false`、`0anything` は文字列のままパス部品として扱われます。大文字小文字を変換する判定もありません。空文字は各箇所で異なり、Node.js の `??` と Python の `dict.get(key, default)` は空文字を fallback にしませんが、フォルダー一覧では空文字を除外します（`cloudflared-find.mjs:61-64`、`access.py:135-140`、`folders.py:35-41`、`strata_mcp.py:566-572`）。

## 有効になる条件

- アプリの connector 探索では `platform === 'win32'` の場合だけ `ProgramFiles` が参照されます。探索の優先順位は Strata の connector フォルダー、任意 component フォルダー、`PATH`、その後のシステム候補です。`STRATA_CLOUDFLARED` が truthy ならその単一パスで早期 return し、`STRATA_CLOUDFLARED_SEARCH === 'own'` なら Strata 自身の候補までで探索を止めるため、いずれも `ProgramFiles` の候補に進みません（`app/host/server/cloudflared-find.mjs:43-64`）。見つかった候補は実行可能性と `--version` 出力を検査し、見つからない・起動できない・古い場合は探索結果の `found` が null になり、スキップ理由を返します（同 `:95-110`）。
- Terminal CLI の cloudflared 探索も Windows のみです。`STRATA_CLOUDFLARED` が空でない場合はそれだけを返し、それ以外は `PATH` を先に探索します。Program Files の候補が有効でないと次候補へ進み、条件を満たす cloudflared がなければ `None` になります（`terminal/strata_cli/launch/access.py:122-146,176-189`）。アクセス方法一覧では cloudflared がない旨を表示し、トンネル開始時には導入案内を返します（同 `:294-320,327-330,438-445`）。
- `strata_control.folders.problem()` が Windows で使われる場合、`ProgramFiles` 配下はシステム領域候補です。指定データフォルダーがその領域内にあり、ユーザー home 配下でなければ問題として返します。CLI の `--data-dir` はこの問題を `ValueError` にし、画面のフォルダー選択も理由を表示します（`terminal/strata_control/folders.py:31-60,77-94`、`terminal/strata_cli/launch/cmd.py:240-245`、`terminal/strata_cli/launch/screens.py:948-950`）。`SystemRoot`、`windir`、`ProgramFiles(x86)`、`ProgramW6432`、`SystemDrive` と固定の Windows パスも同時に調べるため、`ProgramFiles` の値だけで判定が決まるとは限りません（`folders.py:31-41`）。
- MCP の `strata_install` に `data_dir` が渡され、Windows で候補がシステム folder 配下か判定するとき、`ProgramFiles` が root 集合に入ります。既存の現在データディレクトリーなど特別扱いされるパスはこの判定より前に通過します。該当すれば `ToolError("data_dir ... is inside a system folder")` になります（`terminal/tools/strata_mcp.py:566-572,2478-2502`）。
- Monitor の NVML 探索は Windows 上で NVIDIA reader を作るときに有効です。AMD reader または macOS reader ではこの `ProgramFiles` のコード経路を通りません。Linux では別名の共有ライブラリ候補を使います（`terminal/serve/telemetry.py:41-52,1417-1430,1433-1445`）。
- ビルド・開発経路では、CUDA Windows package builder が指定値を Visual Studio 2022 の BuildTools / Community 候補に使い、`build_vision_windows.bat` は `cl` が PATH にないときに同じ場所を探索します。`tools/check` は `cl` が `base_env` の PATH にない場合に Visual Studio 2022 の `vcvars64.bat` を探します。`ProgramFiles` が不正・空で候補が見つからない場合、後続のビルド確認で失敗するか、`tools/check` は `no C++ compiler: cl is not on PATH and Visual Studio 2022's vcvars64.bat was not found` を返します（`tools/packaging/build_cuda_windows.py:43-45`、`tools/packaging/build_vision_windows.bat:40-46`、`tools/check:161-189`）。

## 実行時の詳細

- アプリの `createConnectorInstaller` は既定で `process.env` を受け取り、`look()` ごとに `findConnector()` を呼びます。ProgramFiles の値自体を別変数へ cache していません。Windows 候補は `cloudflared\\cloudflared.exe` を追加し、`ProgramFiles(x86)` の候補も別に追加します。Strata の directory / component / PATH に有効な connector があればそちらが優先です（`app/host/server/cloudflared-install.mjs:34-45`、`cloudflared-find.mjs:43-70,95-110`）。
- Terminal CLI は `cloudflared_info()` の呼び出し時に環境を読み、`options()`、`missing_helper()`、`start_tunnel()` が探索結果を使います。ProgramFiles の値を cache しません。一方、`cloudflared_version()` は実行結果を `(path, mtime)` キーで `_cf_seen` に cache します。これは候補の探索結果や環境変数値の cache ではありません（`terminal/strata_cli/launch/access.py:119-124,149-167,176-189,294-300,327-330,438-445`）。
- `folders._system_roots()` と `strata_mcp.system_folders()` は呼び出しごとに `os.environ` を参照します。`folders.problem()` は Windows に限らず呼ばれますが、Windows 環境変数 root の分岐は `os.name == "nt"` の場合だけです。これらの関数には値の static cache はありません（`terminal/strata_control/folders.py:31-60,77-94`、`terminal/tools/strata_mcp.py:566-572,2478-2502`）。
- Monitor は `Telemetry.__init__()` で各 GPU の `monitor_reader()` を一度作成し、reader を保持してサンプルに使います。NVML 初期化時には最初に `nvml.dll`、次に ProgramFiles 配下の DLL を `ctypes.CDLL` で試します。どちらもロードできない場合 `_Nvml.ok()` は false となり、Linux の場合だけ Intel reader への fallback があります。ここでは ProgramFiles は DLL 候補パスの構成にのみ使われ、NVML 自身の環境変数解釈は説明対象に含めません（`terminal/serve/telemetry.py:41-69,1417-1430,1704-1726`）。
- 開発スクリプトでは `tools/check.msvc_env()` の成功・失敗結果を `_vc_env` に cache します。`terminal/setup.py` の `find_vcvars()` は `ProgramFiles(x86)` だけを参照し、`STRATA_VCVARS` が truthy ならそれを優先するため、これは `ProgramFiles` の読み取り箇所ではありません（`tools/check:158-189`、`terminal/setup.py:2674-2699`）。

## ログと測定値

ProgramFiles 自体について値を記録するログや測定値はありません。探索が失敗した後の cloudflared 不在表示・導入案内、保存先の拒否文言、`tools/check` の compiler 不在理由は上記の条件で発生します。Monitor は DLL 候補の `ctypes.CDLL` が `OSError` になると次候補へ進み、すべて失敗してもこの箇所ではログを出しません（`terminal/serve/telemetry.py:46-52`）。

## 根拠

- `app/host/server/cloudflared-find.mjs:43-70,95-110`
- `app/host/server/cloudflared-install.mjs:34-45`
- `app/host/server/agent/agent-bridge.mjs:181-190,529-535`
- `terminal/strata_cli/launch/access.py:119-146,149-189,294-320,327-330,438-445`
- `terminal/strata_control/folders.py:31-60,77-113`
- `terminal/tools/strata_mcp.py:566-572,2478-2502`
- `terminal/serve/telemetry.py:41-69,1417-1430,1704-1726`
- `tools/packaging/build_cuda_windows.py:43-45`
- `tools/packaging/build_vision_windows.bat:40-46`
- `tools/check:158-189`
- `terminal/setup.py:2674-2699`、`terminal/tools/hip/build_windows.bat:60-65`（`ProgramFiles(x86)` のみ。対象変数との部分一致を確認）

検索で見つかった `app/host/tests/cloudflared-find.test.mjs` と `terminal/tests/terminal/test_cloudflared_find.py` の参照は、テスト入力の疑似環境辞書です。環境から値を読む本番処理の根拠にはしていません。
