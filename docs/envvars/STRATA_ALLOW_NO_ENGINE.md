# `STRATA_ALLOW_NO_ENGINE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Control モードのセットアップで engine component が見つからないとき、`strata launch` がモデルの準備を続けることを許可します。通常の `setup.py` や engine の実行時設定を切り替える変数ではなく、`setup.py` 内の engine 不在時の停止判定に使われます。

Terminal の launch runner は、利用可能な engine がないと判定した後、モデルのダウンロードを続ける選択を通過すると、子 `setup.py` の環境にこの変数を `1` として設定します。`setup.py` は engine が欠けている場合でも処理を続け、警告を出してモデルファイルの準備を行います。engine 自体はこの経路では取得もビルドもされず、engine component は後からインストールする必要があります。

## 値と判定

完全一致の文字列比較です。数値変換や trim はしません。

| `STRATA_ALLOW_NO_ENGINE` | engine が見つからない場合の判定（`STRATA_NEED_ENGINE=1` のとき） |
|---|---|
| `1` | engine 不在を理由に停止せず、警告してモデルの準備を続ける |
| unset、空文字、`0`、その他の値 | setup は `fail()` を呼び、終了コード 1 で停止する |

この判定は `setup.py` が engine missing の例外を捕捉した時点で実行されます。環境変数を setup 実行中に変更しても、その後の別の読み取り箇所はありません。

## 有効になる条件

- `setup.py` が Control モード（`STRATA_CONTROL_INSTALL=1`）で動くこと。このモードはモデルを準備し run config を書くが、engine を fetch/build しない。
- engine component の解決が `EngineMissing` になること。engine が見つかればこの変数は参照されず、engine 不在の警告も出ません。
- 停止を回避するには値が厳密に `1` であること。また停止条件は `STRATA_NEED_ENGINE` も厳密に `1` の場合に限られます。`STRATA_NEED_ENGINE` が未設定または別の値なら、`STRATA_ALLOW_NO_ENGINE` の値にかかわらず setup はこの判定では停止しません。

`strata launch` は engine がない場合、モデルの取得を続けるか確認します。拒否した場合は setup を起動せずに終了します。続行が承認された場合（`--yes` の場合も含む）、runner が子プロセス環境に `STRATA_ALLOW_NO_ENGINE=1` を設定します。engine がある通常経路では runner は `STRATA_NEED_ENGINE=1` を設定し、`STRATA_ALLOW_NO_ENGINE` は上書きしません。そのため、engine 解決後に状態が変わって setup 側で欠落が判明した場合などに、起動元環境から引き継いだ `STRATA_ALLOW_NO_ENGINE=1` が停止を抑止することがあります。

## 実行時の詳細

engine がない状態でこの値が有効だと、`setup.py` は `home()/engine` を engine の参照先として返し、meta に `component: "missing"` を設定します。stderr ではなく setup の標準出力に `[!]` 形式の警告を表示し、モデルをダウンロード・準備します。画像機能を要求していて、その engine folder に image encoder がない場合は、さらに画像機能を無効にする警告を出します。Terminal runner はモデルと設定の準備を終えた後、serving は開始せず、engine を後から入れるよう促す警告結果を返します。

無効の場合は `fail()` が engine 不在理由と engine の導入手順を出し、`sys.exit(1)` で終了します。案内には「nothing was downloaded and files already downloaded are kept」とあります。Terminal runner 自身の事前確認でモデルのダウンロードを拒否した場合は `LaunchError` で終了し、この変数を設定した子 setup は起動されません。

## 根拠

- `strata_cli/launch/runner.py:510-526`: engine 不在状態を記録し、確認・拒否の扱いを決める。
- `strata_cli/launch/runner.py:749-760`: setup 子プロセス環境から `STRATA_NEED_ENGINE` を一度除き、engine 不在なら `STRATA_ALLOW_NO_ENGINE=1`、それ以外なら `STRATA_NEED_ENGINE=1` を設定して起動する。
- `setup.py:72-78`: `STRATA_CONTROL_INSTALL=1` が Control mode を選ぶ。
- `setup.py:7160-7187`: Control mode の engine 解決、厳密な値判定、停止・警告・missing component の設定。
- `setup.py:693-702`: `warn()` の `[!]` 出力形式と `fail()` の標準出力・終了動作。
- `strata_cli/launch/runner.py:1157-1172`: engine 不在時はモデル設定後に serving を始めず、warning 結果を返す。
