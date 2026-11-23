# `--build`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `metal/setup_mac.py`（`setup.py` が Apple Silicon の通常 setup を委譲） |
| オプション | `--build` |
| 別名 | なし |
| 値 | なし。真偽フラグ。 |

## 役割

Apple Silicon の Metal エンジンを、現在の Strata checkout から改めてコンパイルします。通常の Mac setup でもエンジンが未作成またはソースに対して古ければビルドされますが、`--build` を付けると既存のビルド記録を削除して、記録上現行のエンジンも再ビルド対象にします。Mac 以外の `setup.py` parser にある `--build` の説明とは別スコープです。

## 使い方

```sh
# checkout のルートから、Metal エンジンを強制再ビルドして通常の setup を実行
./setup.sh --build

# エンジンを再ビルドし、モデルファイルは変更せずに更新処理を終える
./setup.sh --update --build

# エンジンを再ビルドして setup の設定ファイルと起動スクリプトを作り、サーバーは起動しない
./setup.sh --build --no-start
```

## 値と既定値

`argparse` の `store_true` として登録され、引数値は取りません。省略時は偽です。`setup.py` は通常の Mac 経路で引数を `metal/setup_mac.py` にそのまま渡します。Mac parser は `parse_known_args` を使い、認識しない引数は「not used on a Mac」と警告します。`--check` を併用した場合は Mac の検査結果を返した時点で終了するため、`--build` があってもビルドされません。

## 実行時の動作

`--build` が真なら `engine/metal/build-metal/BUILD.json` を削除してから `build_engine()` を呼びます。`build_engine()` はこの記録、実行ファイルの存在、Strata のソース version と対象ソース群の digest を使って現行性を判定するため、記録を削除したこの経路では既存エンジンがあっても通常の現行判定を通過しません。CMake を Ninja generator、Release 設定で構成し、Ninja で `strata` target をビルドします。成功すると同ディレクトリへ `BUILD.json` を書き、実行ファイルのパスを setup の後続処理へ渡します。

`--update --build` の場合はエンジン処理後に終了し、既存モデルと pack の有無を確認して不足を通知します。更新経路はモデルファイルをダウンロード・準備しません。`--build` 単独では残りの setup も続きます。既存のモデル shard が完了済みなら再利用し、画像対応が選択されていれば画像 encoder の確認・ビルド、モデル pack 等の準備、設定ファイルと起動スクリプトの書き込みを行います。`--no-start` がなければ最後にサーバーを起動します。

## 適用条件と副作用

- `terminal/setup.py` は macOS で、Strata Control installer 経路ではなく、Hy4-Flash / Inkling-2-Mini 専用経路でもない場合に `engine/metal/setup_mac.py` へ委譲します。この文書の parser はその Mac 経路のものです。機器・macOS 等の適合性検査で問題があれば通常は setup を停止します。
- `--build` を使うと `engine/metal/build-metal/BUILD.json` を削除し、必要に応じて `engine/metal/build-metal/` と `build.log` を作成または更新します。CMake と Ninja が利用できない場合、build 用 requirements から導入を試みます。Metal のヘッダーが checkout 内にない場合は Apple の URL から取得・検証して `engine/third_party/metal-cpp` に展開します。
- `--update` なしでは、ビルド後に通常 setup が続くため、モデル取得、モデル pack、設定ファイル `strata-<model>.json`、`run-<model>.sh` にも影響し得ます。`--update` はエンジン更新後にモデル状態を検査して終了します。`--no-start` は設定作成後のサーバー起動を抑止します。

## 出力とエラー

ビルド開始時に進捗を表示し、CMake と Ninja の stdout/stderr は `engine/metal/build-metal/build.log` にまとめられます。どちらかが失敗すると `S.fail()` がログの場所と対処ヒントを表示して終了コード 1 で停止します。CMake / Ninja の導入後も見つからない場合も終了コード 1 です。成功時はビルド済みエンジンの場所を表示します。

## 根拠

- `terminal/setup.py:9206-9210` — Mac setup の委譲先と、通常の CUDA / HIP 経路を使わないこと。
- `terminal/setup.py:11216-11219` — Mac で委譲する条件。Control、Hy4-Flash、Inkling-2-Mini の分岐を除外。
- `engine/metal/setup_mac.py:372-405` — Mac parser、`--build` の `store_true` 登録、未知引数の警告。
- `engine/metal/setup_mac.py:416-432` — 既定の起動経路を避ける条件と、Mac 検査・`--check` の早期終了。
- `engine/metal/setup_mac.py:109-126` — エンジンの現行判定とソース digest の対象。
- `engine/metal/setup_mac.py:129-153` — Metal 用 CMake / Ninja build、ログ、成功 stamp の作成、失敗経路。
- `engine/metal/setup_mac.py:475-495` — stamp 削除、エンジン呼び出し、`--update` 時のモデル不変更と終了。
- `engine/metal/setup_mac.py:497-523`, `525-566`, `593-621` — 通常 setup のモデル・pack 処理、設定と起動スクリプトの書き込み、`--no-start` と起動。
- `terminal/setup.py:1049-1056`, `6620-6632` — setup の終了コード 1 と build 用 CMake / Ninja の確認・導入。
- `engine/metal/setup_mac.py:85-100` — metal-cpp ヘッダーの取得・検証・展開。
