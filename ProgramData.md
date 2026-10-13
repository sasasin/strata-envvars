# `ProgramData`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。対象は Strata 所有ソース。作業ツリーには未追跡の `bench/results/2026-10-12-community-ai-pro-r9700-qwen3-8-flash-next-iq2-xs/` があるが、調査対象のソースは変更されていない。

## 役割

Windows の `tools/strata_mcp.py` が `strata_install` の `data_dir` を検査するとき、システムフォルダー一覧の一つとして `ProgramData` の値を使う。そのフォルダー自身、またはその配下を新しいデータ保存先に指定すると、インストール計画を拒否する。モデルエンジンや `setup.py` の一般的な設定値としては読まれていない。

## 値と判定

| 状態 | 動作 |
|---|---|
| Windows 以外 | `ProgramData` は読まない。固定の Unix システムフォルダー一覧を使う。 |
| Windows で未設定、または空文字 | `os.environ.get()` が falsy 値を返し、システムフォルダー一覧に加えない。 |
| Windows で空でない値 | 値を `norm()` に渡して正規化したパスを一覧に加える。文字列の値域検査やディレクトリ存在確認は、この環境変数に対して行わない。 |

値の比較は数値 parse や `"1"` 等の文字列判定ではない。非空文字列をパスとして扱う。`norm()` は絶対パス化、`realpath`、OS の `normcase` を適用するため、相対値もプロセスの現在ディレクトリを基準に絶対化される。

## 有効になる条件

- MCP サーバーが Windows 上で動作していること（`WIN = os.name == "nt"`）。
- `strata_install` に `data_dir` が指定され、その値が `check_data_dir()` に渡されること。
- 指定先が、既存 Strata データフォルダー、Strata ルート内、またはルート隣の既定 `Strata-data` ではないこと。これらはシステムフォルダー検査より前に許可される。

この条件下で、正規化した指定先が `ProgramData` と一致するか、その配下にある場合、`ToolError("data_dir ... is inside a system folder")` で拒否する。他の Windows 環境変数（`SystemRoot`、`windir`、`ProgramFiles`、`ProgramFiles(x86)`、`ProgramW6432`）も同じ一覧に追加される。`ProgramData` が未設定なら、その名前のパスに対するこの個別の拒否条件は追加されない。

## 実行時の詳細

`ProgramData` は `system_folders()` の呼び出しごとに `os.environ.get("ProgramData")` で読み取られ、結果を関数内にキャッシュしない。`check_data_dir()` は `strata_install()` から指定された `data_dir` の検査時に呼ばれる。したがって、MCP プロセス内で環境値が検査前に変われば、その後の検査に反映される。なお、同じ検査関数は指定された `data_dir` に `os.path.expandvars(raw)` も適用するため、入力文字列に環境変数参照を含めた場合にも、その時点のプロセス環境がパス解決に関与する。

この変数は保存先を決めたり、子プロセスへ値を設定したりはしない。保存先の拒否判定にだけ影響する。拒否時のエラー文字列は `data_dir {raw!r} is inside a system folder`。ログ出力や警告を行うコードはこの分岐にはない。

## 文書との照合

`docs/MCP_SERVER.md` は、`data_dir` をシステムフォルダー内に置けないという一般的な制約を説明している。個々の Windows 環境変数名は列挙していない。実装の列挙に `ProgramData` が含まれること、および未設定・空文字時の扱いは `tools/strata_mcp.py` のコードで確認した。

## 根拠

- `tools/strata_mcp.py:44-45`: OS 判定 `WIN` と既定 Strata ルート。
- `tools/strata_mcp.py:363-382`: `norm()` と、Windows で `ProgramData` を含むシステムフォルダー一覧の構築。
- `tools/strata_mcp.py:1130-1154`: `data_dir` の正規化、既存配置の許可、システムフォルダー配下の拒否。
- `tools/strata_mcp.py:1248`: インストール処理からの `check_data_dir()` 呼び出し。
- `docs/MCP_SERVER.md:172-181`: `data_dir` の一般的なパス制約。
