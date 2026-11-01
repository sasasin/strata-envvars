# `--set-default-data-dir`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.sh` → `setup.py` → macOS Apple Silicon では `metal/setup_mac.py` |
| オプション | `--set-default-data-dir` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

`--data-dir` で選んだ新しいデータフォルダーを、既存モデルファイルをその場所へ移動せずに今後の既定フォルダーとして記憶します。parser の説明も「`--data-dir` と併用し、移動せず新しいフォルダーを記憶する」としています（`metal/setup_mac.py:339-342`）。

## 使い方

Strata checkout のディレクトリで、例の保存先を既定にし、既存データを移動せず、setup 完了後にサーバーを起動しない例です。

```sh
./setup.sh --setup --data-dir ~/Strata-data --set-default-data-dir --yes --no-start
```

`--set-default-data-dir` 自体は `--data-dir` がなくても parser に拒否されませんが、その場合は新しいパスを指定しないため、このフラグによる別の保存先選択は起きません（parser は `metal/setup_mac.py:339-342`、引数から共通処理への受け渡しは `setup.py:6472-6475`）。

## 値と既定値

- 値は不要で、指定時は真、未指定時は偽です。型・`choices`・数値範囲はありません。重複指定されても同じ真値です（`metal/setup_mac.py:341`）。
- 単独では新しい保存先を選びません。`--data-dir` を省略したとき、共通処理は設定済みの `data_dir`、未設定なら checkout の親の `Strata-data` を宛先に使います（`setup.py:6387-6389,6472-6475`; Mac では `home()` が checkout のルートです: `setup.py:86-88`）。
- `--data-dir` の値は共通処理で `expanduser()` と `resolve()` を通します。相対パスも絶対パスに解決されます。指定先が無効なら失敗し、既存先は書き込み可能なディレクトリであること、未作成先は最寄りの既存親から作成可能であることなどを検査します（`setup.py:6389-6393`; `strata_control/folders.py:63-100`）。

## 実行時の動作

Mac parser は `S.data_folder_for(a)` をモデル選択や通常の setup 手順より先に呼びます。この処理はデータフォルダーを選び、既存モデルデータの場所を調べます（`metal/setup_mac.py:356-367`; 共通処理 `setup.py:6378-6389,6472-6475`）。

- `--data-dir` が現在の記憶先と異なり、他の場所に既存データがある場合、既定動作はデータを移動せず、新しいダウンロード先だけを変えることです。`--set-default-data-dir` を付けると、この保持分岐で `data_dir` として新しい宛先を設定へ保存してから戻ります（`setup.py:6410-6432`）。
- Mac parser の `--yes` は既定 false です。既存データをどうするかの質問が必要な場合、`--yes` なしなら対話で選び、`--yes` ありなら移動せず保持する側になります。保持したまま既定先も変更したい場合は `--set-default-data-dir` を併用します（`metal/setup_mac.py:340-344`; `setup.py:6417-6432`）。
- `--move-data` を併用すると保持分岐ではなく移動処理へ進みます。`--set-default-data-dir` は移動を抑止しません。移動処理では同じドライブ上の `models/`、`packs/`、`mtp/` などを宛先へ移し、必要なモデル設定のパスも更新します。別ドライブ上のデータは大容量コピーを避けて元の場所に残ります（`setup.py:6381-6386,6410-6469`）。
- 既存データが他の場所にない場合は、共通処理が新しい宛先を既定にし、最後に設定を保存します。この経路でもフラグ固有の別処理はありません（`setup.py:6433-6434,6466-6469`）。
- 保存先は `data_dir` 設定へ保存されます。通常の Mac CLI では `~/.config/strata/settings.json`（`XDG_CONFIG_HOME` があればその下）で、`STRATA_SETTINGS_FILE` が設定されていればそのファイルを使います。値が変わったときは `data_dir_at` も記録されます（`setup.py:6235-6265`）。

## 適用条件と副作用

`setup.py` が Darwin 上で `STRATA_CONTROL_INSTALL=1` ではない場合に Mac 専用 parser へ全引数を渡します。shell wrapper は `setup.py` に引数をそのまま渡します（`setup.sh:76`; `setup.py:82,7703-7707,9062-9069`）。Control install mode はこの委譲経路の対象外です。

指定先が妥当なら、ディレクトリ作成とユーザー設定ファイルの更新が起きます。既存データを保持する場合、モデル関連ファイルの移動は行いません。`--move-data` や、既存データのない場合の通常移行分岐は別です（`setup.py:6398-6402,6410-6469`）。

## 出力とエラー

- 指定したフォルダーが不正なら、`S.fail()` が理由と案内を表示し、終了コード 1 で停止します（`setup.py:6390-6393,904-909`; 検査条件は `strata_control/folders.py:63-100`）。
- ディレクトリ作成に失敗した場合は警告を出し、checkout の `home()` を使って続行します（`setup.py:6398-6402`）。設定ファイルの親ディレクトリ作成または書き込みで `OSError` が起きた場合は警告して続行します（`setup.py:6258-6265`）。
- 既存ファイルを保持する経路では、ファイルが元の場所に残り、新規ダウンロードが指定先に行く旨を表示します（`setup.py:6427-6432`）。

## 根拠

- Mac parser、真偽値、Mac setup から共通処理への適用: `metal/setup_mac.py:339-367`。
- Darwin での Mac 実装への引数委譲と `setup.sh` の引数転送: `setup.py:7703-7707,9062-9069`; `setup.sh:76`。
- `--data-dir` の解決、保持・移動分岐、既定保存先、設定保存: `setup.py:6235-6265,6378-6475`。
- パス検証: `strata_control/folders.py:63-100`。

## 調査範囲

調査対象は上記 SHA のソースです。`git status --short --branch` は `## main...origin/main`（working tree clean）でした。CLI `--help` や Mac 実機での実行、ファイルシステム依存の失敗挙動は確認していません。記述は parser と共通処理の静的確認に基づきます。
