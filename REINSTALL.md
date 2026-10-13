# `REINSTALL`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。Strata 同梱の Docker 起動スクリプトでの使用を調査。

## 役割

`REINSTALL` は Docker コンテナの entrypoint が、選択したモデルのセットアップを再実行するか決めるフラグです。値が文字列 `1` の場合、選択モデルの `/data/config/strata-<tag>.json` がすでにあっても `setup.py --setup --yes --no-start` を実行し、生成された設定をデータボリュームへ反映します。エンジンの再ビルドや削除を指示する変数ではありません。Dockerfile ではエンジンはイメージ内にあると説明され、entrypoint もセットアップ時にその旨を表示します。

## 値と判定

entrypoint は `${REINSTALL:-0}` を文字列 `1` と比較します。数値変換や真偽値 parse はしません。

| 値 | 判定 | 結果（`CONFIG` が空の場合） |
|---|---|---|
| 未設定 | `0` に置換され、`1` ではない | 既存設定があればセットアップを省略して起動。設定ファイルがなければセットアップ |
| 空文字 | `:-` により `0` に置換 | 未設定と同じ |
| `1` | 完全一致 | 既存設定の有無によらずセットアップ |
| `0`、`true`、`01`、`1 `、その他の非空文字列 | `1` と不一致 | 既存設定があればセットアップを省略。設定ファイルがなければセットアップ |

大文字小文字や前後の空白を正規化しません。設定有無を見ているのではなく、展開後の値全体が正確に `1` かを判定します。

根拠: `docker-entrypoint.sh:61,70`。

## 有効になる条件

- `CONFIG` が空でない場合は `REINSTALL` より優先されます。entrypoint は `CONFIG` のファイル存在を確認し、`/opt/strata/strata-<tag>.json` をそのファイルへのリンクにして、セットアップを実行しません。`REINSTALL=1` でもこの分岐は変わりません。ファイルがなければ `CONFIG=... does not exist.` を stderr に出して終了します。
- `CONFIG` が空で、`REINSTALL` が `1` 以外の場合、`/opt/strata/strata-<tag>.json` が `/data/config/` 配下を指す有効なシンボリックリンクなら、そのリンクを保ってセットアップを省略します。そうでなくても `/data/config/strata-<tag>.json` が存在すれば、そこへリンクし直してセットアップを省略します。
- `CONFIG` が空で、`REINSTALL=1` または選択モデルのデータ側設定ファイルがない場合にセットアップします。設定ファイルがない場合は `REINSTALL` を設定しなくても初回セットアップになります。
- `REINSTALL=1` はモデル選択 (`FAMILY`, `MODEL`) ごとの設定ファイルを対象にします。別モデル用の既存設定があること自体は、その選択モデルの設定ファイルがない限り再セットアップを抑止しません。

根拠: `docker-entrypoint.sh:19-43,55-70`。

## 実行時の詳細

変数は entrypoint の実行時にシェルで評価され、プロセス中に再評価されるキャッシュはありません。`REINSTALL=1` のセットアップ分岐では、`FAMILY`, `MODEL`, `CONTEXT`, `VISION`, `HOST`, `API_KEY`, `PORT`, `LOW_RAM` を引数として常に `setup.py` に渡します。`KV`, `GPUS`, `GPU`, `LAYER_SPLIT`, `GGUF_DIR`, `RESIDENT_BUDGET_GIB`, `KV_STREAMING` は空でない場合だけ対応する CLI 引数に追加します。したがって、再セットアップ時の設定値は現在渡されている環境変数と `setup.py` の既定値から決まります。値の妥当性検証や数値範囲の判定は `REINSTALL` 自身にはありません。

呼び出しは `.venv/bin/python setup.py --setup --yes ... --no-start` です。`--yes` は推奨回答を自動選択し、`--no-start` はセットアップ直後の起動を止めます。entrypoint はセットアップ後、生成された `/opt/strata/strata-<tag>.json` とデータ側設定を比較し、内容が異なる場合はデータ側へコピーします。その後 `Config: ... (from MODEL ..., just set up)` を表示し、最後に通常の `setup.py --port ...` を `exec` して選択モデルを起動します。後続の起動でも `REINSTALL=1` が残っていれば、毎回このセットアップ分岐に入ります。

環境変数が `setup.py` の引数に追加されない項目は、この entrypoint の再セットアップでは明示的に変更されません。`setup.py` の `--setup` は明示的なセットアップ経路を選び、`--no-start` はその処理からモデル起動へ進まないようにします。

根拠: `docker-entrypoint.sh:65-106`, `setup.py:4875-4877,5814-5815,5842-5849`。

## 文書との照合

`docs/INSTALL.md` は `REINSTALL=1` を、すでにセットアップ済みのモデルの context、vision、KV、host、API key、LOW_RAM などを変える場合に使うと案内しています（`docs/INSTALL.md:103-111,133-134`）。entrypoint ではそれらの環境変数をセットアップ CLI に渡す分岐になっています。なお、ソースでは GPU 選択など一部の値も条件付きで渡されます（`docker-entrypoint.sh:76-86`）。

## 根拠

- `docker-entrypoint.sh:19-43,55-106` — 既定値、設定ファイルの選択、`REINSTALL` の比較、セットアップと起動の分岐。
- `setup.py:4875-4877,5814-5815,5842-5849` — `--setup` / `--no-start` の CLI と、設定保存後の起動処理。
- `Dockerfile:6-11,30-35` — エンジンはイメージに含まれ、`REINSTALL=1` が設定変更時に使われるという説明。
- `docs/INSTALL.md:103-134` — Docker 利用時の変数と `REINSTALL=1` の案内。
