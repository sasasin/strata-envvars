# `ProgramData`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`ProgramData` は Strata の設定値として parse されるのではなく、Windows 上のパスとして参照される。主な用途は Chocolatey 配下の `cloudflared.exe` 候補を探すことと、MCP のインストール先検査で Windows のシステムフォルダーを列挙すること。Agent の成果物追跡では、値が設定されていればそのフォルダーを追跡対象から除外する。読み取り箇所は `terminal/strata_cli/launch/access.py`、`app/host/server/cloudflared-find.mjs`、`terminal/tools/strata_mcp.py`、`app/host/server/agent/agent-bridge.mjs` にある。`docs/DETAILS.md` にこの変数の説明は見つからなかった。

## 値と判定

値を真偽値や数値に変換する処理はない。各経路でパス結合またはパス正規化に使われ、空白除去・検証・範囲制限はされない。

| 経路・条件 | unset | 空文字 | 設定値と無効値の扱い |
|---|---|---|---|
| Python CLI の cloudflared 探索（Windows） | `C:\ProgramData` を既定のルートに使う | `Path("")` をルートにし、後続要素を連結する | 文字列をそのままパスとして使う。`0`、`1`、`true`、`false`、`0anything` も特別扱いせずパス要素になる。`STRATA_CLOUDFLARED` が空白以外を含む値ならその単独候補に切り替わり、`ProgramData` は参照されない。 |
| Node アプリの cloudflared 探索（Windows） | `C:\ProgramData` を既定のルートに使う | nullish ではないため既定値に置換されず、空のルートを `win32.join` に渡す | `env.ProgramData ?? 'C:\\ProgramData'` の値をパス結合する。文字列内容の検証はない。`STRATA_CLOUDFLARED` が truthy なら単独候補を返し、また `STRATA_CLOUDFLARED_SEARCH=own` または `search=false` なら通常候補だけで探索が止まり、この値を使うシステム候補へ進まない。 |
| MCP の `data_dir` 検査（Windows） | システムフォルダー一覧に `ProgramData` を加えない | `if p` のフィルターで除外される | truthy の値を `norm()` で正規化してシステムフォルダーとして照合する。加えて、入力 `data_dir` に `%ProgramData%` が書かれた場合は `os.path.expandvars()` が環境から置換する。値の内容や文字種を個別に検証しない。 |
| Agent の成果物追跡（全 OS のコード経路） | 除外リストに加えない | `.filter(Boolean)` で除外される | 値を追跡除外ディレクトリーとして渡す。真偽値相当以外の内容検証はない。実際に効くのはチャットの作業フォルダーの内側に当該パスがある場合。 |

Python CLI 側では環境変数名を `os.environ.get("ProgramData", r"C:\ProgramData")` で取得する。Node 側は `env.ProgramData ?? ...` を使い、未設定または `null` のときだけ fallback する。MCP 側は `os.environ.get(k)` の結果を truthy の場合だけ一覧に含める。Agent 側では関数に渡された `env`（既定値は `process.env`）のプロパティを直接読み、空値をフィルターで捨てる。いずれも値を parse しない（`terminal/strata_cli/launch/access.py:122-146`, `app/host/server/cloudflared-find.mjs:43-70`, `terminal/tools/strata_mcp.py:566-572`, `app/host/server/agent/agent-bridge.mjs:160,184-189`）。

## 有効になる条件

- **Python CLI の cloudflared 探索:** Windows の場合だけ `ProgramData` 配下の Chocolatey パス候補を追加する。`STRATA_CLOUDFLARED` が明示されるとその候補だけを返す。候補パスが実在するファイルであり、`cloudflared --version` の実行が受理される必要がある。PATH や他の通常ディレクトリーで先に有効な候補が見つかれば、後続候補は調べない（`terminal/strata_cli/launch/access.py:122-146,176-184`）。
- **Node アプリの cloudflared 探索:** `platform === 'win32'` で、検索が有効で、`STRATA_CLOUDFLARED` が truthy でない場合にだけ ProgramData 配下の候補を追加する。Strata 自身のフォルダー、コンポーネント、PATH、Program Files 等で先に使用可能な connector が見つかれば、それが返る（`app/host/server/cloudflared-find.mjs:43-70,95-110`; Installer は `app/host/server/cloudflared-install.mjs:34-50`）。
- **MCP のインストール先検査:** Windows で、指定された `data_dir` が現在のデータディレクトリー、Strata の管理対象フォルダー等の許可経路に該当しない新規パスである場合、親ディレクトリーと名前などの検査の後にシステムフォルダー一覧と照合する。候補が `ProgramData` 自身またはその配下なら `ToolError("data_dir {raw!r} is inside a system folder")` になる。Windows 以外ではこの環境変数を一覧に含めない（`terminal/tools/strata_mcp.py:566-572,2478-2501`）。
- **Agent の成果物追跡:** `createAgentBridge` の `env` 引数（既定は `process.env`）から、そのターンの `DeliverableTracker` を作る際に値を取得する。除外パスがチャットの作業フォルダー内にある場合、そのディレクトリーは再帰探索・成果物確認から除かれる。作業フォルダーそのものが除外リストにある場合、tracker はそのパスを内側の除外として登録しない（`app/host/server/agent/agent-bridge.mjs:160,184-189,533`; `app/host/server/agent/deliverables.mjs:97-123,145-150`）。

