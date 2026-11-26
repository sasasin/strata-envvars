# `setup.py --data-dir`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` などの入口からも同じ parser を使用） |
| オプション | `--data-dir` |
| 別名 | なし |
| 値 | データフォルダーのパス。parser は文字列を受け取り、実行時にユーザー領域へ展開して絶対パスに解決する。 |

## 役割

モデルのダウンロード先を含む Strata のデータフォルダーを指定します。未指定なら設定に保存されたフォルダー、保存値がなければ Strata フォルダーの隣の `Strata-data` が候補です。`--data-dir` で別の場所を指定しても既存データは自動では移動せず、新規ダウンロードだけを新しい場所へ置けます。既定では同じデータルートの `models/` が GGUF の配置先になり、pack や MTP データもこのルートを使います。GGUF のみ別の場所に置く場合は `--models-dir` を併用します。

## 使い方

```sh
# 新しいモデルのセットアップ先を指定する
./setup.sh --setup --family qwen --model IQ3_S --data-dir /mnt/models/Strata-data

# 既存ファイルは元の場所に残し、新しい場所を今後の既定先にもする
./setup.sh --setup --family qwen --model IQ3_S --data-dir /mnt/models/Strata-data --set-default-data-dir

# 既存データも新しいフォルダーへ移す（移動対象は同じドライブ上のデータ）
./setup.sh --setup --family qwen --model IQ3_S --data-dir /mnt/models/Strata-data --move-data
```

## 値と既定値

- parser には `type`、`choices`、明示的な既定値がありません。値を省略した場合は `None` となり、保存済みの `data_dir`、または Strata フォルダーの隣にある `Strata-data` が選ばれます（`terminal/setup.py:11510-11511`, `7419-7430`）。
- 指定値は `Path(...).expanduser().resolve()` で解決されます。その後、存在するフォルダーならディレクトリーかつ書き込み可能か、未作成なら作成元の親フォルダーが存在して書き込み可能かを確認します。システムフォルダー、ファイル、書き込み不可の場所などは拒否されます（`terminal/setup.py:7430-7434`; `terminal/strata_control/folders.py:77-113`）。
- 値の文字列形式や最大長を parser は制限しません。相対パスは実行時の作業ディレクトリーを基準に絶対パスへ解決されます（`terminal/setup.py:7430`）。

## 実行時の動作

- `data_folder_for()` が `--data-dir` と `--move-data`、`--yes`、`--set-default-data-dir` の値をまとめてデータフォルダー選択処理に渡します（`terminal/setup.py:7513-7516`）。通常の既存モデル起動だけなら `data_folder_in_place()` を使い、フォルダー作成・移動・設定保存をしません。ただし `--data-dir` があると単純起動判定から外れ、`data_folder_for()` の経路になります（`terminal/setup.py:11681-11690`）。
- 指定先が現在の既定先と異なり、既存モデルファイルが見つかった場合、`--move-data` がなければそれらは残り、新しいダウンロード先として指定先が使われます。同じドライブ上の既存データがあり、`--yes` もない場合は「keep / move」を尋ね、既定回答は `keep` です。`--yes` を付けた場合は質問を省略し、`--move-data` がなければ既存データを移しません（`terminal/setup.py:7451-7473`）。
- 移動する場合、同じドライブ上で `models/` の内容を統合し、移動先の同名ファイルを保持します。`packs/` の各項目と `mtp/` は移動先に同じ項目がない場合に移し、移動済みファイルを参照するモデル設定も更新します。使用中などで移せないファイルは元に残ります。別ドライブ上の既存データはコピーせず、その場所で引き続き利用する対象として扱われます（`terminal/setup.py:7349-7367`, `7482-7506`）。
- 指定先が選ばれ、既存データを残す場合、`--set-default-data-dir` を付けると移動せずに設定へ保存します。既存データがない場合または移動処理を進めた場合も、選択先を設定へ保存します。設定保存時、`data_dir` が変わると `data_dir_at` も更新されます（`terminal/setup.py:7471-7475`, `7507-7509`, `7299-7306`）。
- `--models-dir` を省略すると GGUF の場所は `<data-dir>/models` になります。明示した場合は GGUF の場所を別指定できますが、pack などデータルート下の生成先は `data-dir` 側を使います（`terminal/setup.py:11517`, `11687-11690`, `12305-12307`, `12328-12340`）。

## 適用条件と副作用

- `--data-dir` が指定され、フォルダーが妥当なら、選択処理でフォルダーを作成します。妥当性の確認では、既存フォルダーまたは未作成先の親に小さな一時ファイルを書いて削除し、書き込み可否を確かめます（`terminal/setup.py:7439-7443`; `terminal/strata_control/folders.py:63-74`, `95-110`）。
- 移動は同一ドライブのデータに限られ、既存の同名データが移動先にある場合は移動先を保持します。ファイル使用中などで移動できないデータは残り、警告されることがあります（`terminal/setup.py:7482-7506`; `7349-7367`）。
- `--data-dir` と `--move-data`、`--set-default-data-dir` は別の制御です。前者だけでは既存ファイルを動かさず、後二者はそれぞれ既存データの移動と、移動しない場合の既定先保存を指定します（`terminal/setup.py:11510-11516`, `7451-7475`）。

## 出力とエラー

- 明示したフォルダーが検査に失敗すると、フォルダーの問題と「何もダウンロード・変更されず、既定先にも保存されない」旨を出して停止します。`fail()` はエラーイベント（JSONL 出力時）を出し、終了コード 1 で終了します（`terminal/setup.py:7431-7434`, `1049-1056`）。
- 検査後のフォルダー作成で `OSError` が起きると警告し、データ先を `home()` に切り替えて続行します（`terminal/setup.py:7439-7443`）。設定ファイルの保存に失敗した場合も警告し、処理自体は続行します（`terminal/setup.py:7299-7306`）。

## 根拠

- `terminal/setup.py:11510-11517` — parser 登録と隣接する `--move-data`、`--set-default-data-dir`、`--models-dir` の定義。
- `terminal/setup.py:7419-7516` — パス選択、既存フォルダーの検出、対話・移動・保存、および引数との接続。
- `terminal/setup.py:11681-11690` — 通常起動とデータフォルダー選択処理の分岐、および `models/` の既定位置。
- `terminal/setup.py:7349-7382`, `7482-7509` — ファイル移動・統合、設定内パスの更新、保存。
- `terminal/strata_control/folders.py:63-113` — 書き込み確認とフォルダー検証。
- `terminal/setup.py:1049-1056` — 失敗時の表示、JSONL エラーイベント、終了コード。
