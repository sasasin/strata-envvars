# `--data-dir`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `metal/setup_mac.py`（`setup.py` から Apple Silicon の Mac 向け処理として委譲） |
| オプション | `--data-dir` |
| 別名 | なし |
| 値 | データフォルダーのパス（文字列）。指定先は絶対パスで、書き込み可能なフォルダーである必要がある |

## 役割

モデルファイル、準備済み pack、MTP データなどを置くデータフォルダーを指定する。Mac 用 setup はこの場所を新規ダウンロードと生成物の配置先に使い、既存の Strata フォルダーなどにあるデータは同じ場所として扱える場合に限り、別途確認または `--move-data` の指定に従って移動する。GGUF ファイルを別の場所に置く用途は `--models-dir` または `--gguf-dir` の担当であり、`--data-dir` はそれらの代替ではない。

## 使い方

```sh
# 新しい場所をデータ先に指定して Mac 用セットアップを実施（既存データは自動では移動しない）
./setup.sh --setup --yes --no-start --data-dir /Volumes/Work/Strata-data

# 既存モデルデータも新しい場所へ移す。移動できないデータは元の場所に残る場合がある
./setup.sh --setup --yes --no-start --data-dir /Volumes/Work/Strata-data --move-data
```

## 値と既定値

Mac parser は `--data-dir` を値付き引数として受理し、個別の型変換・選択肢制限は設けていない（`engine/metal/setup_mac.py:386-388`）。共有処理は指定値を `expanduser()` と `resolve()` で解決し、空値または未指定なら設定に記録されたデータフォルダーを使う。記録がなければ Strata フォルダーの隣にある `Strata-data` が既定先となる（`terminal/setup.py:7339-7348`）。

指定先は絶対パスであること、システムフォルダーではないこと、既存ならディレクトリーかつ書き込み可能であること、未作成なら親ディレクトリーまで存在し書き込み可能であることを検査する。相対パス、ファイル、使用不能な場所などは拒否される。検査後、指定先の作成を試みる。作成に失敗すると警告を出し、データ先を Strata の実行フォルダーに切り替える（`terminal/strata_control/folders.py:77-110`、`terminal/setup.py:7344-7356`）。

## 実行時の動作

Mac parser が得た値は `S.data_folder_for(a)` から共通の `data_folder()` に渡される（`engine/metal/setup_mac.py:412-414`、`terminal/setup.py:7429-7432`）。移動確認時に `--yes` がない場合、同一ドライブ上に既存データが見つかると「そのまま残す」か「移動する」かを尋ねる。`--yes` がある場合の既定は既存データを残して新しいダウンロードだけを指定先へ置くこと。`--move-data` はこの確認を省いて移動を選ぶ。既存データが一つもなければ、新しい場所が記憶先になる（`terminal/setup.py:7373-7409`）。

別のデータ先を指定して既存データを残す場合、`--set-default-data-dir` も同時指定されていなければ設定上の記憶先は変更されない。`--set-default-data-dir` を加えると、移動せずに指定先を記憶する（`terminal/setup.py:7338-7342`、`terminal/setup.py:7398-7404`）。データを移動する場合は `models` 配下をファイル単位でマージし、`packs` と `mtp` は移動先に同名の項目がないときに移動する。設定ファイル内のパスも、ファイルが移動先にあり元の場所にはない場合に更新する。移動先の同名ファイルは保持され、移動できなかったファイルも元に残り得る（`terminal/setup.py:7405-7422`、`terminal/setup.py:7265-7307`）。

Mac setup は戻り値のデータ先と、移動後もデータが残る場所を探索対象にする。モデル GGUF は通常 `<data-dir>/models/<モデル>` にダウンロードされ、pack、Metal 用生成物、MTP もデータ先の下に置かれる。`--models-dir` を指定すると GGUF の配置だけが別になります（`engine/metal/setup_mac.py:412-414`、`engine/metal/setup_mac.py:486-500`、`engine/metal/setup_mac.py:517-567`）。

## 適用条件と副作用

- この文書のスコープは `source-setup/mac`。トップレベル `setup.py` は macOS で通常の Metal setup を起動すると `engine/metal/setup_mac.py` に引数を渡す（`terminal/setup.py:9207-9211`、`terminal/setup.py:11218-11219`）。
- パス検証後に指定フォルダーを作成し、条件に応じて既存の `models`、`packs`、`mtp` を移動し、設定ファイルとアプリ設定のデータ先を変更する。`--data-dir` だけでは既存ファイルを移動しない。
- `--move-data` と `--set-default-data-dir` は `--data-dir` と組み合わせる補助オプション。`--move-data` が有効なら同じドライブの既存データを移動する。別ドライブのデータは移動せず、既存場所を探索対象に残す（`terminal/setup.py:7391-7424`）。
- `--models-dir` は GGUF の保存先を別途変更し、`--gguf-dir` は既存 GGUF の利用先を指定する。`--data-dir` と併用可能で、それぞれデータ一式の保存先、GGUF の保存先／入力先として別々に使われる（`engine/metal/setup_mac.py:414`、`engine/metal/setup_mac.py:486-500`）。

## 出力とエラー

指定パスが無効な場合、共通 `fail()` が理由と案内を表示し、setup を終了コード `1` で停止する。指定パスの検証失敗については「何もダウンロード・変更しておらず、データ先として保存していない」と案内される（`terminal/strata_control/folders.py:83-108`、`terminal/setup.py:7344-7347`、`terminal/setup.py:1049-1057`）。

データ先フォルダーを作成できない場合は警告を出して実行フォルダーへフォールバックする。設定ファイルの保存に失敗した場合も警告を出すが、`save_settings()` 自体はその場で終了しない（`terminal/setup.py:7352-7356`、`terminal/setup.py:7215-7223`）。セットアップ全体の後続失敗や終了コードは別のエラー経路に依存するため、このオプション固有の結果としては特定できない。

## 根拠

- `engine/metal/setup_mac.py:386-388` — Mac parser 定義と `--move-data`、`--set-default-data-dir` の関係。
- `terminal/setup.py:7338-7424` — 既定先、検証後の処理、移動・記憶条件、残存フォルダーの扱い。
- `terminal/setup.py:7429-7432` — Mac parser の引数から共通データフォルダー処理への引き渡し。
- `terminal/strata_control/folders.py:77-120` — パスの有効条件と拒否理由。
- `terminal/setup.py:7265-7307`、`terminal/setup.py:7208-7223` — ファイル移動、設定内パス更新、設定保存。
- `engine/metal/setup_mac.py:412-414`、`engine/metal/setup_mac.py:486-567` — Mac setup におけるデータ先の探索、GGUF・pack・生成物の利用。
- `terminal/setup.py:9207-9211`、`terminal/setup.py:11218-11219` — `setup.py` から Mac 用 setup への委譲。
