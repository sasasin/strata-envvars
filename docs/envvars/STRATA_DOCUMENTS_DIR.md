# `STRATA_DOCUMENTS_DIR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この変数は Strata が Documents フォルダーとして扱う場所を指定します。デスクトップ host では新規モデルフォルダーの既定値と、Linux のチャット用 workspace の既定場所の基準になります。Terminal では既存データを探す `Documents/Strata` 候補を追加します。どちらも値をパスとして扱いますが、相対パスや空文字の処理、候補が採用される条件は異なります。[`app/host/server/model-directory-default.mjs:14-25,34-42`](../../../../Niko1221/Strata/app/host/server/model-directory-default.mjs)、[`terminal/strata_control/discovery.py:65-88,263-295`](../../../../Niko1221/Strata/terminal/strata_control/discovery.py)

## 値と判定

| 読み取り経路 | 未設定・空文字 | 設定値の扱いと例 |
|---|---|---|
| デスクトップ host の `documentsFolder()` | `undefined` と `""` は未指定扱い。Windows は Windows の既知 Documents フォルダーを試し、Linux は XDG の設定を試す。最終 fallback は `<home>/Documents`。 | 値を trim・展開・正規化せずに受け取る。絶対パスならそのまま使う（例 `/mnt/docs`）。相対パス（例 `docs`）や空白だけの値は絶対パスでないため `<home>/Documents` に fallback。Linux の XDG Documents 値や設定ファイルの値は別途 `$HOME` 展開と絶対パス検査を行うが、この変数には行わない。 |
| Terminal の `documents_dirs()` | `None` と `""` は候補に追加されない。 | truthy な値を `Path(explicit)` として最初の候補に追加する。trim、`expanduser()`、絶対パス検査、正規化はしない（例 `~/docs` は文字どおり `~/docs/Strata` 候補）。ただし候補フォルダーにモデル等がなければ採用されない。 |

デスクトップ host は Windows / Linux / macOS で後続 fallback が異なります。Terminal は Windows で `USERPROFILE`（空なら home）の `Documents` と設定済み OneDrive 各種の `Documents` も候補にし、非 Windows では `XDG_DOCUMENTS_DIR` と `<home>/Documents` も候補にします。重複候補は除去されます。[`app/host/server/model-directory-default.mjs:15-25`](../../../../Niko1221/Strata/app/host/server/model-directory-default.mjs)、[`terminal/strata_control/discovery.py:67-88`](../../../../Niko1221/Strata/terminal/strata_control/discovery.py)

この変数自体の数値変換、大小文字比較、許容値域はありません。ホストは絶対パスだけを使い、Terminal は候補を作った後に `Documents/Strata` 内の `Models` / `models` / `packs` のいずれかに中身があるかを調べます。[`terminal/strata_control/discovery.py:288-297`](../../../../Niko1221/Strata/terminal/strata_control/discovery.py)

## 有効になる条件

- **デスクトップ host のモデルフォルダー**: 本変数の Documents 値に `Strata/Models` を足した場所が既定です。`STRATA_MODELS_DIR` が truthy なら、その `path.resolve()` 値がこの既定場所を置き換えます。ただし保存済み `state.modelsDir` はどちらの環境変数由来の場所よりも優先されます。[`app/host/server/model-directory-default.mjs:7-25`](../../../../Niko1221/Strata/app/host/server/model-directory-default.mjs)、[`app/host/server/store.mjs:69-85`](../../../../Niko1221/Strata/app/host/server/store.mjs)
- 保存済み `state.modelsDir` がある場合はそれが優先されます。保存先がなくても、`STRATA_MODELS_DIR` が未指定で `STRATA_HOME/models` 配下に既存 GGUF 重みがあれば既存フォルダーを維持します。それ以外で Documents 由来の既定フォルダーを作成・検査します。[`app/host/server/store.mjs:52-63,69-89`](../../../../Niko1221/Strata/app/host/server/store.mjs)
- Documents 由来の既定フォルダーを作成または読み書き実行可能にできない場合、モデル用の fallback は `STRATA_HOME/models` です。この失敗で host 起動を止めません。[`app/host/server/store.mjs:69-88`](../../../../Niko1221/Strata/app/host/server/store.mjs)
- **デスクトップ host の workspace**: `STRATA_WORKSPACE` が truthy ならその `resolve()` 値が優先されます。未指定の場合、Linux では本変数が workspace 基準にも使われ、`Strata/Workspace` を作成します。ただし既存 workspace が `<home>/Documents/Strata/Workspace` にあり、指定先にはまだ workspace がない場合は旧場所を保ちます。Windows と macOS では `workspaceBases()` が `<home>/Documents` を使うため、本変数は workspace 場所に影響しません。作成に失敗すると次の候補を試し、全候補で失敗した場合は home を使います。[`app/host/server/index.mjs:111-123`](../../../../Niko1221/Strata/app/host/server/index.mjs)、[`app/host/server/model-directory-default.mjs:34-42`](../../../../Niko1221/Strata/app/host/server/model-directory-default.mjs)
- **Terminal のモデルデータ候補**: `STRATA_SETTINGS_FILE` が設定された app mode では Documents 候補自体を加えません。通常の Terminal では自分の設定とデスクトップ app の設定が Documents 候補より先です。両設定の場所が異なるときは更新時刻が新しい側を優先し、古い側の設定ファイルを同期します（ただし app 側の場所が存在しない場合は Terminal 側を維持）。[`terminal/strata_control/discovery.py:60-62,242-275`](../../../../Niko1221/Strata/terminal/strata_control/discovery.py)
- Terminal は `Documents/Strata` の `Models` / `models` / `packs` のいずれかに中身がある候補だけを採用します。該当しなければ `Catalog` の install 隣接既定値に進みます。個別モデルの run config や起動設定の `--data-dir` がある場合は、各呼び出し側がモデル実体または明示 data dir を優先します。[`terminal/strata_control/discovery.py:278-297`](../../../../Niko1221/Strata/terminal/strata_control/discovery.py)、[`terminal/strata_cli/launch/catalog.py:753-774`](../../../../Niko1221/Strata/terminal/strata_cli/launch/catalog.py)、[`terminal/strata_cli/launch/runner.py:1445-1465,1590-1597,1828-1840`](../../../../Niko1221/Strata/terminal/strata_cli/launch/runner.py)

