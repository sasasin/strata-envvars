# `STRATA_DOCUMENTS_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。外部ライブラリの環境変数動作は対象外です。

## 役割

Strata が使う Documents フォルダーを指定します。Strata 内で二つの用途があります。

- デスクトップアプリの Node ホストでは、新しいモデルライブラリの既定先を `<Documents>/Strata/Models` に決めます。
- Terminal の Python 側では、既存データを探すときに `<Documents>/Strata` を候補に加えます。ただし、その下にモデル等のデータが見つかった場合だけ採用します。

同じ値でも、Node ホストは単一の既定場所として扱い、Python は他の Documents 候補と合わせた探索候補として扱います。読み取り箇所は `apps/host/server/model-directory-default.mjs:8-19` と `strata_control/discovery.py:64-87` です。

## 値と判定

| 読み取り箇所 | 未設定・空文字 | 空でない値 | 不正・相対値 |
|---|---|---|---|
| Node ホスト | Windows は Windows の既知 Documents フォルダーを取得し、失敗時はホームの `Documents`。Linux は `XDG_DOCUMENTS_DIR`、なければ `user-dirs.dirs` を試し、最終的にホームの `Documents`。その他の OS（macOS を含む）はホームの `Documents`。 | `STRATA_MODELS_DIR` が truthy ならそちらが先に使われる。そうでなければこの値を Documents として使い、`Strata/Models` を足す。 | 絶対パスでなければ OS 別 Documents 値を使わず、ホームの `Documents` に戻る。文字列の trim、`~` 展開、環境変数展開はしない。 |
| Python の discovery | この候補を追加しない。OS 別の他の候補は引き続き追加する。 | `Path(value)` を Documents 候補リストの先頭に追加する。 | trim、絶対パス確認、`~` や `$HOME` 展開はしない。相対値も相対 `Path` 候補として保持する。 |

Node 側で「空」は falsy 判定です。空白だけの値は空扱いではなく非空ですが、相対パスなので後でホームの `Documents` にフォールバックします。絶対パスでも、存在確認は既定値を作る関数内では行いません。後段で作成・アクセス確認します。

Linux の Node 側では `STRATA_DOCUMENTS_DIR` が空の場合に限り、`XDG_DOCUMENTS_DIR`、次に `$XDG_CONFIG_HOME` または `~/.config` 内の `user-dirs.dirs` にある `XDG_DOCUMENTS_DIR="..."` を参照します。読み取った値は `$HOME` / `${HOME}` を置換し、残りの `$` がなく絶対パスなら採用します。Windows の既知フォルダー取得に失敗した例外は無視して通常の既定値へ進みます（`apps/host/server/model-directory-default.mjs:8-19`）。

Python 側の Documents 候補は重複を除いて保持します。Windows では `USERPROFILE/Documents` と設定されている OneDrive の各 `Documents` も候補に加わります。その他の OS では `XDG_DOCUMENTS_DIR` とホームの `Documents` が続きます（`strata_control/discovery.py:64-87`）。

## 有効になる条件

- **デスクトップアプリ / Node ホスト:** `defaultModelDirectory()` が `store.mjs` の読み込み時に一度呼ばれます。保存済みの `state.modelsDir` があればそれが優先されます。保存値がなくても、`STRATA_MODELS_DIR` が未設定または空でなく、既存の `STRATA_HOME/models` 以下に重みファイルがある場合は既存ライブラリを維持します。どちらにも当たらない新規ライブラリで、この変数由来の既定場所が使われます（`apps/host/server/store.mjs:60-87`）。
- **Terminal / Python discovery:** `data_dir_choices()` がこの変数を候補にしますが、`STRATA_SETTINGS_FILE` が truthy のアプリ内モードでは Documents 候補群そのものを探索しません。アプリ内モード判定は同変数の値の設定有無ではなく、`STRATA_SETTINGS_FILE` の truthy 判定です（`strata_control/discovery.py:59-61,262-274`）。
- Python の候補が既定データ先に採用されるのは、その `Documents/Strata` 下に `Models`、`models`、`packs` のいずれかがあり、さらにそのサブフォルダーが空でない場合です。自分の設定ファイルの `data_dir` があれば先に使われ、アプリの data folder が存在する場合も Documents より先です。どの候補も合わなければ呼び出し元の既定先になります（`strata_control/discovery.py:262-296`）。
- ホスト側の `STRATA_MODELS_DIR` はより直接的なモデルフォルダー指定です。Node helper は truthy な値を `path.resolve()` したパスにし、ホストのモデル既定値として扱います。保存済みフォルダーはさらに優先されます（`apps/host/server/model-directory-default.mjs:9-11`, `apps/host/server/store.mjs:60-87`）。
- Python の通常の `strata launch` では `--data-dir` が実際の起動先を指定できます。`STRATA_DOCUMENTS_DIR` は主に既存データの自動発見用で、`data_dir()` は設定済みデータ場所やアプリの場所を先に選びます（`strata_cli/launch/catalog.py:546-553`, `strata_cli/launch/cmd.py:90-92`, `strata_control/discovery.py:277-289`）。

