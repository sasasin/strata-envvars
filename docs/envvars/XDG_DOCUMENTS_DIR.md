# `XDG_DOCUMENTS_DIR`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

この変数は、Strata Terminal の既存データフォルダー探索と、Linux デスクトップ host の新規モデルライブラリー既定位置の候補に使われる。Terminal 側では `STRATA_DOCUMENTS_DIR` の次に Documents フォルダー候補へ追加し、その中の `Strata/` に既存モデルデータがある場合に選ぶ。host 側では新規モデルフォルダーを `<Documents>/Strata/Models` として組み立てる。どちらも変数だけで既存の保存先を移動しない。`strata_control.discovery.documents_dirs` と host の `defaultModelDirectory` が読み取り元である（`strata_control/discovery.py:65-88,263-295`; `apps/host/server/model-directory-default.mjs:8-19`）。

## 値と判定

| 経路 | unset / 空文字 | 有効になる値（例） | 無効・別扱いの値（例） |
|---|---|---|---|
| Terminal (`strata_control.discovery`) | `environ.get()` が偽になるため候補に加えず、`~/Documents` を候補にする | 非空文字列をそのまま `Path` にする。例: `/mnt/archive/Documents` | 文字列としての検証・絶対パス確認・`$HOME` 展開はしない。`relative/docs` も候補になる。Windows 判定時はこの変数を読まず、`USERPROFILE/Documents` と OneDrive 候補を使う。 |
| Linux デスクトップ host (`defaultModelDirectory`) | 未設定または空文字なら `user-dirs.dirs` を読む | 絶対 POSIX パス。`$HOME` または `${HOME}` は home に置換後に使える。例: `/mnt/archive/Documents`, `${HOME}/Dokumente` | 相対パス、`~`、置換後にも `$` を含む値は採用せず `home/Documents` に fallback。例: `relative/docs`, `~/Docs`, `$(command)`。 |

Terminal 側は環境マップの値の truthiness だけを判定し、パースしない。空文字は未設定と同じ扱いで、非空ならそのまま候補へ追加する。候補が実際に選ばれるには、その候補の `Strata/` に `Models`、`models` または `packs` のいずれかの非空ディレクトリーが必要である（`strata_control/discovery.py:70-88,288-297`）。

host 側は Linux でのみ環境変数を直接見る。`STRATA_MODELS_DIR` が truthy ならそれを解決して即時返却し、この変数を参照しない。そうでなければ truthy な `STRATA_DOCUMENTS_DIR` を先に使い、未設定または空なら `XDG_DOCUMENTS_DIR` を調べる。XDG 値が空なら `XDG_CONFIG_HOME`、または `~/.config` の `user-dirs.dirs` から、`XDG_DOCUMENTS_DIR="..."` に一致する最初の非空・二重引用符内の値を読む。ファイル読取例外は無視する。直接値が相対パスなどで無効でも、設定ファイルを再試行せず `home/Documents` へ fallback する（`apps/host/server/model-directory-default.mjs:9-19`）。

設定ファイル由来・環境変数由来のどちらも、host は `${HOME}` と、末尾または `/` の直前にある `$HOME` を置換する。その後に `$` が残らず、パスが絶対パスである場合だけ採用する。文字列全体のシェル評価や `~` 展開はしない。最終的に選んだ Documents パスへ `Strata/Models` を連結する（`apps/host/server/model-directory-default.mjs:14-19`）。

## 有効になる条件

