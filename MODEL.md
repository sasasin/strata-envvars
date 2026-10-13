# `MODEL`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソースであり、Docker 自体の挙動は含めない。

## 役割

Docker コンテナーの `docker-entrypoint.sh` が、初期セットアップするモデルと起動する設定ファイルを選びます。Strata の C++ エンジンや `serve/server.py` が `MODEL` を直接読む実装は確認できません。entrypoint は値を設定ファイル名に使い、セットアップが必要な場合は `setup.py --model` に渡します。

## 値と判定

`MODEL="${MODEL:-IQ2_XS}"` で読み込みます。シェルの `:-` 展開なので、未設定と空文字はいずれも `IQ2_XS` になります。空白を trim したり、文字列をモデル名に正規化したりする処理はありません。

| 状況 | entrypoint の扱い |
|---|---|
| 未設定または空文字 | `IQ2_XS` を使用 |
| 非空文字列 | その値を保持し、設定ファイル名の生成に使う |
| セットアップが必要 | 元の値を `setup.py --model <値>` に渡す。`setup.py` の argparse は `MODELS` のキーと完全一致する値だけを受け付ける |

設定ファイル用の `tag` では `MODEL` の ASCII 大文字 `A`〜`Z` だけを小文字に変換します。句点、ハイフン、アンダースコアなどはそのまま残ります。`FAMILY=qwen` の場合は `strata-<小文字化したMODEL>.json`、それ以外は `strata-<FAMILY>-<小文字化したMODEL>.json` を参照します。`FAMILY` の値自体は entrypoint では検証されませんが、セットアップに進む場合は `setup.py --family` の選択肢で検証されます。

## 有効になる条件

entrypoint は常に `MODEL` を設定ファイル名に反映しますが、値がモデル取得やインストール設定に使われるのは、既存設定を選ぶとき、または新規セットアップ時です。

- `CONFIG` が空でなく、指定ファイルが存在するときは、そのファイルへのリンクを作って優先します。`MODEL` は setup の `--model` 引数には渡されません。
- `CONFIG` が空で、対象の `strata-<tag>.json` がデータ領域に既にある場合は、その設定を使います。通常は再セットアップせず、`MODEL` に対応する既存モデル設定を選びます。
- `REINSTALL=1` の場合、既存リンクを保持せず、対象の設定を再セットアップします。
- 対象設定がなく `REINSTALL` も `1` でない場合も、セットアップします。このとき未対応のモデル名は `setup.py` の `--model` choices で拒否されます。
- 既存の `/opt/strata/strata-<tag>.json` シンボリックリンクがデータ領域内の設定ファイルを指していて、`CONFIG` が空、かつ `REINSTALL` が `1` でない場合、そのリンク先を保持します。

## 実行時の詳細

entrypoint は `MODEL` をプロセス起動時にシェル変数へ設定し、同じシェル内で `tag` と設定ファイルパスを組み立てます。値を再読込する処理はありません。新規セットアップでは、モデル名を `setup.py --setup --yes --family ... --model ...` に渡し、生成された `/opt/strata/strata-<tag>.json` を `/data/config/strata-<tag>.json` にコピーまたは更新します。その後は最終的に `setup.py --port ...` を実行します。設定を再利用する場合も、`/opt/strata/strata-<tag>.json` を対象設定へリンクしてから起動します。

`CONFIG` が非空なら対象ファイルの存在を確認し、存在しなければ stderr に `CONFIG=<値> does not exist.` を出して終了します。entrypoint はセットアップまたは既存設定の選択時に `Config: ...` を出力します。`MODEL` 自体に関するログは、通常 `Config: ... (from MODEL <値>...)` の形です。

## 根拠

- `docker-entrypoint.sh:19-35`: `MODEL` の既定値、`FAMILY` などの初期値、`CONFIG` との関係。
- `docker-entrypoint.sh:37-43`: `FAMILY` と `MODEL` からタグ、設定ファイル名を構築。
- `docker-entrypoint.sh:55-70`: `CONFIG`、既存リンク、`REINSTALL`、設定ファイル有無による優先順位。
- `docker-entrypoint.sh:71-93`: setup へのモデル引き渡し、設定保存、観測可能な `Config:` ログ。
- `docker-entrypoint.sh:96-106`: 設定選択後に `setup.py` を実行する処理。
- `setup.py:4827-4831`: `--family` と `--model` の argparse choices。
- `docs/INSTALL.md:100-117`: Docker の `MODEL` と `FAMILY`、既存モデル切替、`REINSTALL`、`CONFIG`、モデル名の小文字化についての説明。上記の実装と一致する。
