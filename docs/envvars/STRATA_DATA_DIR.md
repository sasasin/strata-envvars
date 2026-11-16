# `STRATA_DATA_DIR`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

この変数は、Strata Terminal のインストーラが Terminal 本体を置くデータルートを指定する。また、Python のインストール探索では、その直下の `install/` を既存モデル設定の探索候補に加える。モデルファイルの保存先を直接決める変数ではない。`strata launch --data-dir` はモデル用データフォルダーの指定であり、インストール先とは別に扱われる（`packaging/install.sh:24-27,110-141`、`packaging/install.ps1:87-89,113-115`、`strata_control/discovery.py:170-192`、`strata_cli/launch/runner.py:41-57`）。

## 値と判定

| 読み取り箇所・条件 | 未設定 | 空文字 | 設定値の処理・無効値 |
|---|---|---|---|
| `packaging/install.sh`（Linux/macOS） | `${XDG_DATA_HOME:-$HOME/.local/share}/strata` | `:-` により未設定と同じ既定値 | 非空文字列をパスとして使い、`terminal/<version>` 以下へ展開する。値を parse・正規化・検証する処理はない。変数展開は引用されており、値の `~` はシェルによるホーム展開を受けない（`packaging/install.sh:24-27,110-112`）。 |
| `packaging/install.ps1`（Windows） | `%LOCALAPPDATA%\Strata`。`LOCALAPPDATA` も未設定・空なら `Die` で終了 | PowerShell の偽値として未設定と同じ扱い | 非空値を `$data` に代入する。形式や存在確認の事前検証はなく、後続のディレクトリ作成・展開で失敗すればインストーラのエラー経路に入る（`packaging/install.ps1:87-90,113-115,144`）。 |
| Python のインストール探索 | `install/` 候補を追加しない | `if data_root` が偽となり候補を追加しない | `environ.get` で文字列を取得し、`Path(...).expanduser() / "install"` を候補化する。値の形式検査はなく、候補内に認識対象の run config がある場合だけ探索結果に残る（`strata_control/discovery.py:161-193`）。 |

Python の探索では、値そのものの比較や大文字小文字・数値の判定はしない。空白だけの値や不正なパス文字列も文字列として候補化されるが、そこに有効な run config が見つからなければ候補から落ちる。Linux/macOS インストーラでは空文字を既定値に置き換える一方、Python 探索では空文字を候補なしとする。

## 有効になる条件

- インストール先の上書きに使われるのは `install.sh` / `install.ps1` の実行時である。インストール場所はそれぞれ `DATA_DIR/terminal/<version>`、`$data/terminal/<version>` となる。設定済みの `STRATA_DATA_DIR` が空なら両インストーラとも既定値を使う（`packaging/install.sh:24-27,110-112`、`packaging/install.ps1:87-89,113-115`）。
- Python の `discovery.places` では、明示引数または `STRATA_INSTALL_DIR` が `raw is not None` で選ばれると、その場所だけを返すため、`STRATA_DATA_DIR` の候補は調べない。そうでなければ `STRATA_DATA_DIR/install` は `here`、ユーザー設定に記録された場所、アプリの場所より前に候補へ追加される（`strata_control/discovery.py:161-179`）。ただし `STRATA_DATA_DIR/install` に `strata-*.json` 形式の run config がなければ探索結果には含まれない（同 `:142-150,180-193`）。
- `find_install` は候補の先頭を採用し、どの候補にも run config がなければアプリのインストール場所へ fallback する。この場合、変数を設定しただけでは `STRATA_DATA_DIR/install` が使われるとは限らない（`strata_control/discovery.py:196-204`）。
- `strata launch` の `--data-dir` はモデルデータ用設定である。インストール探索候補を上書きする指定ではない。計画時の説明では `--data-dir` があればそれを使い、なければ `STRATA_DATA_DIR` を参照する（`strata_cli/launch/runner.py:41-57,2393-2397`）。

## 実行時の詳細

シェル版インストーラは起動時に `DATA_DIR` を一度設定し、その後の展開・リンク作成に使う（`packaging/install.sh:24-27,110-141`）。PowerShell 版も処理中に `$data` を一度決め、展開先と `current` の設定先に使う（`packaging/install.ps1:87-90,113-115,174-189`）。

Python 側は `places()` の呼び出しごとに `environ.get("STRATA_DATA_DIR")` を評価し、値を `Path.expanduser()` に通す。関数内 static cache はない。通常の呼び出しでは `environ` の既定値はその時点の `os.environ` である（`strata_control/discovery.py:161-172`）。`strata models list` などの共有探索経路は `discovery.places` を呼ぶ（`strata_cli/launch/catalog.py:173-177,249-253`、`strata_control/models.py:80-86`）。

`strata launch --plan` の preflight は、選ばれたインストールが指定データフォルダーの外にあり、明示的なインストール場所ではない場合、次の警告を `warnings` に加える。これは説明だけで、インストールを切り替えたりファイルを移動したりしない: `Strata is using the earlier install in ... (... saved model setting(s) and its engine settings), not a clean one in ...: the data folder only says where model files are kept. To test from scratch, use a new user account or remove the earlier install first.`（`strata_cli/launch/runner.py:41-57,2380-2397,2419-2420`）。

## ログと測定値

Python の条件に合う場合、上記の `strata launch --plan` 警告が観測できる。インストーラでは、この変数専用の受理値ログはない。Windows で `STRATA_DATA_DIR` と `LOCALAPPDATA` の両方が空の場合は stderr に `strata installer: Windows did not say where your user folder is. Set $env:STRATA_DATA_DIR to a folder you own, for example $env:STRATA_DATA_DIR='C:\Strata', and run this again.` を出して停止する（`packaging/install.ps1:24,87`）。パス作成・展開の失敗時は既存のインストーラ失敗処理へ進む（`packaging/install.sh:112-114`、`packaging/install.ps1:144`）。性能測定値は該当しない。

## 根拠

- `packaging/install.sh:24-27,110-141` — Unix 系インストーラの既定値、保存先。
- `packaging/install.ps1:87-90,113-115,144,174-189` — Windows での値判定、保存先と失敗経路。
- `strata_control/discovery.py:161-204` — 探索候補、優先順、run config の条件、fallback。
- `strata_cli/launch/catalog.py:173-177,249-253`、`strata_control/models.py:80-86` — 共有探索関数の呼び出し。
- `strata_cli/launch/runner.py:41-57,2380-2420` — `--data-dir` との選択、計画時警告。
