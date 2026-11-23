# `STRATA_HY4_SHOW`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata Terminal の MCP ツール `strata_models` が返すモデルファミリー一覧に Hy4-Flash を含めるための表示ゲートです。`Strata.hy4_visible()` が真になると `HY4_FAMILIES` の項目を一覧用の family table に追加し、モデル一覧の `families` に現れます（`terminal/tools/strata_mcp.py:638-640, 646-655, 2417-2428`）。これは engine の実行・計算を有効化する設定ではありません。この環境変数への参照は同ファイルのこの読み取り箇所のみで、engine 側の挙動を変える読み取りは確認できません。

## 値と判定

`os.environ.get("STRATA_HY4_SHOW") == "1"` で文字列全体を比較します。数値変換や trim、大文字小文字変換はありません。明示的な空文字は未設定と同様にこの条件を満たさず、`1` の前後に空白がある値、`true`、`True`、`0`、`0anything` も一致しません（`terminal/tools/strata_mcp.py:651`）。

| 条件 | unset | 有効になる値（例） | この条件では有効にならない値（例） |
|---|---|---|---|
| MCP ツールの Hy4 表示判定 | 後述のダウンロードソース・ローカルファイルを確認 | `1` | 空文字、`0`、`true`、`True`、` 1`、`1 `、`0anything` |

`1` 以外でも、Hy4 のダウンロードソースが設定されているか、データフォルダー内に Hy4 のローカルファイルがあれば表示されます。したがって表の「有効」はこの環境変数自身の判定を指し、Hy4 表示の唯一の条件ではありません（`terminal/tools/strata_mcp.py:651-653`）。

## 有効になる条件

- 対象は `terminal/tools/strata_mcp.py` の Strata Terminal MCP サーバーです。`strata_models` の呼び出しが `Strata.model_table()` / `Strata.tables()` を通じて Hy4 の表示判定を行います（`terminal/tools/strata_mcp.py:1522-1525, 2417-2428`）。
- `strata_control.hy4_family` の import が成功する必要があります。例外が発生すると `hy4_visible()` は `False` を返し、環境変数が `1` でも表示されません（`terminal/tools/strata_mcp.py:649-655`）。
- setup モジュールが利用可能な場合、その `HY4_FAMILIES` に登録された項目が表示候補になります。setup モジュールを読み込めない場合、`tables()` は組み込みの fallback table を返し、`own_families()` を経由しないため、この経路では環境変数による Hy4 family の追加はありません（`terminal/tools/strata_mcp.py:623-627, 638-640`）。
- `STRATA_HY4_SHOW` が未設定または `1` 以外でも、`hy4_family.sources()` が真を返すか、`hy4_family.local_files(...)` がファイルを返せば表示されます（`terminal/tools/strata_mcp.py:651-653`）。この変数の `1` はこれらの確認を短絡し、表示を許可します。
- OS、GPU backend、CLI 引数、モデル実行状態による追加条件は、この環境変数の判定箇所にはありません。サーバーモードの engine 動作を切り替える用途でもありません（読み取り箇所: `terminal/tools/strata_mcp.py:651`）。

## 実行時の詳細

値は `hy4_visible()` が呼ばれるたびに `os.environ.get` で読み直され、関数内キャッシュはありません。判定は `own_families()` から `tables()` を作るときやモデル表を構築するときに呼ばれます。従って MCP サーバープロセス内で `os.environ` が変更された場合、次回以降の呼び出しでは新しい値が判定に使われます（`terminal/tools/strata_mcp.py:623-640, 646-655, 1522-1525, 2417-2428`）。起動時に一度だけ固定する処理、CLI 引数による上書き、子プロセスへの転送はこの環境変数について確認できません。

`strata_models` は環境情報・推薦結果とともに `families` を返します。Hy4 が表示条件を満たす場合、family の説明情報（title/about/tag/license 等）に `own_path` と `hy4` の印を付け、対応するサイズをモデル表に加えます（`terminal/tools/strata_mcp.py:638-640, 2417-2428`）。

## ログと測定値

この変数の値や不一致を報告するログはありません。`hy4_visible()` 内で import や確認処理が例外になった場合も、その例外を捕捉して `False` を返すだけです（`terminal/tools/strata_mcp.py:649-655`）。測定値は該当しません。

## 根拠

- `terminal/tools/strata_mcp.py:623-627` — setup のモデル・family table と fallback table の選択。
- `terminal/tools/strata_mcp.py:629-655` — Hy4 family の追加と環境変数、ソース、ローカルファイルによる表示判定。
- `terminal/tools/strata_mcp.py:1522-1525` — 通常モデル表からの table 利用。
- `terminal/tools/strata_mcp.py:2417-2428` — MCP `strata_models` の結果にモデルファミリー一覧を含める処理。
