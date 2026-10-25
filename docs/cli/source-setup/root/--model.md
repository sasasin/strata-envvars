# `--model`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`SETUP.bat`、`update.sh`、`UPDATE.bat` からも委譲） |
| オプション | `--model` |
| 別名 | なし |
| 値 | parser が列挙するモデルサイズ名を1つ |

## 役割

setup するモデルサイズを明示します。通常の起動ではなく setup 選択経路に入り、選択した値は family と照合された後、モデルの取得・準備・設定に使われます（`setup.py:8603-8620`、`setup.py:8911-8960`）。

## 使い方

```sh
./setup.sh --family qwen --model IQ3_S --no-start
```

Linux の `setup.sh` は引数を `setup.py` に渡します。Windows の `START-HERE.bat` も引数を渡し、`SETUP.bat` と更新用 wrapper も setup CLI に委譲します（`setup.sh:6-13`、`setup.sh:76`、`START-HERE.bat:44-54`、`SETUP.bat:1-3`、`update.sh:62`、`UPDATE.bat:1-6`）。

## 値と既定値

Windows/Linux の通常 parser では、`--model` は `MODELS` のキーに加え、`PREVIEW_FAMILIES` と `MULTI_FILE_FAMILIES` に属する各 family の `models` キーも選択肢として受け付けます。重複値は除去されます（`setup.py:8425-8427`）。例えば通常モデルには `Q2_0`、`IQ2_XS`、`IQ3_XXS`、`IQ3_S`、family 固有モデルには `IQ1_M`、`UD-IQ4_XS`、`UD-Q4_K_XL`、`UD-Q6_K_XL`、`Q8_0`、`UD-Q8_K_XL` や DeepSeek の各 bpw 名があります。網羅的な現在値は `setup.py:406-460`、`setup.py:633-655`、`setup.py:735-777` の定義を参照してください。

値は必須、既定値は未指定（`None`）です。省略時は family や PC の状態に応じた推奨値が選ばれるか、対話メニューで選択します。指定値は family の選択を自動では行いません。family を指定しない場合も、通常経路では family メニューに進みます（`setup.py:8911-8931`、`setup.py:8952-8983`）。

選択肢外の値や値の欠落は `argparse` が usage error として拒否します。`MODELS` にない特別なモデル値には、対応 family の指定が必要です。該当 family を付けずに指定すると parser が `--family` の候補を示して停止します（`setup.py:8553-8556`）。通常 family 内に存在しないサイズも family 選択後に失敗します（`setup.py:8952-8960`）。

## 実行時の動作

既にインストール済みのモデルがあっても、`--model` を指定すると「通常起動のみ」の分岐を外れ、setup 選択へ進みます。値は選択した family のサイズ一覧と照合され、適合すればそのサイズを推奨値やメニュー選択の代わりに使います（`setup.py:8603-8620`、`setup.py:8677-8695`、`setup.py:8952-8983`）。

選択モデルに応じてファイル名・保存先タグが決まり、必要なモデルファイルの探索・ダウンロード・検証と準備に使われます。通常 family ではモデル shard を取得し、必要に応じて pack を作成します（`setup.py:9045-9049`、`setup.py:9205-9225`、`setup.py:9305-9325`、`setup.py:9341-9368`）。setup はモデル設定と `run-<model>.bat` / `run-<model>.sh` を作成し、`--no-start` がなければモデルを起動します（`setup.py:6154-6159`、`setup.py:7260-7272`、`setup.py:6740-6741`）。

`--model` は `--calibrate` とも使われ、既にインストールされた設定から対象モデルを絞ります。指定モデルが未インストールなら calibration 対象が見つからず失敗します（`setup.py:6433-6448`、`setup.py:8656-8662`）。

## 相互作用、適用条件、副作用

- `--family` と併用する場合、モデル名はその family に属している必要があります。非対応の組み合わせはエラーとなります（`setup.py:8914-8938`、`setup.py:8952-8960`）。
- `--yes` と明示的な `--model` の組み合わせは、メモリ不足など本来確認で停止するリスクを受け入れたものとして扱われる箇所があります。`--yes` だけでは同じ同意になりません（`setup.py:5851-5860`）。例えば必要 RAM を満たさない場合でも、選択モデルを続行する分岐があります（`setup.py:9004-9013`、`setup.py:9043-9045`、`setup.py:5863-5879`）。
- `--model` 自体はファイル取得・変換を実行する setup 経路を選び得ます。ファイルが未取得ならダウンロードし、形式に応じて pack の準備も行います。`--no-start` はインストール後の起動を抑えます（`setup.py:8603-8620`、`setup.py:9213-9325`、`setup.py:9341-9368`）。
- macOS の通常 setup は `setup.py` の parser より先に `metal/setup_mac.py` へ委譲され、そちらでは `MAC_MODELS` のキーが選択肢です（`setup.py:8418-8419`、`metal/setup_mac.py:327-334`）。macOS Control setup は `setup.py` parser を通りますが、利用可能なモデルを別途絞り込みます（`setup.py:8561-8563`、`setup.py:8261-8279`）。

## 出力と失敗経路

parser の値エラーは標準の `argparse` usage error です。family とモデルの不一致、未インストールモデルへの calibration、必要なディスク空き容量不足などは setup 内の `fail()` 経由で理由を表示して停止します（`setup.py:825-830`、`setup.py:8553-8556`、`setup.py:8952-8960`、`setup.py:8020-8023`、`setup.py:8656-8662`）。メモリなどのリスクは条件に応じて警告と確認を出し、明示的なモデル指定と `--yes` がある場合は確認を省いて続行することがあります（`setup.py:5851-5860`）。

## 調査範囲

同一 revision の parser、モデル定義、setup 分岐、取得・準備・起動関連の処理を確認しました。`--help` の実行、OS ごとの実機 setup、ダウンロード、モデル起動は行っていません。macOS は独自 parser または Control setup のソース上の条件まで確認し、実機動作は確認していません。

## 根拠

- Parser の choices と特別 family 検証: `setup.py:8420-8427`、`setup.py:8553-8556`
- モデル・family 定義: `setup.py:406-460`、`setup.py:568-619`、`setup.py:633-655`、`setup.py:735-777`
- 通常起動と setup 分岐、family 内選択: `setup.py:8603-8620`、`setup.py:8677-8695`、`setup.py:8911-8960`
- 明示指定時のリスク同意: `setup.py:5851-5879`、`setup.py:9004-9013`、`setup.py:9043-9045`
- モデルファイル取得・検証・準備: `setup.py:9205-9225`、`setup.py:9305-9325`、`setup.py:9341-9368`
- 設定・起動スクリプトと calibration: `setup.py:6154-6159`、`setup.py:6433-6448`、`setup.py:6740-6741`、`setup.py:7260-7272`、`setup.py:8656-8662`
- macOS の適用条件と wrapper 委譲: `setup.py:8418-8419`、`setup.py:8236-8279`、`metal/setup_mac.py:327-334`、`setup.sh:6-13`、`START-HERE.bat:44-54`
