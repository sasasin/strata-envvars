# `STRATA_DATA`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata の Docker entrypoint が、コンテナ内のモデルデータとセットアップ設定ファイルを置くディレクトリを選びます。標準値は `/data` です。entrypoint はこの値を `setup.py --data-dir` に渡して初回セットアップを行い、モデル別の設定ファイルを同じディレクトリ下の `config/` に保存・選択します。エンジンの場所や実行時の GPU 設定を直接変える変数ではありません。

この名前を環境から読む本番コードは `docker-entrypoint.sh` のみです。一般の `setup.py` やサーバープロセスが `STRATA_DATA` を直接読み取る実装は見つかりませんでした。

## 値と判定

| 入力 | entrypoint が使う値 |
|---|---|
| 未設定 | `/data` |
| 空文字 | `/data` |
| その他 | 与えられた文字列をそのままパスとして使用 |

シェルの `${STRATA_DATA:-/data}` 展開なので未設定と空文字は同じ扱いです。数値 parse、値域検査、空白除去、相対パスの解決は entrypoint では行いません。相対パスを指定した場合は、先に `cd /opt/strata` しているため、その作業ディレクトリ基準になります。値はシェルの引用符付き展開で使われ、空白を含むパスも一つの引数として渡されます。

## 有効になる条件

- `STRATA_DATA` の読み取りは Docker 用 `docker-entrypoint.sh` の実行時に限られます。Dockerfile はこのスクリプトを `ENTRYPOINT` に設定しています。
- シェルは `set -e` を有効にし、指定先の `config/` を `mkdir -p` します。作成に失敗すれば entrypoint はその時点で終了します。
- `CONFIG` が設定されている場合は指定された設定ファイルをモデル別リンクにします。設定がない場合は、既存リンクが `$STRATA_DATA/config/` 内を指していて `REINSTALL` が `1` でなければそれを維持します。それ以外では、`REINSTALL=1` またはモデル別設定ファイルが未作成のときにセットアップを実行します。
- `setup.py` に `--data-dir` が渡されるのは、そのセットアップ分岐です。後続の通常起動では `--data-dir` は渡されません。entrypoint 自体は `STRATA_DATA` を変えたときに旧パスから新パスへデータをコピーしません。セットアップが走る場合の既存データの探索・移動は `setup.py` の `data_folder()` の別ロジックです。

## 実行時の詳細

entrypoint は `STRATA_DATA` が未設定または空なら `/data` に代入し、`$STRATA_DATA/config/strata-<family>-<model>.json`（qwen family は family prefix なし）を当該モデルのセットアップ設定ファイルとして扱います。セットアップ分岐では `setup.py --setup --yes` に `--data-dir "$STRATA_DATA"` を渡します。`setup.py` は引数のパスを解決して作成し、その場所を `data_dir` として設定に記録します。モデルファイルは既定でその配下の `models/`、pack は `packs/`、MTP データは `mtp/` を探索・使用します。

`STRATA_DATA` を指定したディレクトリに書き込み可能な Docker volume を割り当てると、データとモデル別設定をコンテナ再作成後も保持する構成になります。Dockerfile の例では volume を `/data` に割り当てています。値を変更した場合、entrypoint は変更後のパスに新しい `config/` を作りますが、entrypoint 自体は前のパスからデータをコピーしません。`CONFIG` が空で、指定先にモデル別設定ファイルもなく、維持対象となる既存リンクもない場合はセットアップ分岐へ進みます。セットアップが走れば `setup.py` は保存済み設定や既存インストールからデータを探索し、条件に応じて移動することがあります。

通常起動の最終段では `setup.py` を `--port` 等とともに実行しますが、`STRATA_DATA` は環境変数として明示的には参照されません。データ場所は初回セットアップ時に渡した `--data-dir` と保存済み設定が担います。そのため、変数を起動後に書き換えても実行中のサーバーのデータ場所は変わらず、entrypoint の次回実行時に設定ファイル選択先・セットアップ引数として読み直されます。

## 根拠

- `docker-entrypoint.sh:6-7,19,37-44`: entrypoint の実行環境、作業ディレクトリ、既定値、モデル別設定パスの構築とディレクトリ作成。
- `docker-entrypoint.sh:55-94`: `CONFIG`、既存リンク、`REINSTALL`、設定ファイル有無による分岐と、初回セットアップへの `--data-dir` 引き渡し。
- `docker-entrypoint.sh:96-106`: 通常起動では `--data-dir` を渡さないこと。
- `Dockerfile:20-23,25-32,117`: `/data` volume の使用例、データ類を volume に置く構成、および entrypoint の登録。
- `setup.py:4870-4872,3813-3823,3862-3864,4952-4955,5464-5467,5567-5569`: `--data-dir` の説明、指定ディレクトリの決定・作成・保存、既定の models ディレクトリ、および pack/MTP データの場所。
- `docs/DETAILS.md` などの文書には `STRATA_DATA` 自体の説明は見つかりませんでした。上記はこの commit の entrypoint と `setup.py` の実装に基づく説明です。
