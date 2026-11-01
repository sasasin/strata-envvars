# `--setup`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `metal/setup_mac.py`（`setup.py` から Apple Silicon の macOS で委譲） |
| オプション | `--setup` |
| 別名 | なし |
| 値 | なし。`store_true` のフラグ |

## 役割

保存済みの Mac 用設定があるとき、引数なしの `setup.py` が既存モデルをそのまま起動する通常経路を避け、セットアップ処理に進みます。新しいモデルの導入や設定変更を行うときに使います。単独でエンジンの再ビルドを強制するフラグではありません。

## 使い方

Strata checkout のルートで実行します。

```sh
./setup.sh --setup
```

すでに設定済みのモデルとは別のモデルを選ぶ例:

```sh
./setup.sh --setup --model q2_0
```

`--no-start` を併用すると、セットアップ後にサーバーを起動せず終了します。

## 値と既定値

値は取りません。`argparse` の `store_true` action により、省略時は `False`、指定時は `True` です。同じフラグを複数回指定しても真偽値のままです。parser は `parse_known_args()` を使い、他の未知引数は警告して無視しますが、これは `--setup` 自身の値規則ではありません（`metal/setup_mac.py:327-358`）。

## 実行時の動作

- macOS かつ `STRATA_CONTROL_INSTALL=1` ではない `setup.py` は、自身の PC 向け parser を通る前に argv を `metal/setup_mac.py` へ渡します。`setup.py` 経由ではその子プロセスが終了コードを返します（`setup.py:82,7703-7707,9068-9069`）。`setup.sh` はルートの `setup.py` を起動します（`setup.sh:7-13,39-50`）。
- Mac 用 parser で `--setup` が真になると、既存設定がある場合でも、その設定を即時起動する分岐を通りません。この分岐は既存設定があり、かつ `--setup`、`--model`、`--check`、`--no-start`、`--update`、`--build` のいずれも指定されない場合だけ既存設定を起動します（`metal/setup_mac.py:348-352,369-371`）。
- セットアップ経路では Mac の状態確認とモデル選択に進みます。`--model` がなければ選択画面を出し、モデルファイルを取得・検証し、必要な準備を行って、`strata-<model>.json` と起動スクリプトを書きます（`metal/setup_mac.py:373-405,450-475,476-540,542-562`）。既にあるステップはスキップされる方針が同ファイルの説明にあります（`metal/setup_mac.py:1-16`）。
- `--setup` は再ビルド指定ではありません。エンジンの再ビルド用 option は別の `--build` で、実装ではそれが真のとき既存 `BUILD.json` を削除してから `build_engine()` を呼びます（`metal/setup_mac.py:352,428-435`）。
- セットアップが完了すると、`--no-start` がなければ生成した設定でサーバーを起動します。`--no-start` 指定時は設定と起動スクリプトを書いた後、終了コード 0 で戻ります（`metal/setup_mac.py:559-570`）。

## 適用条件と副作用

この option の個別 parser は Apple Silicon 用 `metal/setup_mac.py` にあります。`setup.py` からは Darwin かつ `STRATA_CONTROL_INSTALL` が `1` でない場合に委譲されます。Control install mode はこの委譲条件から外れます（`setup.py:82,9068-9069`）。索引上も `setup.py` の共通 parser とは別の `mac/` scope です（`docs/cli/README.md:1594-1618`）。

セットアップ経路では Python package の導入、Metal engine の準備、モデル・画像 encoder 等のダウンロード、モデル pack 作成、設定ファイルと起動スクリプトの書き込みが起こり得ます。具体的な処理はモデル、既存ファイル、`--vision` などの指定により異なります（`metal/setup_mac.py:424-475,476-540,542-562`）。未指定時に既存モデルを起動するだけの通常経路と異なり、処理後は既定でサーバーも起動します。

同じスコープの `--check` は Mac 検査後に終了し、`--update` はエンジン準備後にモデルファイルを更新せず終了します。これらを併用した場合もそれぞれの早期終了分岐に入るため、`--setup` が通常のモデル取得・準備を強制するわけではありません（`metal/setup_mac.py:348-352,369-383,428-448`）。

## 出力とエラー

既存設定がある通常経路では起動処理へ進みますが、`--setup` はその場で起動する代わりにセットアップの進捗を表示します。`--no-start` がなければ完了後にサーバーを起動します（`metal/setup_mac.py:364-381,542-570`）。Mac 検査で問題があれば最初の問題を `S.fail()` に渡して終了します。`--check` 併用時は問題の有無に応じて 1 または 0 を返し、通常の setup 処理には進みません（`metal/setup_mac.py:382-386`）。

モデル準備時に Strata engine が稼働中であれば、同時準備による Mac の停止を避けるためエラーにして再実行方法を案内します（`metal/setup_mac.py:480-495`）。その他のダウンロード、build、ファイル検査、起動時エラーの詳細は、個々の helper と外部処理に依存するためここでは一律の終了コードを特定しません。

## 根拠

- `metal/setup_mac.py:327-358` — parser 定義、`--setup` の `store_true`、未知引数の処理。
- `metal/setup_mac.py:369-371` — 既存設定を直接起動する条件。
- `metal/setup_mac.py:373-448` — Mac 検査、モデル選択、`--check` / `--update` の早期終了。
- `metal/setup_mac.py:424-475,476-540,542-570` — package・engine・モデル準備、設定書き込み、`--no-start` と起動。
- `setup.py:82,7703-7707,9068-9069` — Control install mode と macOS 委譲条件。
- `setup.sh:7-13,39-50` — shell wrapper から `setup.py` への委譲。
- `docs/cli/README.md:1594-1618` — mac scope の位置付けと `--setup` の索引リンク。
