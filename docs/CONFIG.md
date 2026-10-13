# `CONFIG`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソースで、外部ライブラリや Docker 自身の環境変数動作は含めない。

## 役割

Docker コンテナの entrypoint に、起動に使う Strata 設定 JSON のパスを指定します。空でなければ `MODEL` / `FAMILY` から作る通常の設定ファイル選択より優先され、`/opt/strata/strata-<family-model>.json` を指定ファイルへのシンボリックリンクにします。その後の `setup.py` 起動時に、このリンク先を含むインストール済み設定からモデル設定が選ばれます。

この変数を読む実装は `docker-entrypoint.sh` のみです。通常の `setup.py` や engine が `CONFIG` を直接読む処理はありません。

## 値と判定

| 値 | entrypoint の扱い |
|---|---|
| 未設定 | `CONFIG="${CONFIG:-}"` により空文字になる。非指定時の選択へ進む |
| 空文字 | 未設定と同じ。`[ -n "$CONFIG" ]` が偽になる |
| 非空文字列 | 前後空白を除去せずパスとして扱う。`[ -f "$CONFIG" ]` が成功すればそのパスを設定元にする |
| 非空だが通常ファイルでないパス、存在しないパス | `CONFIG=<値> does not exist.` を stderr に出し、終了コード 1 で終了する |

値を数値や真偽値として parse しません。`-f` はシェルのファイル判定で、リンク先をたどって通常ファイルかを確認します。ファイル内容の JSON 検証は entrypoint では行いません。

## 有効になる条件

- Docker イメージの `ENTRYPOINT` は `./docker-entrypoint.sh` であり、同スクリプトが `CONFIG` を処理します。ホスト上で `setup.py` を直接起動する場合、この変数による選択処理はありません。
- `CONFIG` が非空の場合、`REINSTALL=1` かどうかや既存リンクの有無より先にこの分岐が選ばれます。`CONFIG` 指定時は entrypoint 自身の再セットアップ分岐を通りません。
- `CONFIG` が空の場合は、まず `REINSTALL` が `1` でなく、モデル用リンクが `/data/config/` 配下の既存ファイルを指していればそのリンクを維持します。それ以外は `REINSTALL=1` またはモデル設定ファイルが未作成なら setup を実行し、そうでなければ `/data/config/strata-<model>.json` へのリンクを作ります。

## 実行時の詳細

entrypoint は `FAMILY` と `MODEL` からリンク名を作ります。`FAMILY=qwen` では family 接頭辞なし、それ以外では小文字化したモデル名の前に `<family>-` を付け、リンク名を `/opt/strata/strata-$tag.json` とします。`CONFIG` が非空なら、ファイル判定に成功した後 `ln -sfn "$CONFIG" "$link"` を実行し、`Config: <値> (from CONFIG)` を標準出力に表示します。指定ファイル自体は書き換えません。

続いて entrypoint は `.venv/bin/python setup.py --port ...` を実行します。`setup.py` は `ROOT` 内の `strata-*.json` を列挙し、JSON オブジェクトに truthy な `exe` と list 型の `args` があるものをモデル設定として扱います。CONFIG のファイル名は entrypoint が作るリンク名としては `MODEL` / `FAMILY` に依存しますが、リンク先の JSON 内容が有効な設定かどうかはこの後の `setup.py` 側で判定されます。無効な JSON や `exe` / `args` のない JSON は警告付きで設定一覧から除外されます。

## 根拠

- `docker-entrypoint.sh:19-35`: `FAMILY`、`MODEL` とともに `CONFIG` を空既定で設定。
- `docker-entrypoint.sh:41-44`: family/model からリンク名を作成。
- `docker-entrypoint.sh:55-70`: CONFIG の優先順位、ファイル判定、失敗時のメッセージ、リンク作成とログ。
- `docker-entrypoint.sh:71-106`: CONFIG が空の場合の setup 条件と、最後に `setup.py` を起動する処理。
- `setup.py:4000-4003,4063-4081`: 設定候補の列挙と JSON 内の `exe` / `args` 判定。
- `Dockerfile:25-28,117`: setup 用環境変数とコンテナ entrypoint の指定。
- `docs/INSTALL.md:103-117`: Docker の `CONFIG` が任意の設定ファイルでモデル選択を上書きする説明、および既存 `/data/config/` リンクの扱い。