## 実行時の詳細

デスクトップ host の `store.mjs` はモジュール初期化中に `DEFAULT_MODELS_DIRECTORY` を一度計算し、同じ初期化で state を読み `MODELS_DIR` を選びます。`index.mjs` も起動時に `WORKSPACE` を決めます。そのためプロセス起動後に環境変数を変えても、これらの値は再評価されません。モデル保存先を後から変更する経路は環境変数ではなく Settings の `changeModelsDirectory()` で、state に保存してから `MODELS_DIR` を更新します。[`app/host/server/store.mjs:52-63,85-89,133-141`](../../../../Niko1221/Strata/app/host/server/store.mjs)、[`app/host/server/index.mjs:114-124`](../../../../Niko1221/Strata/app/host/server/index.mjs)

Terminal の `documents_dirs()` は呼ばれるたびに渡された `environ`（省略時は `os.environ`）を参照し、結果を cache しません。`Catalog.data_dir_choice()` から `discovery.data_dir()` が呼ばれ、設定済みデータ場所、既存 app data、モデル等を含む Documents 候補、最後に install 隣接 default の順で選びます。通常 Terminal では設定同期のためファイル書き込みが起きる場合がありますが、Documents 候補の発見そのものは読み取りです。app mode は同期と Documents 候補を使いません。[`terminal/strata_control/discovery.py:65-88,242-290`](../../../../Niko1221/Strata/terminal/strata_control/discovery.py)、[`terminal/strata_cli/launch/catalog.py:753-760`](../../../../Niko1221/Strata/terminal/strata_cli/launch/catalog.py)

## ログと測定値

デスクトップ host が既定モデルフォルダーを作成・検査できない場合、stderr に `[strata] ` を先頭につけ、次の文面を `console.warn` で出します（`${preferred}` と `${legacy}` は選択されたパス、`${error.code ?? error.message}` はエラー値です）。

```text
Strata could not use ${preferred} for models (${error}), so models go to ${legacy}. You can pick another folder in Settings.
```

この警告はモデル保存先選択の失敗時に限られます。Terminal の Documents 候補が採用されない場合に、この変数専用の警告・終了・例外を出すコードは確認できません。測定値はありません。[`app/host/server/store.mjs:77-89`](../../../../Niko1221/Strata/app/host/server/store.mjs)、[`terminal/strata_control/discovery.py:278-297`](../../../../Niko1221/Strata/terminal/strata_control/discovery.py)

## 根拠

- `app/host/server/model-directory-default.mjs:7-25,34-42` — デスクトップ host のモデル Documents パスと workspace 候補。
- `app/host/server/store.mjs:52-63,69-89,133-141` — state 読み込み、既定モデル場所の優先順位、失敗時 fallback と警告、保存先変更。
- `app/host/server/index.mjs:111-124` — workspace の起動時決定と `STRATA_WORKSPACE` 優先。
- `terminal/strata_control/discovery.py:60-88,242-297` — Terminal の app mode、Documents 候補、設定同期、候補採用条件。
- `terminal/strata_cli/launch/catalog.py:753-774`、`terminal/strata_cli/launch/runner.py:1445-1465,1590-1597,1828-1840` — Terminal からの呼び出し、保存済みモデル場所・`--data-dir` の優先。
