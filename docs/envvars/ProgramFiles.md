# `ProgramFiles`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Windows 上で標準の Program Files ディレクトリを参照し、cloudflared と NVML DLL の探索候補、システム領域の判定、エージェントの成果物追跡除外範囲を組み立てます。Windows 用 vision build スクリプトでは Visual Studio 2022 の探索候補にも使います。Strata は値を数値や真偽値に変換せず、パスの一部として扱います。

## 値と判定

参照箇所ごとに未設定・空文字の扱いが異なります。空白の trim、パスの存在確認による環境変数値の補正、値の正当性検証はありません。

| 経路 | 未設定 | 空文字 | 設定値の使い方 |
|---|---|---|---|
| Python cloudflared 探索 | `C:\Program Files` を使う | 空の root として `cloudflared\cloudflared.exe` を候補化 | `ProgramFiles\cloudflared\cloudflared.exe` を候補に追加 |
| Windows telemetry | `C:\Program Files` を使う | `NVIDIA Corporation\NVSMI\nvml.dll` を候補化 | 値に `NVIDIA Corporation\NVSMI\nvml.dll` を連結 |
| Control のモデル保存先検査 | この変数由来の root を追加しない | 同左 | root の一覧にそのまま追加 |
| MCP の保存先検査 | root の一覧に追加しない | falsy 値として除外 | 絶対パス等への正規化後、root の一覧に追加 |
| Host agent の成果物追跡 | `undefined` として除外 | falsy 値として除外 | tracker の除外候補に追加 |
| Windows vision build batch | `%ProgramFiles%` 展開値で候補を作る。既定値の補完なし | prefix が空の候補になる | Visual Studio 2022 BuildTools / Community の候補パスに展開 |

Windows 以外では Python cloudflared 探索はこの変数を参照せず、telemetry は `os.name == "nt"` のときだけ Windows 用候補を作ります。Control と MCP の各システム root 関数も Windows 判定のときだけ環境変数を列挙します。Host agent は渡された `env` オブジェクトから値を取り、既定の `env` は `process.env` です。

## 有効になる条件

- **Python cloudflared 探索**: Windows で、`STRATA_CLOUDFLARED` に空でない明示パスがない場合に候補へ加わります。`PATH` の候補が先に調べられ、Program Files の候補は `ProgramFiles(x86)` の候補とともにその後に調べられます。ファイルが見つからない、または実行・バージョン条件を満たさない場合は次の場所へ進みます。探索全体で見つからなければ、呼び出し元は `cloudflared is not installed` の案内を返します。Linux/macOS ではこの Windows 分岐を通りません。`strata_cli/launch/access.py:70-94,124-137,242-255,270-274`。
- **Host app の cloudflared 探索**: `apps/host/server/cloudflared-find.mjs` も Windows で `env.ProgramFiles ?? 'C:\\Program Files'` を使います。`null` / `undefined` は既定値になりますが、空文字は既定値に置き換わりません。Strata 自身・component の候補と PATH の後で通常の場所として候補化し、`STRATA_CLOUDFLARED` が truthy なら単一候補で早期 return、`STRATA_CLOUDFLARED_SEARCH === 'own'` なら自前フォルダー候補の後で探索を終了します。候補は順に実行可能ファイル・バージョンを調べ、見つからなければ `found: null` を返します。`apps/host/server/cloudflared-find.mjs:42-70,95-110`; installer からの呼び出しは `apps/host/server/cloudflared-install.mjs:34-43`。
- **NVML telemetry**: Windows で、かつ AMD backend ではない GPU reader を作る経路に限ります。最初に名前だけの `nvml.dll` をロードし、失敗時に Program Files 配下の候補を試します。そのため、先の候補がロードできれば `ProgramFiles` の値は使用結果に影響しません。Program Files 配下を含む候補でも reader が初期化できない場合、GPU reader は無効になります。Telemetry は無効 reader を通常の GPU 読み取り対象から外し、GPU 情報なしで CPU/RAM 等の記録を続けます。`serve/telemetry.py:36-64,348-355,535-589`; 起動経路は `serve/server.py:5247-5255,8854-8857`。
- **モデル保存先のシステム領域検査**: `strata_control.folders.problem()` が Windows 上で指定されたフォルダーを検査するときに参照します。指定先が Program Files root 配下で、利用者のホーム配下ではない場合はシステムフォルダーとして拒否します。環境変数が未設定または空でも `SystemDrive` 由来の Windows 固定候補（`<drive>\Program Files` 等）は別途検査されます。CLI は理由を表示し、値を保存しません。`strata_control/folders.py:27-37,63-80`; CLI 呼び出しは `strata_cli/launch/cmd.py:233-238` と `strata_cli/launch/screens.py:882-889`。
- **MCP の保存先検査**: `strata_install` の `data_dir` が既存の許可先でない場合に、Windows のシステム領域一覧に加わります。配下のパスは `ToolError("data_dir ... is inside a system folder")` で拒否されます。ProgramFiles が未設定または空ならこの root は加わりません。`tools/strata_mcp.py:483-489,2269-2293`。
- **Host agent の成果物追跡**: 各 agent turn の tracker を作る際に `ProgramFiles` を除外候補として渡します。tracker はこの root 配下を成果物探索から除外します。値が未設定または空なら候補に入りません。`apps/host/server/agent/agent-bridge.mjs:121-140,364-378`; 適用は `apps/host/server/agent/deliverables.mjs:52-85`。
- **vision build batch**: `where cl` で compiler が見つからない場合に限って、Windows の batch 展開で Program Files 配下の Visual Studio 2022 を探します。見つけた場合 `vcvars64.bat` を呼び、最後まで `cl.exe` が見つからなければ batch はエラー終了します。`packaging/build_vision_windows.bat:43-49`。

