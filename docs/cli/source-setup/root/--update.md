# `--update`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`UPDATE.bat`、`update.sh` からも委譲） |
| オプション | `--update` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時 `False`、指定時 `True` |

## 役割

インストール済みモデルの起動前更新処理を実行し、モデル自体は起動しません。対象は Python 実行環境の Strata runtime packages、必要な engine、インストール済みモデルごとの設定移行と MTP draft vocabulary です。モデルの重みファイルはこの処理では更新しません（`setup.py:6682-6709`）。

## 使い方

ソース checkout のルートで直接実行する場合:

```sh
python setup.py --update
```

POSIX の更新 wrapper は `./update.sh`、Windows は `UPDATE.bat` です。これらはソース checkout なら先に `git pull --ff-only` を試み、その後 `setup.py --update` を起動します。GitHub archive など `.git` のないコピーではソース更新は行わず、既存モデルの設定等を確認します（`update.sh:1-6, 9-17, 55-62`; `UPDATE.bat:1-6, 11-20, 72-80`）。`setup.py --update` の直接実行には `git pull` はありません。

## 値と既定値

`argparse` の `action="store_true"` で宣言され、値は不要です。省略時は偽、指定時は真です。値を付ける形式ではなく、重複して指定しても真のままです。無効な値・未知の引数は `argparse` の標準エラー処理になります（`setup.py:8420, 8496-8498, 8553`）。

## 実行時の動作

`main()` はインストール済み設定を列挙した後、`--update` が真なら `update_install(have, a)` を返し、その後の通常 setup／モデル開始経路へ進みません。`update_install` は有効なモデル設定だけに絞り、該当設定がなければ「モデル未インストール」の案内を出して終了コード 0 を返します（`setup.py:8602-8609, 8617-8619, 6682-6692`）。

有効な設定がある場合は次の順に処理します。

1. `runtime_packages()` が組み立てる runtime requirements を pip で確認・導入します。同じ内容が記録済みなら再導入を省略します（`setup.py:3270-3276, 3295-3317, 6693-6694`）。
2. `--build` が指定されていなければ `update_installed_engine(a.prebuilt)` を呼びます。対象 engine がない場合や、既に十分新しい場合は更新対象になりません。更新失敗・使用中・該当 GPU 用 engine がない場合は警告して既存 engine を維持する経路があります（`setup.py:5235-5248, 5280-5323, 6695-6696`）。
3. 各モデルの JSON 設定を `upgrade_config()` に通します。旧 `--prefill 2048` の更新や WSL での KV streaming 設定削除が必要な場合、設定ファイルを一時ファイル経由で置換します。MTP を使う設定は draft vocabulary を更新し、Windows の HIP 設定では engine の隣の HIP runtime も確認します（`setup.py:6154-6159, 6657-6679, 6698-6704, 7171-7188`）。

各モデルを `[ok] ...: up to date` と表示し、最後に更新完了と通常の起動方法を表示して 0 を返します。更新分岐からモデル起動関数は呼ばれません（`setup.py:6704-6709, 8617-8619`）。

## 適用条件と副作用

- `--update` 自体は `setup.py` が見つけるこの Strata folder 内のインストール済みモデル設定に適用されます。設定ファイルは `exe` と `args` を持つ JSON として判定されます（`setup.py:6456-6469, 6472-6474, 6688-6692`）。
- `UPDATE.bat` / `update.sh` は `.git` があると `git pull --ff-only` を実行します。これは wrapper の動作で、`setup.py --update` の動作ではありません（`update.sh:9-17, 55-62`; `UPDATE.bat:11-20, 72-80`）。
- `--build` 併用時は `update_install` 内の ready-made / installed engine 更新呼び出し自体が省略されます。`--prebuilt`（既定値は `STRATA_PREBUILT_URL` または `PREBUILT_URL`）は、その engine 更新呼び出しの配布元として渡されます（`setup.py:8513-8514, 6695-6696`）。
- `--rollback-engine` も併用した場合、`main()` の rollback 分岐が `--update` 分岐より先に返るため、rollback のみ実行されます。`--setup` やモデル選択などを併用しても `--update` 分岐が先に返るため、通常 setup は行われません（`setup.py:8614-8620`）。
- `--data-dir`、`--move-data`、`--set-default-data-dir`、`--yes` は `--update` の分岐より前に共通データフォルダ処理へ渡されます。このため併用時は指定先フォルダの作成、設定保存、またはモデルデータの移動が起こり得ます。`--data-dir` 単独では通常既存データを移動せず、`--move-data` などが移動条件に影響します（`setup.py:6042-6050, 6136-6139, 8606-8619`）。
- engine の更新ではネットワーク取得や、ローカルビルド済み engine の再コンパイルが発生し得ます。パッケージ導入も pip を実行します（`setup.py:3295-3317, 5235-5323`）。

## 出力とエラー

進捗・完了案内・警告は `print()` による標準出力です。該当モデルがない場合も標準出力に案内を出して 0 で終了します（`setup.py:808-829, 6688-6692, 6704-6709`）。

不正な型の引数や未知の引数は argparse の usage/error 経路になります（`setup.py:8420, 8496-8498, 8553`）。pip 導入などの失敗は `run()` 側の例外・終了処理に委ねられます。engine 更新中の取得・compile・使用中など一部の失敗は警告して既存 engine を使い続けます（`setup.py:5235-5323`）。エラー時の終了コードは個々の呼び出し先に依存し、すべての失敗条件を一律に 1 とする処理は確認できません。

## 根拠

- parser と値の型: `setup.py:8420-8421, 8493-8501, 8553`
- `--update` 分岐と設定列挙: `setup.py:6456-6474, 8602-8619`
- 更新内容、未インストール時、完了出力: `setup.py:6682-6709`
- Python packages と導入処理: `setup.py:3270-3317`
- engine の更新条件と fallback: `setup.py:5184-5205, 5235-5323`
- 設定移行と draft vocabulary: `setup.py:6154-6159, 6657-6679, 7149-7188`
- wrapper の委譲とソース更新: `setup.sh:6-12, 76`; `START-HERE.bat:44-54`; `SETUP.bat:1-3`; `update.sh:9-17, 55-62`; `UPDATE.bat:11-20, 72-80`

同一 revision の CLI `--help` は実行していません。記載は parser 定義と処理経路を照合したソース調査に基づきます。Release 配布物の実体や各 OS 上での実行確認はこの調査では行っていません。
