# `setup.sh --no-browser`（macOS / Metal）

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `./setup.sh`（macOS Apple Silicon では `engine/metal/setup_mac.py` に委譲） |
| オプション | `--no-browser` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

モデルのセットアップや起動時に、準備完了後のチャットページ自動表示を止めます。API を使うハーネスやアプリから利用する場合などに使えます。macOS の通常経路では `setup.py` が Apple Silicon の処理を `engine/metal/setup_mac.py` に渡し、その parser がこのフラグを受け取ります（`terminal/setup.py:11218-11220`、`engine/metal/setup_mac.py:372-385`）。

## 使い方

```sh
# macOS の Metal セットアップを行い、ブラウザーを開かずにモデルを起動
./setup.sh --no-browser

# セットアップ内容を保存するが、この実行ではモデルを起動しない
./setup.sh --no-browser --no-start
```

## 値と既定値

`--no-browser` は `argparse` の `store_false`、保存先 `browser`、既定値 `None` のフラグです。値は指定しません。未指定時は `None` のままなので、ブラウザーを明示的に止めず、通常の起動ではチャットページを開く経路になります。値の範囲検証はありません（`engine/metal/setup_mac.py:375-385`）。

## 実行時の動作

新しいセットアップ経路では、指定すると `a.browser` が `False` になり、生成する `strata-<model>.json` に `"open_browser": false` を保存します。続けて生成する `run-<model>.sh` にはサーバーの `--open` を付けません。`--no-start` を併用した場合も設定と起動スクリプトは書かれ、当該実行でサーバーを開始する段階だけが省略されます（`engine/metal/setup_mac.py:608-621`、`terminal/setup.py:9149-9162`）。

既にインストール済みの Metal 設定を通常起動する場合も、フラグを渡すと `start()` に `False` が渡り、サーバー起動引数に `--open` が追加されません。フラグなしで通常起動する場合は `True` が渡ります（`engine/metal/setup_mac.py:416-418`、`engine/metal/setup_mac.py:311-332`）。サーバー側は `--open` が指定され、かつ設定の `open_browser` が `false` でない場合にだけブラウザー起動処理を行います（`terminal/serve/server.py:9207-9212`）。

この文書の scope である macOS 委譲先 parser には `--browser` の登録がありません。未知の引数は `parse_known_args()` で受け取り、「not used on a Mac」と警告されるため、`--browser` で `--no-browser` を取り消すことはできません（`engine/metal/setup_mac.py:375-405`）。`terminal/setup.py` 自体には `--browser` がありますが、通常の macOS 経路はその parser より前に委譲されます（`terminal/setup.py:11218-11220`、`terminal/setup.py:11287-11291`）。

## 適用条件と副作用

- 適用対象は `terminal/setup.py` が macOS かつ Control モードでなく、Hy4 または Inkling の専用経路でもない場合の Metal セットアップです。通常の Intel / AMD / Linux / Windows 経路の同名フラグとは別 scope です（`terminal/setup.py:11216-11220`）。
- 新しい設定では `open_browser: false` が設定ファイルへ記録され、後続の `./setup.sh` 起動でもブラウザーを開かない設定として残ります。生成される `run-<model>.sh` も `--open` なしになります（`engine/metal/setup_mac.py:608-612`、`terminal/setup.py:9149-9162`）。
- このフラグ自体はブラウザーを閉じたり、サーバーの起動・待受を止めたりしません。サーバーは通常どおり起動し、指定ポートで API とページを提供します（起動コマンド生成: `engine/metal/setup_mac.py:324-332`）。
- `--no-start` を併用するとサーバー起動を行わず終了しますが、設定と起動スクリプトの書き込みはその前に行われます（`engine/metal/setup_mac.py:610-621`）。

## 出力とエラー

このフラグ固有の成功メッセージやエラー経路はありません。未知の引数は警告に出力され、セットアップ処理は続行します（`engine/metal/setup_mac.py:403-405`）。起動時には設定が参照する実行ファイルや GGUF が欠けている場合、またはモデル再パックが実行中の場合に `S.fail()` でサーバーを開始せず失敗します。開始できた場合は `serve/server.py` の終了コードが `start()` から呼び出し元へ返されます（`engine/metal/setup_mac.py:311-332`）。

## 根拠

- `terminal/setup.py:11216-11220` — macOS で Metal setup へ委譲する条件と引数転送。
- `engine/metal/setup_mac.py:375-405` — macOS parser のフラグ定義、既定値、未知引数の警告。
- `engine/metal/setup_mac.py:416-418`、`608-621` — 既存設定起動、新規設定への保存、起動スクリプト生成、`--no-start` と起動呼び出し。
- `engine/metal/setup_mac.py:311-332`、`terminal/setup.py:9149-9162` — 設定を使ったサーバー起動と `--open` の有無。
- `terminal/serve/server.py:9207-9212` — サーバー側のブラウザー起動条件。