## 実行時の詳細

Node ホストではモジュール初期化時に既定値が計算され、その結果から `MODELS_DIR` を選びます。選ばれたフォルダーはホスト起動ログの `models dir   ·  ...` に出ます。Documents 由来の既定先を作成またはアクセス確認できなければ `STRATA_HOME/models` に切り替わり、stderr に `[strata] Strata could not use ... for models (...), so models go to .... You can pick another folder in Settings.` の警告を出します（`apps/host/server/store.mjs:60-87`, `apps/host/server/index.mjs:280-286`）。この初期化後にプロセスの環境を変更しても、`DEFAULT_MODELS_DIRECTORY` と初期の `MODELS_DIR` は再評価されません。Settings API からモデルフォルダーを変えた場合は、検証して状態ファイルへ保存した後、プロセス内の `MODELS_DIR` を更新します（`apps/host/server/store.mjs:131-139`, `apps/host/server/index.mjs:1425-1440`）。

Python の `documents_dirs()` は呼ばれた時点の `os.environ`（または明示的に渡された mapping）を読みます。永続キャッシュはありません。`data_dir()` は設定場所・アプリの場所の後に Documents 候補を順に見て、`Documents/Strata` に既存モデルデータがある最初の場所を返します。Terminal の共通カタログからこの関数が呼ばれ、起動時のデータフォルダー選択などに使われます。`strata models move` では `--from` がなければ同じ探索結果を移動元候補にします（`strata_cli/launch/catalog.py:546-553`, `strata_cli/cli.py:617-626`）。候補フォルダーが存在しない、空、または読めない場合はモデルデータ候補として採用せず、後続候補または呼び出し元の既定先に進みます（`strata_control/discovery.py:277-296`）。

ホストの supervisor は子プロセスの環境を作る際に `process.env` 全体を含めます。そのため、設定されていれば名前自体は継承されますが、今回確認した engine 起動経路には `STRATA_DOCUMENTS_DIR` を読み取る Strata の実装は見つかりませんでした。ホストで選ばれたモデルディレクトリー自体は別途処理に渡されます（`apps/host/server/supervisor.mjs:243-244`）。

## 根拠

- Node の直接参照と OS 別フォールバック: `apps/host/server/model-directory-default.mjs:7-19`
- 保存先・既存ライブラリ・書き込み失敗時 fallback と警告: `apps/host/server/store.mjs:60-87`
- 起動時に表示するモデル場所: `apps/host/server/index.mjs:280-286`
- 実行中に Settings から変更する処理: `apps/host/server/index.mjs:1425-1440`, `apps/host/server/store.mjs:112-139`
- Python の直接参照と OS 別 Documents 候補: `strata_control/discovery.py:59-87`
- Documents 候補の適用条件と既定先への fallback: `strata_control/discovery.py:262-296`
- Terminal の共通カタログからの利用: `strata_cli/launch/catalog.py:546-553`
- `000_envvers.md` には候補名として掲載されています（該当行 708）。上記二つの本番ソース読み取りを確認しました。調査では build・GPU 実行・性能測定・テストを行っていません。
