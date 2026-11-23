# `source-setup` (Mac) `--no-start`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh`（macOS Apple Silicon では `engine/metal/setup_mac.py` に委譲） |
| オプション | `--no-start` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。指定すると `True`、省略時は `False`。 |

## 役割

Mac 用セットアップのチェック、モデル取得・準備、設定ファイルと起動スクリプトの生成は通常どおり行い、最後に Metal エンジンの server を起動しないためのフラグです。モデルのインストールや設定だけを済ませ、後から起動スクリプトを使う用途に使います。既存の Metal 設定がある場合も、このフラグにより既定の「設定を使ってすぐ起動」経路ではなくセットアップ手順に入ります。(`engine/metal/setup_mac.py:372-418, 593-621`)

## 使い方

```sh
# Mac で通常のモデル選択・セットアップを行い、最後の server 起動を省略する
./setup.sh --no-start
```

## 値と既定値

`argparse` の `action="store_true"` で登録され、値や範囲の検証はありません。省略時は偽、指定時は真です。同じフラグを複数回指定しても真のままです。(`engine/metal/setup_mac.py:395-403`)

## 実行時の動作

macOS で通常の Terminal セットアップ入口を使うと、`terminal/setup.py` は引数を保ったまま `engine/metal/setup_mac.py` を呼び出します。Mac 側 parser は `--no-start` を認識し、既存 Metal 設定がある場合にそのまま起動する条件からこのフラグを除外します。したがって既存設定があっても、通常は Mac の確認からセットアップ処理へ進みます。(`terminal/setup.py:9206-9210, 11216-11220`; `engine/metal/setup_mac.py:372-418`)

フラグはモデルファイルの確認・取得、必要なモデル準備、設定 JSON と `run-<model>.sh` の書き込みを無効にしません。完了時には `All set.` と API URL、次回起動方法を表示した後、`--no-start` が真なら `0` を返して終了します。偽なら同じ設定ファイルを使って server 起動処理に進みます。表示される API URL は案内であり、この経路では server は起動されません。(`engine/metal/setup_mac.py:497-621`; `terminal/setup.py:7447-7453, 9149-9163`)

## 適用条件と副作用

- この文書の対象は索引に示された Mac 用 parser です。通常の `terminal/setup.py` が macOS で `metal/setup_mac.py` に委譲する経路が根拠です。(`terminal/setup.py:11216-11220, 9206-9210`)
- セットアップ処理自体は続くため、Python パッケージ導入、必要な engine / image encoder の build、モデルのダウンロードや準備、設定と起動スクリプトの生成が発生し得ます。`--no-start` はこれらを抑止しません。(`engine/metal/setup_mac.py:471-523, 525-589, 593-621`)
- モデル準備が必要で Strata engine が実行中なら、Mac のフリーズ回避のため処理を失敗させ、利用者に server を止めて再実行するよう案内します。このフラグは実行中 engine を停止しません。(`engine/metal/setup_mac.py:525-544`)
- `--check` を同時指定した場合は Mac の問題有無を検査した時点で戻るため、その先のセットアップにも server 起動にも進みません。`--update` を同時指定した場合は engine 更新後、モデルのダウンロード・準備より前に更新分岐から戻り、`--no-start` の終端判定には到達しません。(`engine/metal/setup_mac.py:429-432, 475-495, 619-621`)

## 出力とエラー

セットアップ完了時は `All set.`、API URL、次回起動方法を標準出力へ表示し、server を呼ばずに終了コード `0` を返します。(`engine/metal/setup_mac.py:614-621`; `terminal/setup.py:997-998`)

`--no-start` 自体に独立した入力検証エラーはありません。セットアップ中の失敗は通常どおり発生し得ます。たとえば Mac の要件不適合や、モデル準備中に engine が実行中の場合は `S.fail` がエラー文を表示して終了コード `1` で終了します。`--check` は問題があれば `1`、なければ `0` を返します。(`engine/metal/setup_mac.py:429-432, 538-541`; `terminal/setup.py:1049-1056`)

## 根拠

- `engine/metal/setup_mac.py:372-405` — Mac セットアップの parser。`--no-start` は値なしの `store_true`。未知の引数は警告として扱う。
- `engine/metal/setup_mac.py:416-418` — 保存済み Metal 設定がある場合の通常起動分岐と、`--no-start` による分岐条件。
- `engine/metal/setup_mac.py:429-432, 475-495` — `--check` の早期終了、および `--update` の更新専用経路。
- `engine/metal/setup_mac.py:525-544` — モデル準備時の実行中 engine 検査と失敗経路。
- `engine/metal/setup_mac.py:593-621` — 設定・起動スクリプト生成後、フラグに応じて終了する箇所。
- `terminal/setup.py:9206-9210, 11216-11220` — macOS セットアップ入口から Mac 用実装への委譲。
- `terminal/setup.py:7447-7453, 9149-9163` — 設定 JSON の書き込みと run script の生成。
- `terminal/setup.py:997-998, 1049-1056` — `S.say` の標準出力と `S.fail` のエラー表示・終了コード。
