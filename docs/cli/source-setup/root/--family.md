# `--family`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`SETUP.bat`、`update.sh`、`UPDATE.bat` からも委譲） |
| オプション | `--family` |
| 別名 | なし |
| 値 | family ID を1つ指定。通常の Windows/Linux setup では `qwen`、`swift`、`coder`、`unsloth`、`gyro`、`nvfp4`、`qwen36`、`deepseek41` |

## 役割

インストールまたは設定変更時に対象モデルのファミリーを選びます。ファミリーはモデルファイルの出所・形式や、その後に使う準備・engine 経路を選ぶ識別子です。値を省略した場合は通常 setup のモデル選択メニューで選びます（`setup.py:8911-8937`）。

## 使い方

```sh
./setup.sh --family swift --model IQ3_XXS --no-start
```

Linux では `setup.sh` が引数を `setup.py` に渡します。Windows の `START-HERE.bat` も同様に全引数を渡し、`SETUP.bat` は `--setup` を付けて `START-HERE.bat` を呼びます（`setup.sh:9-13`、`START-HERE.bat:44-54`、`SETUP.bat:1-3`）。更新 wrapper も引数を setup に渡します（`update.sh:62`、`UPDATE.bat:1-6`）。

## 値と既定値

通常の Windows/Linux setup では `argparse` の `choices` が `FAMILIES`、`PREVIEW_FAMILIES`、`MULTI_FILE_FAMILIES` のキーを受け付けます。現在の値は `qwen`、`swift`、`coder`、`unsloth`、`gyro`、`nvfp4`、`qwen36`、`deepseek41` です。`PREVIEW_FAMILIES` は `OWN_PATH_FAMILIES` の別名で、ここでは `qwen36`、複数ファイル family は `deepseek41` です（`setup.py:568-619`、`setup.py:633-656`、`setup.py:735-777`、`setup.py:8420-8424`）。

値は必須で、既定値は未指定（`None`）です。同じオプションを複数回指定した場合、通常 parser は標準の `argparse` の単一値 action を使うため最後の値が残ります。未対応値や値の欠落は parser が usage error として拒否し、setup 本体には進みません（`setup.py:8420-8424`）。

`setup.py` 冒頭の説明は `qwen|swift` のみを例示していますが、現行 parser の choices と一致しません（`setup.py:23`、`setup.py:8421-8424`）。上記の値一覧は実際の parser 定義と family 辞書に基づきます。

## 実行時の動作

通常の Windows/Linux 経路では、family を指定すると `a.family` が明示的な setup 条件になります。インストール済みモデルの通常起動分岐を避け、モデル選択時に指定値を使います。続いて `qwen36` は `install_own_path`、`deepseek41` は `install_dsv41`、その他は `FAMILIES` の定義に基づく標準の family install 経路へ進みます（`setup.py:8603-8620`、`setup.py:8677-8682`、`setup.py:8911-8938`）。setup はモデル取得・準備・設定ファイルと run script の作成を行い、`--no-start` がなければ最後にモデルを起動します（`setup.py:8146-8158`）。

`--model` と併用すると、指定 family のモデル一覧からその値を選びます。対応しないモデル値は family ごとの選択肢を示すエラーになります。モデル値だけを指定する場合も、family が判明しない特別なモデルでは対応 family を指定するよう parser error になります（`setup.py:8553-8556`、`setup.py:8952-8960`）。

`--calibrate` と併用した場合は新規 setup の family 選択ではなく、既存設定のうち指定 family に一致するモデルを calibration 対象に絞ります。該当するインストールがなければ失敗します（`setup.py:6433-6442`、`setup.py:8656-8662`）。`--update` 経路は通常の setup 選択より先に処理されるため、その経路では `--family` によるモデル選択は行われません（`setup.py:8617-8620`）。

## 適用条件と副作用

- 通常の Windows/Linux setup で `nvfp4` を選び AMD HIP backend を使うと、HIP engine に NVFP4 kernel がないため停止します（`setup.py:8938-8942`）。
- macOS の通常（非 Control）setup は `setup.py` の parser より前に `metal/setup_mac.py` へ引数を渡します。この parser が受理する family は `qwen`、`unsloth`、`gyro` のみです。モデル指定がある場合、実際の family はモデル定義から決まり、指定 family が異なると警告してモデル側の family を使います（`setup.py:8418-8419`、`metal/setup_mac.py:327-331`、`metal/setup_mac.py:392-419`）。
- macOS の Control setup は `setup.py` parser を通りますが、family として `qwen` / `gyro` 以外を指定すると失敗します（`setup.py:8561-8563`、`setup.py:8261-8265`）。
- family 選択は実際のインストール経路に影響するため、モデルファイルのダウンロードや準備、設定・起動 script の書き込みを伴い得ます。起動を避ける場合は `--no-start` を併用します（`setup.py:8932-8938`、`setup.py:8146-8158`）。

## 出力とエラー

不正な値・値の欠落は `argparse` が usage とエラーを表示して終了します。setup 内の非対応条件は `fail()` が理由と任意の案内を表示し、終了コード1で停止します（`setup.py:825-830`）。たとえば macOS Control setup で対応外 family を指定した場合や、AMD HIP で NVFP4 を選んだ場合が該当します（`setup.py:8263-8265`、`setup.py:8939-8942`）。

## 調査範囲

同一 revision のソースを参照しました。`--help` は実行しておらず、説明文と parser の食い違いはソース上で確認しています。全 OS・backend の実機実行、ダウンロードや engine 起動の結果は調査していません。

## 根拠

- Parser と早期検証: `setup.py:8418-8424`、`setup.py:8553-8564`
- Family 定義: `setup.py:568-619`、`setup.py:633-656`、`setup.py:735-777`
- setup 起動判定と family 分岐: `setup.py:8603-8620`、`setup.py:8911-8945`
- Model 選択・設定書き込み・起動: `setup.py:8952-8960`、`setup.py:8146-8158`
- Calibration の family 絞り込み: `setup.py:6433-6442`、`setup.py:8656-8662`
- macOS Metal parser と family 解決: `metal/setup_mac.py:327-358`、`metal/setup_mac.py:392-419`
- Wrapper の引数委譲: `setup.sh:9-13`、`START-HERE.bat:44-54`、`SETUP.bat:1-3`、`update.sh:62`、`UPDATE.bat:1-6`
