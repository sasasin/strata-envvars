# `XDG_CONFIG_HOME`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Linux など Windows 以外の環境で、Strata のユーザー設定ファイル `strata/settings.json` を置く親ディレクトリを選びます。Strata の `setup.py` と `tools/strata_mcp.py` がそれぞれ同じ規則でパスを作ります。GPU エンジンの環境変数ではありません。

この設定ファイルには、セットアップで最後に選んだデータフォルダーやインストール先、PC とモデルごとのキャリブレーション結果が保存されます。MCP ツールはそこから `data_dir` を読み、モデルデータの場所や空き容量の確認、ファイルアクセス許可範囲の判定に使います。

## 値と判定

| 条件 | 設定ファイルのパス |
|---|---|
| Windows | `%APPDATA%\Strata\settings.json`。`XDG_CONFIG_HOME` は参照しない |
| Windows 以外で未設定、または空文字 | `Path.home()/.config/strata/settings.json` |
| Windows 以外で空でない値 | `Path(XDG_CONFIG_HOME)/strata/settings.json` |

Python の `os.environ.get("XDG_CONFIG_HOME") or ...` による選択で、空文字は未設定と同じ fallback になります。値の trim、展開、正規化はこの箇所ではしません。したがって空白だけの値も採用され、空白を含むパスとして扱われます。値は数値や真偽値として parse されません。相対パスも拒否されず、`Path` の相対パスとして現在の作業ディレクトリ基準で解釈されます。

根拠: `setup.py:3695-3698`、`tools/strata_mcp.py:435-438`。

## 有効になる条件

- Windows 以外でのみ読み取られます。Windows では `WIN` 分岐が `APPDATA` を使います。
- 値を読むのは Strata セットアップおよび同梱 MCP サーバーです。この変数をエンジン側で読む実装はありません。
- `setup.py` では `--data-dir` が明示されていればそちらが保存先になり、既定の保存先選択は `settings.json` 内の `data_dir`、それもなければ `ROOT.parent / "Strata-data"` です。環境変数はこの設定ファイルの場所を変えるため、保存済み `data_dir` の参照先も間接的に変わります。

## 実行時の詳細

`setup.py` の `settings_path()` は呼び出し時に環境変数を読み、結果をキャッシュしません。`load_settings()` はそのパスの UTF-8 JSON を読み、ファイルがない、読めない、または JSON が不正なら空辞書を返します。`save_settings()` は親ディレクトリを作り、整形した JSON を書きます。書き込みに失敗すると `could not save <path> (<error>)` の警告を出します。保存内容には、`data_folder()` が設定する `data_dir` と直近最大20件の `installs`、セットアップのキャリブレーションが記録する `calibration` などがあります（`setup.py:3701-3713,3805-3815,3854-3855,4146-4172`）。

MCP サーバーの `settings_path()` も呼び出しごとに環境変数を参照します。`data_dir()` は同じパスの JSON から `data_dir` を読み、読み取り失敗時や値がない場合は MCP サーバーの `root.parent / "Strata-data"` を使います。これがモデル一覧と空き容量確認に使われ、ログ表示などの許可パス判定では Strata フォルダーとデータフォルダーを許可ルートにします。したがって MCP サーバーとセットアップで `XDG_CONFIG_HOME` が異なると、互いに別の `settings.json` を読み書きし、MCP がセットアップの保存したデータ場所を見つけないことがあります（`tools/strata_mcp.py:435-449,544-565,568-575,1460-1465`）。

## 文書との照合

`docs/DETAILS.md` は Linux の既定位置を `~/.config/strata/settings.json` と説明し、データフォルダーを設定ファイルに記憶すると記載しています（`docs/DETAILS.md:423-427,1808`）。これは `XDG_CONFIG_HOME` が未設定または空の場合のソース実装と一致します。文書では環境変数による位置変更には触れていません。

## 根拠

- `setup.py:3695-3713` — 設定パス、JSON の読み込みと保存。
- `setup.py:3805-3815,3854-3855` — 設定内の `data_dir` を利用し、保存する処理。
- `setup.py:4146-4172,4182-4194` — キャリブレーション結果の保存と再利用。
- `tools/strata_mcp.py:435-449,544-565,568-575,1460-1465` — 同じパス規則、MCP での `data_dir` 利用と許可ルート判定。
- `docs/DETAILS.md:423-427,1808` — 設定ファイルの既定場所とデータフォルダー記録の説明。
