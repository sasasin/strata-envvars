# `ProgramData`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。対象は Strata 所有ソース。外部ライブラリ・OS 自身による同名環境変数の利用は対象外。

## 役割

Strata 同梱の MCP サーバー `tools/strata_mcp.py` が、Windows で `strata_install` の `data_dir` に指定された場所がシステムフォルダー内かを検査するとき、`ProgramData` の値を保護対象フォルダーの一つとして使います。エンジンや通常の `setup.py` が `ProgramData` を設定として読む実装は、このリポジトリ内で確認できませんでした。

## 値と判定

| 状態 | `system_folders()` での扱い |
|---|---|
| `os.name != "nt"` | この関数は `ProgramData` を読みません。Linux 側では固定のシステムディレクトリー一覧を使います。 |
| 未設定 (`os.environ.get()` が `None`) | 候補から除外します。 |
| 空文字 | `if p` のフィルターで候補から除外します。 |
| 空でない文字列 | 値を数値・真偽値として parse せず、パスとして正規化して保護対象に加えます。 |

正規化は `norm()` が行い、`abspath`、`realpath`、Windows の `normcase` を適用します。値の前後空白除去、存在確認、環境変数値の妥当性検査はありません。したがって `ProgramData=0` も「無効」の意味にはならず、文字列 `0` をパスとして扱います。

## 有効になる条件

- MCP サーバーが Windows で動作していること（`WIN = os.name == "nt"`）。
- `strata_install` に `data_dir` が渡されること。省略時は `check_data_dir()` を呼ばず、Strata の既定データディレクトリーを使います。
- 検査対象が現在の Strata データディレクトリー、Strata 本体の配下、または Strata 本体と同階層の `Strata-data` でないこと。これらは既存の許可先として先に通されます。

その後、保護対象フォルダーと同じ場所またはその配下にある新しい保存先は `ToolError("data_dir ... is inside a system folder")` で拒否されます。`ProgramData` が未設定または空でも、`SystemRoot`、`windir`、`ProgramFiles`、`ProgramFiles(x86)`、`ProgramW6432` の各設定値は独立して検査されます。

## 実行時の詳細

`system_folders()` は呼び出しのたびに環境を読みます。`ProgramData` の値を静的キャッシュするコードはありません。MCP サーバーが処理する `strata_install` の `data_dir` は `install_plan()` から `check_data_dir()` に渡され、正規化した保存先と `system_folders()` の各パスを比較します。Windows の `data_dir` は `os.path.expandvars()` による一般的な環境変数展開も受けるため、たとえば `%ProgramData%` を含む入力は、その時点の環境値に従って展開されます。

拒否時のエラー文言は `data_dir {raw!r} is inside a system folder` です。MCP サーバーの説明書も、外部の新しい `data_dir` は `Strata...` という名前でシステムフォルダー外に置く必要があると記載していますが、`ProgramData` の列挙や値ごとの判定規則までは説明していません（`docs/MCP_SERVER.md` の Paths 節）。

## 根拠

- `tools/strata_mcp.py:44`: `WIN` を `os.name == "nt"` で決定。
- `tools/strata_mcp.py:389-400`: パス正規化、Windows での `ProgramData` を含む保護対象一覧、空値の除外。
- `tools/strata_mcp.py:1153-1176`: `data_dir` の展開・正規化・許可先の例外・システムフォルダー配下の拒否。
- `tools/strata_mcp.py:1225-1272`: `install_plan()` から `check_data_dir()` への呼び出し。
- `docs/MCP_SERVER.md:175-179`: `data_dir` のシステムフォルダー外という説明。