## 実行時の詳細

Python CLI の `_cloudflared_places()` は `cloudflared_info()` が候補を検索するたびに環境を参照して候補一覧を作り直す。`_cf_seen` がキャッシュするのは実行ファイルの版情報で、キーは `(path, mtime)`。ProgramData の値や候補一覧そのものはキャッシュされないため、プロセスの環境値が変われば次回の検索で候補パスも変わる（`terminal/strata_cli/launch/access.py:119,122-146,149-167,176-183`）。

Node 側は `connectorCandidates()` 呼び出しのたびに `env` オブジェクトから候補を生成する。既定では `process.env` だが、`createConnectorInstaller()` と検索関数は `env` を注入可能である。ProgramData 候補が見つかっても、それだけで選ばれるわけではなく、上位候補を順に検査して先に使用可能なものがあれば返す（`app/host/server/cloudflared-find.mjs:43-70,95-110`; `app/host/server/cloudflared-install.mjs:34-45`）。

MCP の `system_folders()` は `check_data_dir()` の呼び出しごとに Windows 環境から一覧を組み立てる。`data_dir` 入力に `%ProgramData%` が含まれる場合はパス検査前に環境値へ展開する。Agent の `trackerFolders()` は `DeliverableTracker` の生成時に評価され、ターン中に作成した tracker の除外パスはその tracker に渡された値で固定される（`terminal/tools/strata_mcp.py:566-572,2478-2499`; `app/host/server/agent/agent-bridge.mjs:184-189,533`; `app/host/server/agent/deliverables.mjs:97-123`）。参照箇所では ProgramData を子プロセス用環境へ明示的に設定しない。cloudflared の subprocess 呼び出しは `env` を個別指定していないため、Strata が継承環境を加工する処理はない（`terminal/strata_cli/launch/access.py:158-159,457-461`; `app/host/server/cloudflared-find.mjs:73-78`）。

## ログと測定値

測定値はない。cloudflared 探索で ProgramData 候補から使用可能なファイルが見つかれば、Node 側は候補の `source: 'system'` とパスを含む結果を返し、`describeConnector()` はパスと「a usual install location」を表示用文字列に含める。使えるものがなければ `found: null` になる。Python CLI 側では候補が無い場合、アクセス選択肢に `cloudflared is not installed` と表示され、Cloudflare アクセスの準備失敗時には cloudflared の未導入メッセージを返す。MCP の拒否時のエラー文は上記のとおり。Agent の除外処理自体はログを出さない（`app/host/server/cloudflared-find.mjs:34-40,108-124`; `terminal/strata_cli/launch/access.py:294-320,327-330`; `terminal/tools/strata_mcp.py:2498-2499`; `app/host/server/agent/agent-bridge.mjs:184-189`）。

## 根拠

- `terminal/strata_cli/launch/access.py:122-146` — Windows の Chocolatey 候補と既定値、候補の優先順。
- `terminal/strata_cli/launch/access.py:149-183` — 候補の実行確認、版情報 cache、探索結果。
- `app/host/server/cloudflared-find.mjs:43-70,95-124` — Node 側の環境参照、検索条件、探索結果と表示用理由。
- `app/host/server/cloudflared-install.mjs:34-50` — installer からの環境値受け渡しと検索。
- `terminal/tools/strata_mcp.py:566-572,2478-2501` — Windows のシステムフォルダー一覧、`data_dir` の環境変数展開と拒否条件。
- `app/host/server/agent/agent-bridge.mjs:160,184-189,533`、`app/host/server/agent/deliverables.mjs:90-123,145-150` — Agent の環境値取得と成果物追跡除外。
