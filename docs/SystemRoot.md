# `SystemRoot`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

Windows 版の同梱 MCP サーバー `tools/strata_mcp.py` が、`strata_install` に渡された新しい `data_dir` を検査する際、Windows のシステムフォルダーとして扱うパスの一つを指定します。指定先が `SystemRoot` と一致するか、その配下にある場合はインストール先として拒否します。推論エンジンや通常の `setup.py` の設定を変える環境変数ではありません。

## 値と判定

| 状態 | MCP サーバーの処理 |
|---|---|
| 未設定または空文字 | `os.environ.get("SystemRoot")` は偽値となり、`system_folders()` の一覧にこのパスを加えません。別名の `windir` などは個別に確認されます。 |
| 空でない値 | 文字列をそのままパスとして `norm()` に渡し、絶対パス化・実パス化・Windows での大文字小文字正規化を行ったうえで禁止対象にします。前後空白の除去や独自の値形式検証はありません。 |

`check_data_dir()` は検査前に入力された `data_dir` に `os.path.expandvars()` を適用します。そのため、入力パス内に `SystemRoot` を参照する環境変数表記があれば、Python の実行環境の展開規則に従って展開された値が後続のパス検査に使われます。`SystemRoot` 自体はこの処理のために別途読み直したり加工したりしません。

## 有効になる条件

- `tools/strata_mcp.py` が Windows と判定する場合（`os.name == "nt"`）だけ、環境変数群からシステムフォルダー一覧を作ります。Linux では `SystemRoot` を参照せず、`/bin`、`/etc`、`/usr` などの固定パス一覧を使います。
- 検査は MCP の `strata_install` に `data_dir` が明示された場合に行われます。`data_dir` を省略した場合は設定済みの保存先をそのまま使います。
- `check_data_dir()` では、現在の保存先、Strata フォルダー内、および Strata フォルダーの隣にある既定の `Strata-data` は先に許可されます。これらの経路ではシステムフォルダーとの照合に進みません。
- 上記の許可対象以外では、指定先が `SystemRoot` などのシステムフォルダーと同一、またはその配下にあると `ToolError` で拒否されます。新しい保存先には別途、絶対パス・既存の親フォルダー・`Strata` で始まるフォルダー名などの条件もあります。

## 実行時の詳細

`SystemRoot` は `system_folders()` が呼ばれるたびに `os.environ.get()` で読み取られ、静的キャッシュされません。同じプロセス内で `os.environ` が変更されれば、後の検査は変更後の値を参照します。値の取得、保存、子プロセスへの個別の上書きはこの処理にはありません。

禁止対象に一致した場合、ツール呼び出しは `data_dir {raw!r} is inside a system folder` というエラーになります。`SystemRoot` が未設定でも、一覧中の `windir`、`ProgramFiles`、`ProgramFiles(x86)`、`ProgramData`、`ProgramW6432` が設定されていればそれらは別に検査されます。

## 根拠

- `tools/strata_mcp.py:44-45`: Windows 判定と MCP サーバーの既定 Strata ルート。
- `tools/strata_mcp.py:371-382`: パス正規化、および Windows で `SystemRoot` を含む環境変数群からシステムフォルダーを作る処理。空値は除外されます。
- `tools/strata_mcp.py:1130-1154`: `data_dir` の展開・形式検査、許可済み保存先の扱い、システムフォルダー配下を拒否する条件とエラー。
- `tools/strata_mcp.py:1248`: 明示された `data_dir` に対して `check_data_dir()` を呼ぶ箇所。
- `docs/MCP_SERVER.md:170-182`: MCP サーバーのパス制約の概要。システムフォルダーの具体的な一覧は文書に列挙されておらず、上記の列挙は現行ソースに基づきます。
