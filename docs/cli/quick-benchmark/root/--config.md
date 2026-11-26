# `--config`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `quick-benchmark` |
| コマンド | `bench.sh` / `BENCH.bat`（委譲先: `python tools/strata_bench.py`） |
| オプション | `--config` |
| 別名 | なし |
| 値 | JSON 設定ファイルのパス（1 個） |

## 役割

ベンチマークに使う Strata モデル設定ファイルを指定します。`--url` を指定せずサーバーを起動する場合は、この設定で起動し、ポートや API キーなども設定から読みます。省略時は `terminal/` 直下にある有効な `strata-*.json` のうち更新日時が最も新しいものを選びます。

## 使い方

```sh
# リポジトリルートから、terminal/ にある別のモデル設定を使って測定
./tools/bench.sh --config strata-model.json
```

`tools/bench.sh` は `terminal/` に移動してから Python スクリプトへ全引数を渡します。Windows の `tools/BENCH.bat` も同じスクリプトへ引数を転送します（`tools/bench.sh:6-10`、`tools/BENCH.bat:8-16`）。

## 値と既定値

- 値は `argparse` が受け取る文字列で、parser に `type`、`choices`、`required`、既定値の指定はありません。省略時は `None` です（`terminal/tools/strata_bench.py:1079-1095`）。
- 指定パスが絶対パスならそのまま使います。相対パスが現在の作業ディレクトリに存在すればそのパスを使い、存在しなければ Strata の `terminal/` (`ROOT`) を基準に解決します（`terminal/tools/strata_bench.py:56`、`1104-1110`）。
- ファイルが存在しない、または通常ファイルでない場合は stderr にセットアップ案内を出し、終了コード `2` で終了します。JSON の読み込みは UTF-8 BOM を許容しますが、JSON 構文や設定オブジェクトの形はこのオプションの parser では検証されません。不正 JSON は `json.loads` から例外になります（`terminal/tools/strata_bench.py:1116-1121`）。
- 設定オブジェクトはサーバー起動時に `terminal/serve/server.py` の `--config` へ渡されます。同サーバーの説明では `exe`、`args`、`cwd`、`tokenizer`、`model_name` などを含む JSON とされています（`terminal/tools/strata_bench.py:812-829`、`terminal/serve/server.py:9157-9160`）。

## 実行時の動作

- `--url` を指定しない場合、指定設定を読み込みます。`--port` がなければ JSON の `port`（なければ `8080`）を使用し、設定の `host` と組み合わせて接続先を決めます。既定サーバーがすでにそのポートで応答していて Strata と判定されれば、そのサーバーを利用します。別サービスが応答するとポート指定を案内して終了コード `2` になります（`terminal/tools/strata_bench.py:1121-1137`）。
- Strata サーバーがまだ応答しない場合、ベンチマークが設定ファイルを `serve/server.py --engine strata --config <file> --port <port>` に渡して起動し、準備完了を待ちます。起動失敗またはタイムアウトではログ末尾を stderr に出し終了コード `1`、起動したプロセスは終了処理で停止します（`terminal/tools/strata_bench.py:812-829`、`1139-1146`、`1181-1184`）。
- `--url` を指定した場合も `--config` を同時指定すると設定を読み込みますが、接続先は `--url` で決まり、その設定でサーバーは起動しません。設定は API キーのフォールバック、GPU・モデルなどの測定情報にも使われます。`--url` だけを指定した場合は設定ファイルを読みません（`terminal/tools/strata_bench.py:1104-1125`、`1128-1141`、`718-770`）。
- 設定の `args` に `--expert-profile-save FILE`（または `--expert-profile-save=FILE`）があると、ベンチマークはサーバーへ渡す一時コピーからその指定を除きます。元の設定は変更せず、stderr に理由を通知し、一時設定をログファイルと同じ一時ディレクトリに作ります（`terminal/tools/strata_bench.py:796-829`）。
- 設定情報は結果の `README.md` と `results.json` に記録されます。設定表示では `exe`・`args` のパスを基底名にし、`cwd`、`log`、設定の `env` 全体や名前に `key`／`token`／`secret`／`password`／`auth` が含まれるキーを除きます。`env` のうち `STRATA_`、`HIP_`、`CUDA_`、`ROCR_`、`ONEAPI_`、`SYCL_` で始まる項目は記録対象です。書き込み・表示前にホーム、ユーザー名、ホスト名、IP、API キーなどの値も置換されます（`terminal/tools/strata_bench.py:81-118`、`645-662`、`1057-1065`）。

## 適用条件と副作用

`--config` はベンチマークの入力設定を選びます。通常のサーバー起動経路では指定モデルのエンジンを起動し、HTTP API に測定リクエストを送ります。すでに Strata が応答していればそのサーバーを利用し、設定に基づく起動を行いません。設定ファイル自体は書き換えませんが、前述の `--expert-profile-save` 除去条件では一時 JSON を作成します。レポートは通常 `bench/results/`（リポジトリの `docs/bench-results/` があればそちら）に作成され、`--out` で変更できます（`terminal/tools/strata_bench.py:1057-1065`、`1164-1165`）。

値が JSON ファイルのパスとして妥当か以外に、parser 側の独自 validation や空文字の拒否はありません。設定 JSON 内の実行可能ファイルや引数の妥当性、および起動後のエンジン固有の失敗条件は、このオプションだけからは確定できず、サーバー側の処理に委ねられます。

## 出力とエラー

- パスが見つからない場合は stderr に「No Strata model is set up...」を出して `2`（`terminal/tools/strata_bench.py:1116-1119`）。
- `--url` 先に Strata が応答しない場合は stderr に通知して `2`（`terminal/tools/strata_bench.py:1130-1134`）。
- 起動したサーバーが準備完了にならない場合はログ末尾を秘匿化して stderr に出し `1`（`terminal/tools/strata_bench.py:1143-1146`）。
- JSON 構文エラーはこの箇所では捕捉されず、通常の Python 例外として伝播します（`terminal/tools/strata_bench.py:1120`）。

## 根拠

- `terminal/tools/strata_bench.py:1079-1095` — `--config` の parser 定義と、型・既定値・必須指定がないこと。
- `terminal/tools/strata_bench.py:1104-1125` — パス解決、既定設定選択、JSON 読み込み、`--url`・ポート・host との関係。
- `terminal/tools/strata_bench.py:777-789` — 省略時に有効な `strata-*.json` を更新日時順で選ぶ条件。
- `terminal/tools/strata_bench.py:796-829`、`1139-1146`、`1181-1184` — 設定の安全な一時加工、サーバー起動・準備待ち・終了処理。
- `terminal/tools/strata_bench.py:645-662`、`1057-1065`、`1164-1165` — レポートに含める設定情報、秘匿化、出力先。
- `terminal/serve/server.py:9157-9160` — 委譲先サーバーの `--config` と JSON の説明。
- `tools/bench.sh:6-10`、`tools/BENCH.bat:8-16` — POSIX / Windows の入口からの引数転送。
