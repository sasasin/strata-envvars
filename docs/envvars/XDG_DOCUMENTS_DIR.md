# `XDG_DOCUMENTS_DIR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Linux のデスクトップ host は、この変数を Documents ディレクトリとして使い、新規インストール時の既定モデル保存先を `<XDG_DOCUMENTS_DIR>/Strata/Models` にする。Terminal 側は `Documents/Strata` に既存モデルがあるかを探す候補の一つとして使う。どちらもモデル保存場所全体を単独で決める設定ではなく、既存設定やモデル状態によって選択されない場合がある。[`app/host/server/model-directory-default.mjs:14-24`](../../../../Niko1221/Strata/app/host/server/model-directory-default.mjs:14) [`terminal/strata_control/discovery.py:65-88`](../../../../Niko1221/Strata/terminal/strata_control/discovery.py:65)

## 値と判定

| 経路 | unset / 空文字 | 値の処理と例 |
|---|---|---|
| desktop host（Linux のみ） | unset または空文字なら `$XDG_CONFIG_HOME/user-dirs.dirs`（未設定なら `~/.config/user-dirs.dirs`）から `XDG_DOCUMENTS_DIR="…"` の行を探す。そこで値を得られない場合は `~/Documents`。 | 環境変数を優先。`${HOME}` と、`/` または文字列末尾に続く `$HOME` を home に置換する。置換後に `$` が残らず絶対パスなら採用。相対値、`$HOMEfoo` など未展開の `$` を含む値は不採用となり `~/Documents` に戻る。空白や大小文字を正規化せず、trim もしない。[^1] |
| Terminal の discovery（Windows 以外） | unset または空文字なら XDG 候補を追加しない。`~/Documents` は別候補として常に追加される。 | 非空値をそのまま `Path(xdg)` に渡す。`$HOME` 展開や絶対パス検査は行わない。例えば相対値も候補化される。重複する候補は除去される。[^2] |

[^1]: desktop host は `STRATA_DOCUMENTS_DIR` が非空なら先に採用し、Windows では Windows の known Documents folder を使うため、この XDG 判定に入らない。`STRATA_MODELS_DIR` が非空なら Documents 解決自体を通らず、その path をモデル先にする。[`app/host/server/model-directory-default.mjs:8-24`](../../../../Niko1221/Strata/app/host/server/model-directory-default.mjs:8)
[^2]: Terminal でも `STRATA_DOCUMENTS_DIR` が非空ならその候補が先に追加される。Windows 分岐では XDG 候補を使わず、`USERPROFILE/Documents` と設定済み OneDrive の Documents を候補にする。[`terminal/strata_control/discovery.py:67-83`](../../../../Niko1221/Strata/terminal/strata_control/discovery.py:67)

## 有効になる条件

- desktop host では `process.platform === 'linux'` のときだけ環境変数を読む。既定モデル先を計算する際に `STRATA_MODELS_DIR` が未設定で、`STRATA_DOCUMENTS_DIR` も空である必要がある。[`app/host/server/model-directory-default.mjs:8-24`](../../../../Niko1221/Strata/app/host/server/model-directory-default.mjs:8)
- その値がモデル保存先に反映されるのは、保存済み `state.modelsDir` がなく、`STRATA_MODELS_DIR` による固定もなく、`STRATA_HOME/models` に保持すべき既存モデルがない場合。保存設定または既存モデルがあればそちらが優先される。[`app/host/server/store.mjs:62-85`](../../../../Niko1221/Strata/app/host/server/store.mjs:62)
- Linux host が選んだ Documents の下に作成・アクセスできなければ `STRATA_HOME/models` に fallback し、通知を警告する。[`app/host/server/store.mjs:77-89`](../../../../Niko1221/Strata/app/host/server/store.mjs:77)
- Terminal ではデスクトップアプリ内モード（`STRATA_SETTINGS_FILE` が真）でなければ Documents 候補を調べる。候補 `Documents/Strata` に `Models`、`models` または `packs` の中身があるときだけデータディレクトリとして選ぶ。設定ファイル由来の候補が優先され、どれも該当しなければ呼び出し元の既定値を使う。[`terminal/strata_control/discovery.py:60-62`](../../../../Niko1221/Strata/terminal/strata_control/discovery.py:60) [`terminal/strata_control/discovery.py:263-296`](../../../../Niko1221/Strata/terminal/strata_control/discovery.py:263)

## 実行時の詳細

desktop host は `model-directory-default.mjs` の関数呼び出し時に `process.env` を評価し、`store.mjs` のモジュール初期化時に `DEFAULT_MODELS_DIRECTORY` とモデル先を決める。その結果は `MODELS_DIR` として起動中保持されるため、プロセス実行中の環境変数変更を再読込するコードではない。[`app/host/server/store.mjs:62-89`](../../../../Niko1221/Strata/app/host/server/store.mjs:62)

Terminal の `documents_dirs()` は `data_dir_choices()` / `data_dir()` の呼び出しごとに渡された `environ`（省略時は `os.environ`）を参照する。選択済みの data directory は後段の `Catalog.data_dir()` 経由で CLI のモデル管理などに使われる。[`terminal/strata_control/discovery.py:65-88`](../../../../Niko1221/Strata/terminal/strata_control/discovery.py:65) [`terminal/strata_control/discovery.py:263-290`](../../../../Niko1221/Strata/terminal/strata_control/discovery.py:263) [`terminal/strata_cli/launch/catalog.py:753-760`](../../../../Niko1221/Strata/terminal/strata_cli/launch/catalog.py:753)

## ログと測定値

desktop host は起動時に選択済みモデル先を `models dir   ·  <path>` と出力する。既定 Documents 先を作成またはアクセスできない場合は stderr に `[strata] Strata could not use <preferred> for models (<error>), so models go to <legacy>. You can pick another folder in Settings.` と警告する。XDG 値が無効で `~/Documents` に戻っただけの場合、専用の警告はない。[`app/host/server/index.mjs:310-316`](../../../../Niko1221/Strata/app/host/server/index.mjs:310) [`app/host/server/store.mjs:77-89`](../../../../Niko1221/Strata/app/host/server/store.mjs:77)

## 根拠

- `app/host/server/model-directory-default.mjs:8-25` — desktop host の優先順位、Linux XDG 判定、設定ファイル fallback、HOME 展開と絶対パス判定。
- `app/host/server/store.mjs:62-89` — 読み取り時期、保存済み値・既存モデルとの優先関係、作成失敗時の fallback と警告。
- `app/host/server/index.mjs:310-316` — 起動時の選択済みモデルディレクトリ出力。
- `terminal/strata_control/discovery.py:65-88,263-296` — Terminal 側の候補生成と実際の選択条件。
- `terminal/strata_cli/launch/catalog.py:753-760` — Terminal の catalog から discovery を呼ぶ経路。
