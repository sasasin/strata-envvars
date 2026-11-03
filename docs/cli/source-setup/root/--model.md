# `setup.py --model`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat` 等からも呼び出される） |
| オプション | `--model` |
| 別名 | なし |
| 値 | parser が列挙する model ID。`--family` に応じて通常・preview・multi-file family の選択肢から選ぶ |

## 役割

setup で使うモデルサイズ／variant を指定します。省略すると通常の setup 経路では既存の導入サイズや推奨値を初期値として選択画面に進みます。指定するとその model ID が選択済みとして扱われ、モデルの適合性判定、取得・準備、生成する設定名などに使われます（`setup.py:10140-10171,10238-10240`）。

## 使い方

```sh
./setup.sh --family qwen --model IQ3_XXS --yes --no-start
```

通常の Linux setup で Qwen family の `IQ3_XXS` を選択し、推奨を自動回答して、最後にモデルを起動せずに終了する例です。Windows は `START-HERE.bat` に同じ option を渡せます。`setup.sh` は `"$@"`、`START-HERE.bat` は `%*` を `setup.py` に渡します（`setup.sh:12`、`START-HERE.bat:48,53`。索引 [`README.md`](../../README.md) の `source-setup` scope）。

## 値と既定値

`--model` は値を1つ取ります。parser は `MODELS`、`PREVIEW_FAMILIES`、`MULTI_FILE_FAMILIES` の model ID を集めて重複を除いたものを `choices` にします。parser 上の既定値は未指定（`None`）です（`setup.py:9573-9575`）。

値は `model_alias()` を通してから選択肢と照合されます。DeepSeek の旧表記 `ISTA-DAS-<数値...>` は `IST-DAS-...` に正規化され、`ISTA-DAS-Coder` / `IST-DAS-Coder` は登録済み Coder ID に正規化されます（`setup.py:195-199`）。それ以外の未知値は argparse の choices エラーになります。

## 実行時の動作

- 通常の setup では `--model` があると、選択した `--family` の model 名一覧にその値があるか検証します。family に属さない値は候補を示して停止し、別 family で使える場合はその組み合わせも案内します（`setup.py:10140-10148`）。`--family` を省略した通常 family 経路では family を選択した後に同じ検査をします（`setup.py:10101-10119,10140-10148`）。
- 有効な model は選択画面を経ずに選ばれ、`MODELS[model]` を使った適合性・RAM/GPU 判定へ進みます（`setup.py:10149-10173`）。選択値は family tag と連結され、モデルファイルや pack、設定ファイルの対象を決めます（`setup.py:10238-10240,10532-10535`）。ファイルが揃っていない通常経路では後続処理が取得・検査・pack 準備を行います（`setup.py:10510-10515,10532-10567`）。
- `--model` はモデルを指定する明示的な setup 要求でもあります。既存導入があっても単純起動経路に入らず（`setup.py:9771-9777`）、通常 setup を選択します（`setup.py:9785-9789`）。`--calibrate` と併用すると導入ではなく、指定 model が既に入っているかを探して calibration 対象にします。該当する導入がなければ停止します（`setup.py:9821-9831`）。
- `--prepare-pack` と併用すると専用の pack 作成経路に入り、`--model` は `--gguf-dir` 内で対象 GGUF shard を探すために使われます。この経路では `--model` と `--gguf-dir` が必須で、`--family` 省略時は `qwen` です。モデル本体のダウンロードや engine 導入は行いません（`setup.py:9321-9349,9723-9724`）。

## 適用条件と副作用

値の候補が正しくても、指定した family にその model がなければ setup は停止します。`--yes` と合わせた場合、メモリ不足や未検証 backend などの risk 確認で、明示的に指定した `--model` が続行の意思表示として扱われる箇所があります（`setup.py:6354-6363,10184-10201,10231-10232`）。`--yes` 単独は同じ同意として扱われません。モデル適合性や不足メモリの判定そのものを無効化する option ではなく、警告・確認または停止条件はモデルと環境によって異なります。

通常の Apple Silicon で `setup.py` を実行すると、root parser に入る前に `metal/setup_mac.py` へ委譲されます（`setup.py:9560-9567`）。Mac 側 parser の `--model` は別 scope の [`source-setup/mac/--model.md`](../mac/--model.md) を参照してください。Strata Control の install mode はこの委譲を通らず、root parser を使います（`setup.py:82-83,9566-9568,9727-9730`）。

## 出力とエラー

未知の model ID は argparse の option/choices エラーになります。parser を通った後の family 不一致や必要ファイルの不備は `fail()` がメッセージと修正案を表示し、終了コード 1 で停止します（`setup.py:965-970,10142-10148`）。メモリ不足などの一部条件は警告後に確認し、拒否すると同じ `fail()` 経路になります（`setup.py:6354-6363`）。

## 根拠

- parser と choices: `setup.py:9560-9575`
- alias 正規化: `setup.py:195-199`
- family/model の照合と選択: `setup.py:10101-10119,10140-10173`; own-path family: `setup.py:8187-8207`; multi-file family: `setup.py:8934-8951`
- setup 要求判定・既存導入・calibration: `setup.py:9771-9789,9821-9831`
- risk の同意条件: `setup.py:6354-6382,10184-10201,10231-10232`
- 選択後のファイル確認・pack と設定対象: `setup.py:10510-10567`
- `--prepare-pack` との相互作用: `setup.py:9321-9349,9718-9724`
- Mac 委譲条件: `setup.py:82-83,9560-9567,9727-9730`

調査対象 checkout は `git status --short --branch` で `main` と `origin/main` が一致し、未コミット変更なしでした。Release 実行物や各 platform の実行は調査していません。値の全候補は parser の定義データから動的に構成されるため、本書では網羅表を複製していません。
