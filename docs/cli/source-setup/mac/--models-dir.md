# `--models-dir`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | macOS の `setup.py` / `setup.sh`（Apple Silicon では `engine/metal/setup_mac.py` に委譲） |
| オプション | `--models-dir` |
| 別名 | なし |
| 値 | パス文字列（位置引数1つ。専用の型変換・形式検証なし） |

## 役割

Apple Silicon 向け Metal セットアップで、モデル GGUF shard の格納先を指定する。指定先の下には選択モデルの tag ディレクトリが作られ、その中に shard が置かれる。既定の models root はデータフォルダー内の `models/`。

## 使い方

Mac の Strata checkout でセットアップする例:

```sh
./setup.sh --setup --models-dir /Volumes/ModelDisk/Strata-models
```

通常起動できる既存構成がある場合、`--models-dir` 単独ではセットアップ経路に入らず既存サーバーを起動する。モデルをセットアップし直す場合は `--setup` または `--model` など、セットアップ経路に入る引数も指定する。

## 値と既定値

parser は値を文字列として受け取るだけで、存在確認、絶対パス化、`~` の展開、空文字の拒否は行わない。相対パスはプロセスの作業ディレクトリ基準で `Path` に変換される。値が省略された場合、または空文字の場合は `<data folder>/models` が使われる。短縮別名はない。

## 実行時の動作

- macOS で通常の `setup.py` を実行すると、`terminal/setup.py` は引数列を変更せず `engine/metal/setup_mac.py` に渡す。Mac 側 parser が `--models-dir` を受理し、指定値を `models_root` にする。
- shard の保存先は `--gguf-dir` があればそのディレクトリ、なければ `<models_root>/<family tag + model>`。ディレクトリを再帰作成してから shard を取得・検証する。完了済み shard は再利用される。
- vision を有効にした場合、画像 encoder は `<models_root>/<encoder filename>` に置かれる。`--gguf-dir` は shard のみを別置きし、画像 encoder の保存先を変更しない。
- `data_folder_for()` が扱う `--data-dir` はデータフォルダーを設定し、pack、MTP などの保管先に関係する別の指定である。`--models-dir` はそれらを移動・変更せず、モデル GGUF と画像 encoder の root を指定する。
- 既存モデル構成があり、`--setup` / `--model` / `--check` / `--no-start` / `--update` / `--build` のいずれもない場合は、通常起動へ早期 return する。この経路では `models_root` は計算されても利用されない。
- `--update` 経路では指定先を使って shard の存在を確認するが、モデルファイル自体はダウンロードしない。不足時は警告して再セットアップを案内する。

## 適用条件と副作用

この parser は macOS のセットアップ委譲先にあるため、ここで確認した挙動の対象は Apple Silicon / Metal のセットアップ経路である。セットアップがモデル取得段階まで進むと、指定したモデルディレクトリを作成し、その中にネットワークから shard をダウンロードする。既存の有効な shard は再利用し、全 shard の GGUF 完全性を確認する。

モデル準備用 pack は `data` 配下、GGUF shard の隣ではなく別の保存先に作られる。通常起動時にはこの option による保存先の切り替えは適用されない。

## 出力とエラー

この option 専用の validation message はない。指定先の作成は `Path.mkdir(parents=True, exist_ok=True)` で行われるため、作成不能などの `OSError` はこの箇所では捕捉されず、スクリプト末尾でも `KeyboardInterrupt` 以外を捕捉しない。ダウンロード失敗は共通 helper がエラーを表示して終了コード1で停止する。shard の欠落・破損・短いファイルも同 helper の `fail()` 経由で停止する。

## 根拠

- parser 定義、余剰引数の扱い、data root との合成、既存構成での早期起動: `engine/metal/setup_mac.py:372-418`
- `--gguf-dir` との優先関係、update 時の確認、shard directory 作成と download/validation: `engine/metal/setup_mac.py:462-513`
- vision encoder の保存先: `engine/metal/setup_mac.py:515-523`
- 指定 shard を含む起動設定への反映: `engine/metal/setup_mac.py:593-612`
- macOS の委譲と引数転送: `terminal/setup.py:9205-9210`, `terminal/setup.py:11198-11219`
- データフォルダーと `--data-dir` の処理: `terminal/setup.py:7335-7432`
- download 失敗の終了処理: `terminal/setup.py:1049-1056`, `terminal/setup.py:3471-3538`
- GGUF shard の欠落・破損・長さ検証: `terminal/setup.py:4171-4198`
