# `--update`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `metal/setup_mac.py`（Apple Silicon の macOS 用セットアップ。通常は `./setup.sh` 経由） |
| オプション | `--update` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は `False` |

## 役割

Mac 用セットアップを engine の確認・必要時 build まで進め、モデルファイルをダウンロード・再準備せずに終了するモードです。既存の Metal 設定があっても通常の server 起動に入らず、選択したモデルのファイルと pack が存在するかを確認します。

`--update` 自体は Git checkout を更新しません。`./update.sh` は先に `git pull --ff-only` を試してから `./setup.sh --update` を実行する wrapper です。一方、`./setup.sh --update` は現在の checkout のままセットアップ処理を行います（`update.sh:2-6,16-17,62`）。

## 使い方

Strata checkout のルートで Mac 用の更新経路を実行します。

```sh
./setup.sh --update
```

モデル選択などの質問に既定値で答える場合は `--yes` も指定できます。例ではモデルファイルを取得せず、選択モデルに対する engine と既存ファイルの確認後に終了します。

```sh
./setup.sh --update --yes
```

`setup.py` は macOS かつ `STRATA_CONTROL_INSTALL=1` でない場合、引数を `metal/setup_mac.py` にそのまま渡します。Control install はこの Mac parser の対象外です（`setup.sh:6-12`、`setup.py:82,9068-9069,7703-7707`）。

## 値と既定値

`argparse` の `store_true` フラグで、引数は不要、既定値は `False` です。複数回指定しても有効状態のままです（`metal/setup_mac.py:351`）。Mac parser は `parse_known_args` を使うため、未知の引数は `not used on a Mac: ...` と警告して続行します。無効な `--model` や `--vision` など、認識済み option の不正な値は argparse の選択肢検証で拒否されます（`metal/setup_mac.py:329-356`）。

## 実行時の動作

1. `--update` があると、既存の Metal 設定が見つかっても自動起動せず、Mac の確認へ進みます（`metal/setup_mac.py:369-371`）。
2. `--check` も同時に指定した場合は、Mac の状態確認後に `--check` の経路が先に終了します。engine の確認・build やモデル存在確認には進みません（`metal/setup_mac.py:373-385`）。
3. `--model` を指定しなければモデル選択を質問します。`--yes` を付けると推奨モデルが選ばれます。`--vision` を省略した場合も質問し、`--yes` では画像読み取りを有効にする既定回答が選ばれます。モデルに対して `--family` が異なる場合、モデル表から得た family を使い、指定 family は警告付きで採用されません（`metal/setup_mac.py:387-418`）。
4. Python package を必要に応じて導入し、llama.cpp の pinned source を確認・取得してから Metal engine を確認します。engine の再利用条件（実行ファイル、version stamp、source digest）が満たされなければ CMake/Ninja で build します。`--build` も指定した場合は先に stamp を削除するため、engine build を強制します（`metal/setup_mac.py:424-434,106-150`）。
5. 選択モデルの GGUF shard が存在して `.done` マークもあり、pack の `native_experts.txt` と `tokenizer/vocab.json` が存在するかを確認します。不足時は警告と `./setup.sh --setup` の案内を表示し、モデルファイルは取得せず終了コード `0` で戻ります。必要な画像 encoder が未取得の場合も警告を表示して終了します（`metal/setup_mac.py:435-448`）。
6. 必要ファイルが揃っている場合も、この分岐で終了します。通常セットアップ後半の shard download、repack/pack、MTP 準備、設定・起動 script の書き込み、server 起動には進みません（`metal/setup_mac.py:435-448,450-570`）。

## 適用条件と副作用

- この挙動は `sys.platform == "darwin"` かつ `STRATA_CONTROL_INSTALL` が `"1"` でないときに適用されます。`setup.py` の冒頭で同条件を判定し、Mac 用 parser に argv を渡します（`setup.py:82,9062-9069`）。
- `--update` だけでは `build-metal/BUILD.json` を削除しないため、現行ソースに一致する engine は再利用されます。`--build` との併用時は stamp が削除され、ローカル build が行われます。package 導入、llama.cpp source の取得、build が必要な場合は、それぞれのファイルや Python 環境に書き込みます（`metal/setup_mac.py:126-150,428-434`、`setup.py:3464-3495,3562-3585,5760-5772`）。
- `--update` の確認対象は、選択モデルの shard と pack です。shard は存在と `.done` のみを見て、pack は指定された2ファイルの存在を見ます。モデル内容の再検証や pack の再生成はこの経路では行いません。画像 encoder は選択が有効 (`yes`) のとき、`models_root` に mmproj が存在するかを確認します（`metal/setup_mac.py:435-447`、`.done` 判定の定義は `setup.py:1007-1009`）。
- モデル確認より前に `data_folder_for()` が実行されます。通常の既定先への整理でも、同じドライブにある既存モデル等をデータフォルダへ移動したり、設定を保存したりする場合があります。`--data-dir`、`--move-data`、`--set-default-data-dir` は移動・保存先の扱いにも影響します。したがって `--update` 分岐自体はモデルをダウンロード・再生成しませんが、実行全体でファイル移動がないとは限りません（`metal/setup_mac.py:364-367`、`setup.py:6381-6469,6472-6475`）。
- `--update` は選択・確認を省略する指定ではありません。`--model`、`--vision` 等を指定しなければ質問が発生します。更新コマンドとして wrapper の `./update.sh` を使う場合は、その wrapper が `git pull --ff-only` を実行する点も区別してください（`metal/setup_mac.py:387-405`、`update.sh:9-17,62`）。

## 出力とエラー

モデル shard または pack がない場合、`[!]` 警告と `./setup.sh --setup` の案内を標準出力へ表示し、終了コード `0` で戻ります。画像 encoder が未取得の場合も同様に警告します（`metal/setup_mac.py:435-448`、`setup.py:896-909`）。

この確認より前に、Mac の前提条件に問題がある場合や Python/engine の処理が失敗した場合は `S.fail()` が案内を表示して終了コード `1` で停止します。CMake/Ninja build の失敗では `build-metal/build.log` を案内します。argparse が認識する option の構文・値が不正なら parser error になります（`metal/setup_mac.py:373-385,140-146,351-356`、`setup.py:904-909`）。

## 根拠

- parser 定義、既定値、未知引数の警告: `metal/setup_mac.py:327-358`
- `setup.py` から Mac parser への委譲条件・argv 転送: `setup.py:82,7703-7707,9062-9069`; wrapper: `setup.sh:6-12`
- 既存設定による自動起動の抑止、`--check` の先行 return、モデル・vision 選択: `metal/setup_mac.py:369-418`
- Python package、llama.cpp、engine 確認と update 分岐: `metal/setup_mac.py:424-448`; engine 再利用・build: `metal/setup_mac.py:106-150`
- update 分岐後に続く通常の download、モデル準備、config 作成、起動: `metal/setup_mac.py:450-570`
- shard と pack の存在判定、未取得時メッセージ: `metal/setup_mac.py:435-447`; `.done` の定義: `setup.py:1007-1009`
- `data_folder_for()` とデータ移動・設定保存: `setup.py:6381-6469,6472-6475`
- wrapper `update.sh` の Git 更新と `--update` 転送: `update.sh:2-6,9-17,62`
- エラー表示と終了コード: `setup.py:900-909`; build 失敗: `metal/setup_mac.py:140-146`
- revision と作業状態: `git rev-parse HEAD` は上記 SHA、`git status --short --branch` は `## main...origin/main`（変更行なし）。
