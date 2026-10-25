# `bench.sh` / `BENCH.bat`（quick benchmark）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `quick-benchmark` |
| コマンド | `bench.sh`（POSIX） / `BENCH.bat`（Windows） |
| 実装 | `tools/strata_bench.py` |
| 引数の扱い | 両 wrapper は引数を Python 実装へ転送します。オプションは同実装で定義されます。 |

## 役割

現在の Strata 設定と実機で短い速度確認を行い、各リクエストの測定値とマシン情報を含むレポートを作成します。これは `strata bench run` が実装する標準ベンチマークとは別の quick speed check です。標準ベンチマークと同じプロトコルの結果として扱わないでください。

## 基本的な使い方

Strata の checkout ルートで実行します。

```sh
# Linux: 仮想環境を使って実行
./bench.sh

# Windows: 同梱の仮想環境を使って実行
BENCH.bat

# 設定を選び、必要なら追加 workload と既定以外の保存先を指定
python tools/strata_bench.py --config strata-model.json --clients 4 --long --out /tmp/strata-results

# 実行中の別サーバーを測定
python tools/strata_bench.py --url http://127.0.0.1:8080 --api-key "$STRATA_KEY"

# 既存結果どうしを比較（サーバーを起動せず測定もしない）
python tools/strata_bench.py --compare OLD_FOLDER --compare-only NEW_FOLDER
```

wrapper はルートへ移動してから `.venv` 内の Python を呼び、未セットアップならエラーを表示します。Windows wrapper は処理終了後に pause します。直接 `python tools/strata_bench.py` を呼ぶ方法もあります。

## 実行モード

| モード | 指定例 | 動作 |
| --- | --- | --- |
| 設定から通常実行 | `./bench.sh`、または `python tools/strata_bench.py` | ルートにある有効な `strata-*.json` のうち最終更新時刻が新しい設定を選びます。`--config FILE` で選択できます。 |
| 既存サーバーを測定 | `python tools/strata_bench.py --url http://127.0.0.1:8080` | 指定 URL の Strata サーバーを使い、bench はそのサーバーを停止しません。 |
| 結果比較 | `--compare OLD` | 新しい測定レポートを作成し、既存結果との比較を表示します。 |
| 比較のみ | `--compare OLD --compare-only NEW` | 2つの既存結果を比較して終了します。`--compare-only` には `--compare` も必要です。 |

## 測定内容と主な動作

通常実行ではサーバーの HTTP API に固定 suite を送り、既定では各 test を3回実行して中央値と範囲を記録します。測定対象は短い chat、約4K・16K token の prompt、5 turn の agent session です。`--clients N` は同時リクエストを追加し、`--long` は約32K token の prompt を追加します。context が足りない prompt や agent session はスキップされます。`--think` を指定しない場合、suite は thinking を無効にして短い回答を測ります。

サーバーが指定ポートで応答していなければ bench が設定から起動し、最大 `--ready-timeout` 秒（既定1800秒）待機します。測定後は bench が起動したサーバーだけを終了します。既定の出力先は `bench/results/` で、GPU・モデル・日付を含む一意なフォルダーに `README.md`、全リクエストを含む `results.json`、起動した場合は engine log excerpt を書きます。`--out DIR` で親フォルダーを指定できます。

## 注意点

- 実行中のモデルをロードして測定するため、既定でもモデル読み込み後に約3〜10分かかる場合があります。`--long` と `--clients` は追加負荷・所要時間を増やします。
- サーバーを新規起動する通常経路では、設定ファイルの port を使います。`--port` で変更できます。指定 port が Strata 以外の HTTP サービスに応答した場合は拒否されます。
- `--gpu` は bench がサーバーを起動するときにのみ渡されます。`--url` で既存サーバーを測るとき、そのサーバーの GPU 選択を変更しません。
- `--runs` は整数として読み取られ、実行時は最低1回に補正されます。`--clients` の同時実行がサーバーの batch slot 数を超える場合、一部のリクエストは順番待ちになります。
- API key は `--api-key`、次に `STRATA_KEY`、設定内の `api_key` の順で利用されます。key は出力前に置換されますが、レポートには設定・マシン情報が含まれるため、共有前に内容を確認してください。
- 起動設定に `--expert-profile-save` があっても、bench がサーバーを起動する場合はその引数を一時コピーから外し、既存の expert profile が短い測定で上書きされないようにします。元の設定ファイル自体は変更しません。
- 選択可能な Strata 設定がない場合、既存サーバーへの `--url` を使うか、セットアップが必要です。URL が Strata として応答しない場合は終了コード2、起動した server が ready にならない場合は終了コード1です。request failure があり、chat/prompt/agent のいずれにも結果がない場合も終了コード1です。
- `--quiet` は通常の進捗表示を抑えます。エラー表示や `argparse` のエラーは別経路で出力されます。

このコマンドの option ごとの値・挙動は[CLI 索引の quick-benchmark 節](../../README.md#quick-benchmark)にある個別文書を参照してください。

## 関連文書

- Strata checkout の `docs/COMMUNITY_BENCHMARKS.md` — quick benchmark の実行方法、出力形式、共有時の確認事項。
- Strata checkout の `docs/BENCHMARK_PROTOCOL.md` — `strata bench run` が実装する標準ベンチマークの手順。quick benchmark とは測定 protocol が異なります。
- [`docs/cli/README.md`](../../README.md) — CLI 索引と quick-benchmark の option 文書。

## 根拠

- `bench.sh:6-13`、`BENCH.bat:8-18` — wrapper の作業ディレクトリ、仮想環境確認、引数転送、Windows の終了後 pause。
- `tools/strata_bench.py:2-28` — quick suite の説明、測定種別、既定時間、標準 benchmark との区別。
- `tools/strata_bench.py:934-948` — parser 定義、option 名、型、既定値、help。索引の15項目（`--api-key`、`--clients`、`--compare`、`--compare-only`、`--config`、`--gpu`、`--help`/`-h`、`--long`、`--out`、`--port`、`--quiet`、`--ready-timeout`、`--runs`、`--think`、`--url`）と一致します。
- `tools/strata_bench.py:951-955,957-999` — compare-only の前提、設定選択、URL/port の判定、server 起動と ready 失敗。
- `tools/strata_bench.py:672-705,708-730,1034-1037` — expert profile 引数の一時除去、server 起動時の log、ready 待ち、bench が起動した server の終了。
- `tools/strata_bench.py:283-299,342-366,372-414` — context による skip、prompt/agent/concurrency suite の実行。
- `tools/strata_bench.py:910-918,1000-1037` — 結果フォルダー作成、ファイル出力、比較表示、終了コード。
- `docs/COMMUNITY_BENCHMARKS.md:98-142`、`docs/BENCHMARK_PROTOCOL.md:13-18` — 利用者向けの実行・報告方法、および標準 benchmark との区別。

調査範囲はこの checkout のソースと同梱文書です。Release 配布物を別途実行しての照合は行っていません。