- Terminal の `documents_dirs` では非 Windows 経路に限り、`XDG_DOCUMENTS_DIR` の候補を追加する。Windows 経路はこの変数を参照しない（`strata_control/discovery.py:37-38,73-83`）。
- Terminal はアプリ自身のプロセス（`STRATA_SETTINGS_FILE` が truthy）では Documents 候補を追加しない。コマンドライン側でも、自分の保存設定とアプリ側データフォルダーが Documents 候補より先に調べられる。CLI の `--data-dir` で指定された場所は launch state に入り、実行時に discovery の既定候補より先に使われる（`strata_control/discovery.py:60-62,263-290`; `strata_cli/launch/cmd.py:81-90`; `strata_cli/launch/runner.py:953-959`）。
- Linux host が既定パスを計算するときは `STRATA_MODELS_DIR` が最優先で、次に非空 `STRATA_DOCUMENTS_DIR`、その次に `XDG_DOCUMENTS_DIR` が使われる。ただし、host の保存済み `state.modelsDir` は計算した既定パスより優先する。保存済み値がなければ、`STRATA_MODELS_DIR` による固定指定がない場合に限り `STRATA_HOME/models` 以下の既存 GGUF ライブラリーを維持する（`apps/host/server/model-directory-default.mjs:10-19`; `apps/host/server/store.mjs:60-83`）。
- Terminal の Documents 候補は、`Strata/Models`・`Strata/models`・`Strata/packs` のどれかが存在し、かつ中に項目がある場合だけ採用される。候補がなければ `Catalog` の default が使われる（`strata_control/discovery.py:278-297`; `strata_cli/launch/catalog.py:537-544`）。
- host 側で既定の Documents フォルダーを作成できない、または読み書き実行権を確認できない場合、`STRATA_HOME/models` に fallback する。host が別に `STRATA_MODELS_DIR`・保存済みフォルダー・既存 GGUF を採用した場合、この XDG 値は選択結果に現れない（`apps/host/server/store.mjs:67-86`）。

## 実行時の詳細

Terminal 側は `documents_dirs()` が呼ばれるたびに渡された環境マップ（省略時は現在の `os.environ`）を読み、結果を cache しない。`data_dir()` は設定の同期後に候補を順に調べ、Documents 候補については `Strata/` 以下を走査してモデルデータの有無を判定する。既存モデルの run config に実データ位置が書かれている場合は、`Catalog.data_dir_for()` がその位置を優先する（`strata_control/discovery.py:65-88,242-297`; `strata_cli/launch/catalog.py:537-558`）。

デスクトップ host 側は `store.mjs` のモジュール初期化中に `defaultModelDirectory()` を一度呼び、`DEFAULT_MODELS_DIRECTORY` に保存する。したがって起動後の環境変更は既定パスに反映されない。Linux の XDG 値が未設定・空のときは同じ初期化中に `user-dirs.dirs` を同期読み込みする。既定パス作成時に失敗した場合は host が notice を設定し、起動自体は `STRATA_HOME/models` を使って続行する（`apps/host/server/store.mjs:60-87`; `apps/host/server/model-directory-default.mjs:8-19`）。

`strata_control/discovery.py` は XDG 設定ファイルを読み込まず、環境変数値だけを候補として使う。一方、Linux host は直接値が空の場合に限り `XDG_CONFIG_HOME/user-dirs.dirs`（未設定時は `~/.config/user-dirs.dirs`）を読む。このため、環境変数が空でも XDG 設定ファイルの Documents 設定が有効になるのは host 経路であり、Terminal 経路では `~/Documents` が候補になる（`strata_control/discovery.py:65-88`; `apps/host/server/model-directory-default.mjs:13-19`）。

## ログと測定値

Terminal の Documents 候補探索自体には、この変数に関するログ出力・終了・失敗処理はない。ディレクトリー列挙時の `OSError` は `_holds_models()` が `False` として扱い、後続候補または既定値へ進む（`strata_control/discovery.py:288-297`）。

host が既定 Documents フォルダーを作成・検査できなければ、stderr に `[strata] ` と `Strata could not use <preferred> for models (<error code または message>), so models go to <legacy>. You can pick another folder in Settings.` を出す。作成失敗以外に、XDG 値の無効さだけを示す警告はない。測定値は該当なし（`apps/host/server/store.mjs:75-86`）。

## 根拠

- `strata_control/discovery.py:65-88` — Documents 候補の生成、OS 分岐、`STRATA_DOCUMENTS_DIR` と XDG の順序。
- `strata_control/discovery.py:263-297` — Terminal の設定候補との優先、アプリモードでの除外、Documents データの存在判定。
- `strata_cli/launch/catalog.py:537-558` — CLI catalog から discovery を呼び、モデル単位の保存先を優先する経路。
- `strata_cli/launch/cmd.py:81-90`; `strata_cli/launch/runner.py:953-959` — `--data-dir` を launch state の明示指定として使う経路。
- `apps/host/server/model-directory-default.mjs:8-19` — host の環境値・設定ファイル・絶対パス判定・fallback。
- `apps/host/server/store.mjs:60-87` — 初期化時の既定値保持、保存済み／既存ライブラリーの優先と失敗 notice。
- `docs/TERMINAL_LAUNCH.md:195`; `docs/INSTALL.md:140` — データフォルダー探索とデスクトップ初期保存先の概要。詳細な値判定は上記実装に基づく。
