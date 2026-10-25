# `--no-start`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--no-start` |
| 別名 | なし |
| 値 | 取らない真偽フラグ。既定値は `False` |

## 役割

標準ベンチマークで `--profile` を使うとき、対象 URL でサーバーが応答しない場合にエンジンを起動せず失敗させます。ベンチマーク実行のために CLI がプロファイルのエンジンを起動することを避けたい場合に指定します。標準 suite は既定の `standard-v1` です。

## 使い方

```sh
strata bench run --profile local --no-start
```

`local` は保存済み serving profile 名、またはインストール済み run config を指します。`--profile` と `--url` は同時に指定できず、どちらか一方が必要です。

## 値と既定値

値を取りません。指定すると `True`、省略すると `False` です。値の形式や数値範囲はなく、同じフラグの重複指定を特別扱いする処理もありません。parser は標準 suite 用 option group に宣言しています（`strata_cli/cli.py:294-300,315-320`）。

## 実行時の動作

標準 suite の `--profile` 経路では、プロファイルから URL を組み立てて `/health` を最大 5 秒で確認します。サーバーが応答しない場合、`--no-start` があれば `ProfileError` を送出し、`bench_standard.start_engine()` による `strata serve --profile ... --quiet` の子プロセス起動へ進みません（`strata_cli/cli.py:1256-1271,1292-1299`、起動するコマンドは `strata_cli/bench_standard.py:673-685`）。

サーバーが既に応答していれば通常どおりそのサーバーを使い、CLI は停止しません（`strata_cli/cli.py:1300-1305`）。`--no-start` を付けない場合に限り、プロファイル指定かつ `/health` 無応答のときエンジンを起動し、ベンチマーク終了後にその実行が起動したプロセスを停止します（`strata_cli/cli.py:1292-1307`）。

このフラグが分岐で参照されるのは `standard-v1` の処理です。`--url` を選んだ場合、または `--suite` で別 suite を選んだ場合は `a.no_start` が参照されず、このフラグ自体による動作変更はありません（suite の分岐は `strata_cli/cli.py:1183-1189`、標準 suite の `/health` 分岐は `strata_cli/cli.py:1292-1305`）。`--url` 経路も自動起動の対象ではありません。

保存済みプロファイルでは、ベンチマークの重複実行を防ぐ lease を `/health` の確認前に取得します。したがって失敗して起動しない場合も lease ファイルの作成・ロック処理は通ります（`strata_cli/cli.py:1282-1289`、`strata_control/benchmarking.py:82-101`）。

## 適用条件と副作用

- 効果があるのは `--suite standard-v1`（既定）かつ `--profile` の場合です。`--url`／別 suite ではフラグは処理上無視されます。
- 応答中のサーバーや既存のエンジンを停止するフラグではありません。既存サーバーを使い、ベンチマーク処理自体は続行します。
- `--no-start` によって新しいエンジンプロセスは起動されません。プロファイルの読み込み、接続確認、標準ベンチマークに伴う出力・ネットワーク要求は別途行われます。
- 応答中でもモデル未ロードなら、標準ベンチマーク側が実行を拒否します。このフラグはモデルのロード待ちやロード状態を変更しません（`strata_cli/bench_standard.py:781-789`）。

## 出力とエラー

指定プロファイルのアドレスでサーバーが応答しない場合は、`no server is answering at the profile's address and --no-start was given` をエラーとして返し、終了コード `5` になります。人間向け出力は stderr の `strata: ...`、JSON 出力では `ok: false` と `error.code: 5` です（例外の定義は `strata_control/profiles.py:30-35`、送出は `strata_cli/cli.py:1292-1295`、例外変換は `strata_cli/cli.py:2166-2173`、出力は `strata_cli/cli.py:527-532`）。この失敗ではベンチマーク本体の `bench_standard.run()` へ進みません。

## 根拠

- 索引上の配置・スコープ: `docs/cli/README.md:610-625`（`strata bench run` の項にリンク）。
- parser、排他的な接続元、suite 既定値、フラグ宣言: `strata_cli/cli.py:293-320`。
- suite ごとの dispatch と標準 suite のみの処理分岐: `strata_cli/cli.py:1183-1189`。
- profile の URL 解決、health 判定、未応答時の拒否、既存サーバー利用、benchmark 呼び出しと終了処理: `strata_cli/cli.py:1256-1307`。
- エンジン起動・ロード待ち・停止の実装: `strata_cli/bench_standard.py:658-695,716-758`。
- 標準 suite がサーバー未応答・モデル未ロード・`/props` 応答なしを検査する箇所: `strata_cli/bench_standard.py:781-789`。
- 保存済み profile の lease: `strata_cli/cli.py:1282-1289`、`strata_control/benchmarking.py:82-101`。
- 調査では同一 revision の parser と呼び出し実装を確認しました。CLI `--help` と Release 配布物の照合は行っていません。
