# `source-setup` `--set-default-data-dir`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `terminal/setup.py`（`setup.sh` / `START-HERE.bat` などから起動される setup） |
| オプション | `--set-default-data-dir` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる（既定値は偽）。 |

## 役割

`--data-dir` で選んだ新しいモデル保存先を、既存モデルを移動せずに Strata の記憶済みデータフォルダーとして保存するためのフラグです。既存モデルを旧フォルダーに残して新しいダウンロードだけを新フォルダーへ置く選択時に使います。`terminal/setup.py` の root parser が受理しますが、通常の Apple Silicon 用 Metal setup は引数を `terminal/engine/metal/setup_mac.py` に委譲し、別スコープの parser で処理します（`terminal/setup.py:9290-9294,11436-11437`、`terminal/engine/metal/setup_mac.py:388`）。

## 使い方

```bash
# 既存モデルをそのまま残し、以後のデータフォルダーを指定する
python terminal/setup.py --data-dir "$HOME/Strata-data" --set-default-data-dir
```

これは通常の setup の実行も続けます。新しいモデル保存先を指定し、既存ファイルを移動せずに処理する意図を示す例です。起動後のモデル設定・インストールなどは通常フローに従います。

## 値と既定値

- parser は `action="store_true"` で登録し、値は不要です。省略時は `False` です（`terminal/setup.py:11515-11516`）。
- 実際に記憶先を選ぶには `--data-dir PATH` も指定します。`data_folder_for()` は `data_dir`、`move_data`、`yes`、本フラグを `data_folder()` に渡します（`terminal/setup.py:7513-7516`）。
- PATH は本フラグの値ではなく `--data-dir` の値です。指定先は展開・解決され、存在するディレクトリーで書き込み可能か、または作成可能か検証されます。相対パス、システムフォルダー、ファイルを指すパス、書き込み不可などは拒否対象です（`terminal/setup.py:7430-7434`、`terminal/strata_control/folders.py:77-113`）。
- フラグを付けても `--data-dir` がなければ、記憶先をこのフラグによって変更する分岐には入りません（`terminal/setup.py:7451-7475`）。通常起動で既存モデルがあり、ほかのセットアップ条件もない場合は `data_folder_in_place()` が使われるため、このフラグによるフォルダー作成・移動・保存も行われません（`terminal/setup.py:11681-11688`）。

## 実行時の動作

`--data-dir` が現在の記憶先と異なる場合、Strata は既存のモデルデータを含むフォルダーを調べます。同一ドライブ上に既存データがあり、`--move-data` がなく、`--yes` もないときは「旧フォルダーに残す / 新フォルダーへ移す」を質問します。「残す」を選んだ場合、本フラグがあれば新フォルダーを `settings.json` の `data_dir` として保存して終了し、既存データは移動しません。`--yes` を指定した場合も移動は行わず、その既存データを旧フォルダーに残す経路に進み、本フラグがあれば新しい記憶先を保存します。別ドライブ上の既存データはその場で使われ、移動の質問は出ません（`terminal/setup.py:7451-7473,7482-7486`）。

`--move-data` を指定した場合は本フラグとは別の移動経路に進み、同一ドライブ上の既存モデルファイルを新しいフォルダーへ移動・統合し、設定ファイル内の移動済みパスを更新します。この経路では処理後に新しい `data_dir` が保存されるため、本フラグは記憶先の保存に追加の効果を与えません（`terminal/setup.py:7474-7509`）。既存モデルデータが見つからない場合も新しいフォルダーが既定先となり、通常の保存処理で記録されます（同 `terminal/setup.py:7474-7476,7507-7509`）。

保存先は Windows では `%APPDATA%/Strata/settings.json`、それ以外では `$XDG_CONFIG_HOME/strata/settings.json`（未設定時は `~/.config/strata/settings.json`）です。新しいデータフォルダーを保存すると `data_dir_at` も更新されます（`terminal/setup.py:7276-7305`）。

## 適用条件と副作用

- 対象は `terminal/setup.py` の root parser と、その値を `data_folder_for()` に渡す setup 経路です。通常の Apple Silicon 用 Metal setup は先に別 CLI へ委譲されます。Intel SYCL の checkout 用 setup も別 setup スクリプトへ引数を転送します（`terminal/setup.py:9290-9294,11628-11638`）。同名オプションの Metal 文書は [`mac scope`](../mac/--set-default-data-dir.md) を参照してください。
- `--data-dir` の指定先を作成することがあります。指定先の妥当性検査後に作成し、検査で問題があれば変更前に失敗します。作成時に OS エラーが起きた場合は警告を出し、`home()` を保存先として続行します（`terminal/setup.py:7431-7443`）。
- 本フラグ単独では既存モデルを移動しません。`--move-data` を付けると既存モデルの移動・統合、空になった `packs` フォルダーの削除、モデル設定内パスの更新が起き得ます（`terminal/setup.py:7487-7506`）。
- `settings.json` の書き込みに失敗した場合は警告を出して続行します。保存先設定が永続化されたことまでは保証されません（`terminal/setup.py:7299-7307`）。

## 出力とエラー

- 指定した `--data-dir` が不正な場合、Strata は「Nothing was downloaded or changed...」を含む説明を標準出力へ出し、終了コード 1 で停止します（`terminal/setup.py:7431-7434,1049-1056`）。
- 記憶済みフォルダーが利用不能な場合は警告し、既定の `Strata-data` へ戻して保存済み `data_dir` を破棄します（`terminal/setup.py:7435-7438`）。
- フォルダー作成や設定保存に失敗した場合は標準出力への警告であり、それ自体は `fail()` による停止経路ではありません（`terminal/setup.py:7440-7443,7299-7307`）。

## 根拠

- `terminal/setup.py:11510-11516` — `--data-dir`、`--move-data`、本オプションの parser 定義。
- `terminal/setup.py:7419-7516` — 保存先決定、既存データの保持・移動、記憶先の保存と CLI 引数の受け渡し。
- `terminal/setup.py:11681-11688` — 通常起動時に既存データフォルダーを読み取り専用で使う分岐。
- `terminal/setup.py:7276-7307` — settings ファイルの場所、ロード・保存、保存失敗時の警告。
- `terminal/strata_control/folders.py:77-113` — `--data-dir` で指定したフォルダーの検証条件。
- `terminal/setup.py:9290-9294,11436-11437`、`terminal/engine/metal/setup_mac.py:388` — 通常の Mac setup の委譲と、Metal 側に別 parser があること。