## 実行時の詳細

Python cloudflared 探索は `os.environ.get("ProgramFiles", default)` で値を取得するため、未設定時だけ既定値になり、空文字は保持されます。各探索呼び出しで候補一覧を組み直します。cloudflared のバージョン結果は `path` と更新時刻でプロセス内キャッシュされますが、候補 root 自体の値をキャッシュする処理はありません。別経路の `STRATA_CLOUDFLARED` が非空ならその単一候補を返し、ProgramFiles の候補を作りません。`strata_cli/launch/access.py:70-94,97-115`。

Host app の探索は `env` 引数で環境オブジェクトを受け、既定値は `process.env` です。`createConnectorInstaller` はその `env` を `findConnector` へ渡します。ProgramFiles の値は探索のたびに候補生成時に読み、候補パスは同モジュール内でキャッシュしません。`STRATA_CLOUDFLARED` や検索制限が候補処理を短絡すると、この値は参照されても探索結果には使われません。`apps/host/server/cloudflared-find.mjs:42-70,95-110`; `apps/host/server/cloudflared-install.mjs:34-43`。

Windows telemetry も `os.environ.get` を使い、値の取得は `_Nvml` reader の生成時です。`Telemetry` は server 起動時に作成されます。環境変数を後から変更しても、すでに作成済み reader の候補パスは再評価されません。NVML の候補ロード・初期化に失敗しても、この変数に関する警告は出しません。通常の sampling 例外が起きた場合は `[strata] metrics: a sample failed (...)` を一度出して sampling を継続しますが、これは ProgramFiles の失敗専用ログではありません。`serve/telemetry.py:36-64,535-589,648-672`; `serve/server.py:5247-5255,8854-8857`。

Control と MCP の root 一覧は各検査時に環境から読み直します。Control では空文字は `if value` で除外し、MCP も `if p` で除外します。MCP の実行中に検査が拒否されると `ToolError` になります。`strata_control/folders.py:27-37,63-80`; `tools/strata_mcp.py:483-489,2269-2293`。

Host agent は `createAgentBridge` に渡された `env` を保持し、turn ごとの `trackerFolders()` 呼び出しで `ProgramFiles` を読むため、その値は成果物追跡の除外リストに反映されます。ここでは Program Files の存在確認や実ディレクトリの列挙はせず、成果物 tracker に除外 root として渡すだけです。`apps/host/server/agent/agent-bridge.mjs:121-140,364-378`; `apps/host/server/agent/deliverables.mjs:52-85`。

候補一覧にある `ProgramFiles(x86)` は別名として各所で独立して読まれます。`setup.py:2363` は `ProgramFiles(x86)` のみを `vswhere.exe` のパス構築に使い、`ProgramFiles` の読み取りではありません。テスト内の名前出現は実装挙動の根拠にしていません。

## 根拠

- 候補名の全参照と用途: `strata_cli/launch/access.py:83-84`; `serve/telemetry.py:36-40`; `tools/strata_mcp.py:483-489`; `strata_control/folders.py:27-37`; `apps/host/server/cloudflared-find.mjs:43-70`; `apps/host/server/agent/agent-bridge.mjs:135-140`; `packaging/build_vision_windows.bat:43-49`。
- Host agent の `exclude` が tracker でサブツリー探索・成果物登録を除外する処理: `apps/host/server/agent/deliverables.mjs:52-85,111`。
- checkout 状態: 調査対象 Strata の `git rev-parse HEAD` は `ffa80d73133ea5c548aefe57889a16e8085a938f`、`git status --short --branch` は `## main...origin/main`（未コミット変更表示なし）。
