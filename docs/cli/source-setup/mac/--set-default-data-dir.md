# `--set-default-data-dir`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `engine/metal/setup_mac.py`（`setup.sh` / `terminal/setup.py` から起動する Apple Silicon Mac 用 setup） |
| オプション | `--set-default-data-dir` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

`--data-dir` で指定した新しいモデル保存先に既存モデルを移動せず、今後の Strata のデータフォルダーとして記憶させます。既存ファイルを選んだ場所に残し、新規ダウンロード先だけを変えたい場合に使います。

## 使い方

```sh
./setup.sh --data-dir /Volumes/Models/Strata --set-default-data-dir --yes
```

絶対パスで新しい保存先を指定します。既存モデルの移動を行わず、確認質問には `--yes` の既定回答（保持）を使います。移動を指示する `--move-data` は付けません。

## 値と既定値

値を取らない `store_true` フラグで、未指定時は `False` です。Mac 用 parser は `--data-dir` と別々に登録しており、組み合わせを parser で必須にはしていません。説明上は `--data-dir` との併用が前提です。`--data-dir` がない場合、このフラグ単独では新しい場所を指定できません。

## 実行時の動作

Mac 用 parser が値を読み、`data_folder_for()` を介して共通の `data_folder()` に渡します。指定先が記憶済みの場所と異なり、既存モデルを含むフォルダーがあるとき、`--move-data` がなければそれらを移動せず、指定先を新規ダウンロード用に使います。この保持分岐で本フラグが有効なら、設定ファイルの `data_dir` を指定先に更新します。既存モデルの所在も返され、そのモデルは元の場所で引き続き参照されます。

既存モデルが同じドライブにあり、`--yes` がない場合は保持か移動かを質問します。`--yes` を付けると質問を省略して保持側になり、本フラグと併用すれば指定先を記憶します。`--move-data` を併用すると移動側の処理が行われ、モデルファイルや設定参照の移動後に指定先が保存されます。既存モデルが見つからない場合は新しい場所が自動的に既定場所になるため、本フラグによる追加の違いはありません。

## 適用条件と副作用

このオプションの parser は Apple Silicon Mac 用 `engine/metal/setup_mac.py` にあります。`terminal/setup.py` は通常の macOS 経路で同スクリプトへ引数をそのまま渡します。一方、Control モードや特定の別セットアップ経路は委譲条件から除外されるため、この parser を通りません。

`--data-dir` は `folders.problem()` により、絶対パスか、システム領域ではないか、既存なら書き込み可能なディレクトリかなどを確認されます。不正な指定は `fail()` に進み、設定保存の前に終了します。指定先ディレクトリの作成時に `OSError` が起きた場合は警告し、ホームディレクトリへフォールバックします。設定は Strata の `settings.json` に書かれ、書き込みに失敗すると警告されます。

## 出力とエラー

不正な `--data-dir` は理由と「何もダウンロード・変更されず、保存先として記憶されない」旨を表示して setup を終了コード `1` で停止します。ディレクトリ作成または設定ファイル書き込み時の `OSError` は警告として表示されます。通常の保持分岐では、既存モデルが元のフォルダーに残り、新しいダウンロードは指定先へ行く旨が表示されます。

## 根拠

- `engine/metal/setup_mac.py:372-405` — Mac parser。`--data-dir`、`--move-data`、本オプションを登録し、未知引数は警告する。
- `engine/metal/setup_mac.py:411-414` — `data_folder_for(a)` の呼び出しと、その結果をモデル保存先に用いる箇所。
- `terminal/setup.py:9205-9210` — Mac 用 setup への引数転送。
- `terminal/setup.py:11407-11413`, `11418` 以降 — macOS での委譲条件と、Control・特定 family 経路との分岐。
- `terminal/setup.py:7335-7343`, `7429-7432` — 引数を共通処理へ渡す経路、`--set-default-data-dir` が既定フォルダーを記憶する条件。
- `terminal/setup.py:7367-7392`, `7403-7426` — 既存モデルの保持・移動分岐、設定保存、ファイルや設定参照の移動。
- `terminal/strata_control/folders.py:77-113`, `120-124`; `terminal/setup.py:7348-7350`, `7355-7359`, `7215-7223`, `1049-1056` — 保存先 validation、作成失敗時の fallback、設定書き込み警告、validation error の出力と終了コード。
