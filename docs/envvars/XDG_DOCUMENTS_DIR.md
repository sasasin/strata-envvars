# `XDG_DOCUMENTS_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata が Documents フォルダーの場所を知るために読みます。端末側 Python では既存の `Documents/Strata` データフォルダーを探索する候補に加えます。デスクトップホストでは、新しいモデルライブラリの既定場所を `Documents/Strata/Models` として組み立てます。GPU engine や推論処理には関与しません。

候補一覧 `docs/envvars/000_envvers.md:1716` に掲載されています。Strata 所有コードでの読み取りは `strata_control/discovery.py:79` と `apps/host/server/model-directory-default.mjs:14` の二系統です。設定文書 `apps/host/docs/native-engine-handover.md:83` も Linux ホストがこの変数を使うと説明しています。

## 値と判定

| 経路 | unset・空文字 | 設定値 | 不正値・読めない設定 |
|---|---|---|---|
| 端末側 Python | 非 Windows では空文字を含む falsy 値を候補に追加せず、`home/Documents` を候補にする | 非空の値をそのまま `Path` にし、`Documents/Strata` 候補として追加する。環境変数中の `$HOME` 展開、絶対パス検査、存在確認はこの段階ではしない | 候補を実際に採用する際、`Documents/Strata` 内に非空の `Models` / `models` / `packs` サブフォルダーがなければ採用しない。I/O エラーも採用不可として扱う |
| デスクトップホスト（Linux） | 空文字なら `XDG_CONFIG_HOME` または `~/.config` の `user-dirs.dirs` を読む | `${HOME}`、または `/` か文字列末尾の直前にある `$HOME` を `home` に置換する。残った `$` がなく、置換後が絶対パスなら Documents として使う | `user-dirs.dirs` の読み取り失敗は握りつぶす。相対パス、未展開の `$` を含む値などは `home/Documents` にフォールバックする。環境変数に非空の不正値がある場合、設定ファイルを追加で読むことはない |

Python 側は `environ.get("XDG_DOCUMENTS_DIR")` の truthiness だけで値の有無を判定します。空白だけの値や相対パスも非空なので候補になります。重複候補は `Path` の等価比較で除きます。Windows 判定時はこの変数を読まず、ユーザープロファイルの `Documents` と OneDrive 候補を使います（`strata_control/discovery.py:64-87`）。

ホスト側の設定ファイル読取は、行頭の空白の後に `XDG_DOCUMENTS_DIR="..."` がある行を正規表現で探します。値の引用符は二重引用符だけを認識し、shell の変数展開やコマンド実行はしません。置換対象は `${HOME}` と `$HOME` の限定形だけです。Linux 以外では `XDG_DOCUMENTS_DIR` と `user-dirs.dirs` を参照せず、Documents の既定は `home/Documents` です（`apps/host/server/model-directory-default.mjs:13-19`）。

## 有効になる条件

- 端末側の `discovery.documents_dirs()` は非 Windows のときに環境値を候補へ加えます。呼び出し側で `windows` を明示した場合はその値、未指定なら OS 判定を使います（`strata_control/discovery.py:36-38,64-87`）。
- 端末側は `STRATA_SETTINGS_FILE` が設定されているアプリ内モードでは Documents 候補を追加しません（`strata_control/discovery.py:59-61,262-274`）。
- デスクトップホストは Linux のときだけ環境値を処理します。`STRATA_DOCUMENTS_DIR` が非空なら Documents の場所として先に使われ、XDG 値を読みに行きません。`STRATA_MODELS_DIR` が非空なら `STRATA_DOCUMENTS_DIR` を含む既定値全体より優先し、そのパスをモデルディレクトリーにします（`apps/host/server/model-directory-default.mjs:8-19`）。
- ホストでは保存済みの `state.modelsDir` が最優先です。次に、`STRATA_MODELS_DIR` による固定指定がない場合は `STRATA_HOME/models` に既存モデルファイルがあれば維持します。これらに該当しない新規ライブラリに XDG 由来の既定場所を使います（`apps/host/server/store.mjs:67-84`）。
- 端末側は設定ファイルに記録されたデータフォルダーを Documents 候補より優先します。`settings` の値はそのまま採用し、`app` の値はフォルダーが存在するとき採用します。Documents 候補は既存モデルデータが見つかったときだけ採用し、それ以外は呼び出し元の既定フォルダーへ進みます（`strata_control/discovery.py:262-295`）。呼び出し元が `s.data_dir` やモデル固有の既存データを明示している場合も catalog の既定値より先に使います（例: `strata_cli/launch/runner.py:919-924,1104,1272-1273`）。

## 実行時の詳細

端末側では `documents_dirs()` が呼ばれるたびに渡された `environ`（省略時は現在の `os.environ`）を参照します。値を static 変数などに保存するキャッシュはありません。`Catalog.data_dir_choice()` が `discovery.data_dir()` に委譲し、端末 CLI のデータ場所を決めます（`strata_cli/launch/catalog.py:546-553`）。選ばれた Documents パスは `Documents/Strata` です。そこに `Models`、`models` または `packs` の中身がなければ採用されず、エラー表示はなく呼び出し元の既定パスが返ります（`strata_control/discovery.py:262-295`）。

デスクトップホストでは `store.mjs` のモジュール初期化中に `defaultModelDirectory()` を呼び、その結果を `DEFAULT_MODELS_DIRECTORY` に保存します。従って通常のホストプロセスでは起動時の値が使われ、起動後の環境変更は再評価されません。既定場所の作成またはアクセス確認に失敗した場合は `STRATA_HOME/models` を選び、`MODELS_DIR_NOTICE` を `[strata] ...` 形式で `console.warn` に出します。Documents のパスが無効な場合のパス選択自体は警告せず `home/Documents/Strata/Models` にフォールバックします（`apps/host/server/store.mjs:60-87`; `apps/host/server/model-directory-default.mjs:8-19`）。

## 根拠

- `strata_control/discovery.py:64-87` — `XDG_DOCUMENTS_DIR` の直接読取、Windows 分岐、Documents 候補の構築。
- `strata_control/discovery.py:262-295` — アプリ内モード、保存済みパスとの優先順位、Documents 候補の採用条件。
- `strata_cli/launch/catalog.py:546-553` — 端末側カタログからデータフォルダー探索への接続。
- `apps/host/server/model-directory-default.mjs:8-19` — Linux での XDG 値・設定ファイルの処理、他の環境変数との優先順位、既定パス。
- `apps/host/server/store.mjs:60-87` — ホスト起動時の評価と、保存済み・既存ライブラリ・既定場所の選択、およびフォールバック警告。
- `apps/host/docs/native-engine-handover.md:83` — Linux の既定モデル置き場で XDG Documents を利用するという説明。
