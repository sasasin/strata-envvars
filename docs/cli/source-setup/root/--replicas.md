# `--replicas`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`SETUP.bat`、`update.sh`、`UPDATE.bat` から委譲） |
| オプション | `--replicas` |
| 別名 | なし |
| 値 | 整数 `N` |

## 役割

選択した GPU 群を同じ枚数ずつ含むグループに分け、グループごとに独立した Strata engine を起動する設定を作ります。リクエストは複数 engine に振り分けられます。各 replica はモデルを個別に保持します（`setup.py:8541-8544`、`serve/replicas.py:1-13`）。

## 使い方

4 枚の GPU を 2 枚ずつのグループにする例です。GPU 番号は環境に合わせてください。

```sh
./setup.sh --gpus 0,1,2,3 --replicas 2
```

同じ引数を `python setup.py ...`、`START-HERE.bat ...`、または更新 wrapper に渡せます。`SETUP.bat` は `START-HERE.bat --setup` を呼び、各 wrapper は `setup.py` に引数を渡します（`SETUP.bat:1-3`、`setup.sh:9-12,76`、`START-HERE.bat:44-54`、`update.sh:62`、`UPDATE.bat:1-6`）。

## 値と既定値

`setup.py` の parser は `type=int` で値を整数へ変換します。省略時は `None` で、今回の setup 実行から replica 数を設定しません（`setup.py:8541-8544`）。整数でない値は parser に拒否されます。コードには `N` の正の範囲を検査する明示的な validation はありません。

setup 側で設定を行うのは `N >= 2` の場合だけです。`N` が 1 以下ならこの処理は何もせず、初回 setup では `replicas` キーを作りません（`setup.py:9655-9668`）。`--replicas` は replica 設定を解除するオプションではありません。既存の run config に `replicas` がある場合、`SETUP_KEYS` に含まれないため、今回の config に設定されなければ通常の再 setup 時に旧値が引き継がれます。したがって、省略、`1` 以下の指定、GPU 条件を満たさない指定はいずれも既存の設定を明示的に消しません（`setup.py:6162-6167,6177-6188,6312-6340`）。

## 実行時の動作

`N >= 2` のとき、setup は今回選ばれた GPU のリスト `multi` が空でないこと、および GPU 数が `N` で割り切れることを確認します。条件を満たせば `cfg["replicas"] = N` を保存し、GPU リストを順番に等分したグループ数を表示します（`setup.py:9637-9645,9655-9664`）。例えば GPU 0,1,2,3 と `N=2` なら、0,1 と 2,3 の 2 グループです。

設定はモデルの run config に書かれ、生成される起動スクリプトはその config を `serve/server.py --config ...` に渡します（`setup.py:6312-6340,7260-7272`）。server は設定の `gpu` と `replicas` からグループを作り、グループが得られれば各グループに engine を一つずつ起動します。リクエストを振り分ける `ReplicaEngine` が前段に置かれます（`serve/server.py:8409-8418,7966-8007`、`serve/replicas.py:42-71,91-106`）。server を直接起動するときの同名 `serve/server.py --replicas N` は、その実行時に config の値を上書きします（`serve/server.py:8209-8214,8284-8285`）。

## 適用条件と副作用

- 選択 GPU がない、または GPU 数が `N` で割り切れない場合は setup が `[!]` 警告を表示し、今回の config には値を設定しません。提案される代替は `--gpu` / `--gpus` でカードを選ぶか、config に GPU グループを明記する方法です（`setup.py:9655-9664`）。この警告経路はエラー終了ではありません（`setup.py:817-829`）。
- 各 replica がモデルのコピーと host thread を持つため、総 RAM 使用量が増えます。setup は `os.cpu_count() < 8 * N` のとき RAM 確認の警告を出しますが、これは拒否条件ではありません（`setup.py:9667-9668`）。
- 1 グループに複数 GPU があり、`--layer-split` が `auto` 以外なら、その値が各 group に適用されるとの警告を出します（`setup.py:9665-9666`）。
- Linux で CPU topology を取得できる場合、server は replica ごとに重複しない物理 CPU core を割り当てます。割当不能時や Linux 以外ではこの affinity 設定はありません（`serve/replicas.py:21-23,109-115`、`serve/server.py:7970-7983`）。
- replica engine の起動に失敗すると、すでに起動した engine を閉じ、失敗した replica 番号を含む `[strata] replica ... did not start` で終了します（`serve/server.py:7979-8005`）。

`setup.py` の通常の parser 経路と config 作成箇所を対象に確認しました。macOS の通常 setup は別の `mac_setup` に早期委譲し、macOS Control と SYCL も別経路へ分岐するため、それぞれで `--replicas` が同じように保存・利用されるかは本調査では確認していません（`setup.py:8418-8420,8561-8564`）。

## 出力とエラー

GPU 条件不成立時は setup の `[!]` 警告表示となり、終了ではなく未設定で続行します（`setup.py:821-829,9655-9664`）。整数に変換できない値は `argparse` の parser で拒否されます（`setup.py:8420,8541-8544`）。server 起動時に設定された GPU 群を解釈できない場合は config error として終了し、engine 起動時の失敗は前節の replica 起動エラー経路になります（`serve/server.py:8409-8418,7979-8005`、`serve/replicas.py:42-81`）。

## 根拠

- parser 定義・値変換: `setup.py:8420-8421,8541-8544`
- GPU 群との適合判定、警告、config への格納: `setup.py:9637-9645,9655-9668`
- config の既定キーと既存値の引き継ぎ、書き込み: `setup.py:6162-6188,6312-6340`
- run script が server に config を渡す箇所: `setup.py:7260-7272`
- 起動時の config override・replica group 解決・engine 起動: `serve/server.py:8209-8214,8284-8285,8409-8418,7966-8007`
- GPU 群の validation と replica ごとの config: `serve/replicas.py:42-106`
- wrapper の引数委譲: `SETUP.bat:1-3`、`setup.sh:9-12,76`、`START-HERE.bat:44-54`、`update.sh:62`、`UPDATE.bat:1-6`
