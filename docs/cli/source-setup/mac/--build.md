# `--build`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `metal/setup_mac.py`（macOS 用セットアップ。通常は `./setup.sh` 経由） |
| オプション | `--build` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は `False` |

## 役割

現在のソースに対応する Metal engine がすでにある場合も、engine の再ビルドを強制します。`--build` はビルド処理だけを実行する指定ではありません。`--update` と組み合わせると、engine のビルド後にモデル更新経路へ入り、モデルファイルを変更せずに終了します。

## 使い方

macOS の Strata checkout で、engine を再ビルドしてモデル更新経路で終了する例です。

```sh
./setup.sh --build --update
```

`setup.sh` は引数を `setup.py` に渡し、macOS かつ Control install でない場合、`setup.py` がそれらを `metal/setup_mac.py` に転送します（`setup.sh:6-12`、`setup.py:9068-9069`、`setup.py:7703-7707`）。

## 値と既定値

`argparse` の `store_true` フラグで、引数は不要、既定値は `False` です。複数回指定しても有効状態のままです（`metal/setup_mac.py:352`）。この parser は `parse_known_args` を使うため、未知の引数は parser error にせず、`not used on a Mac: ...` と警告して処理を続けます（`metal/setup_mac.py:356-358`）。

## 実行時の動作

`--build` が指定されると、engine のビルド判定 stamp `build-metal/BUILD.json` を削除してから `build_engine()` を呼びます。通常の再利用判定は、stamp 内のバージョンとソース digest が一致し、実行ファイルも存在するときに成立します。stamp を削除することでその判定を無効にし、`build-metal/` を使って CMake の Release 設定と Ninja の `strata` target を実行します。ビルド出力は `build-metal/build.log` に記録され、成功時は新しい `BUILD.json` が書かれます（`metal/setup_mac.py:106-112,126-150,428-434`）。

この分岐より前に Mac の状態確認、モデル選択等の対話、Python package の確認・導入、llama.cpp の取得確認が行われます。`--update` を付けない場合、ビルド後は通常のモデル取得・準備・設定ファイルと起動スクリプトの作成に進み、`--no-start` がなければ server も起動します（`metal/setup_mac.py:369-431,435-570`）。`--update` の場合は engine build 後にモデルの存在を確認して終了し、不足モデルはダウンロードせず警告を表示します（`metal/setup_mac.py:435-448`）。

## 適用条件と副作用

この scope は `setup.py` が macOS (`sys.platform == "darwin"`) で Control install (`STRATA_CONTROL_INSTALL=1`) ではない場合に使う `metal/setup_mac.py` の parser です。setup は Apple Silicon / Metal 用の経路として説明されています（`setup.py:82,9068-9069`、`metal/setup_mac.py:1-16`）。

`build-metal/BUILD.json` は存在すれば削除されます。engine が現在のソースに合っていても、CMake/Ninja によるローカルビルドを再実行します。ビルドログは `build-metal/build.log` に書き込まれます。ビルドツールが見つからない場合は requirements-build 由来の導入を試みます（`metal/setup_mac.py:131-149`、`setup.py:5760-5772`）。

`--build` 単独での実行は後続のモデル取得・準備も伴い得ます。再ビルド後にモデル処理を避けたい場合は `--update` を併用してください。ただし update 経路でも Mac 確認や選択、Python package 処理などビルド前のセットアップ処理は実行されます（`metal/setup_mac.py:373-448`）。

## 出力とエラー

CMake または Ninja が失敗すると、`build-metal/build.log` を参照するエラーと Command Line Tools の確認案内を表示してセットアップを終了コード `1` で停止します（`metal/setup_mac.py:140-146`、`setup.py:904-909`）。ビルドツール導入後に CMake / Ninja が見つからない場合も、修復方法を示して終了します（`setup.py:5760-5772`）。

## 根拠

- parser 定義・既定値: `metal/setup_mac.py:352`
- 未知引数の扱い: `metal/setup_mac.py:356-358`
- Mac parser への委譲: `setup.py:9068-9069,7703-7707`、`setup.sh:6-12`
- stamp の無効化とビルド呼び出し: `metal/setup_mac.py:428-434`
- stamp 判定、CMake/Ninja 実行、ログ、成功 stamp: `metal/setup_mac.py:106-150`
- `--update` および後続セットアップ: `metal/setup_mac.py:435-448,450-570`
- ビルドツールの導入・確認と失敗: `setup.py:5760-5772`
- エラー表示と終了コード: `setup.py:904-909`
