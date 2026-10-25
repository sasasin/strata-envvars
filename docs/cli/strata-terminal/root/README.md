# `strata`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata`（トップレベル） |
| POSIX の入口 | `bin/strata`。checkout では `strata.py` を起動 |
| 実装 | `strata.py`、`strata_cli/cli.py` および各コマンド module |
| トップレベル option | `-h` / `--help`、`--version`。サブコマンド固有 option は各コマンドの文書を参照 |

## 役割

Strata Terminal CLI は、推論サーバーの起動・管理、モデルやコンポーネントの確認、接続クライアントの設定、監視などを行うユーザー向け Python CLI です。実行ファイル名が同じネイティブ推論エンジンとは別のプログラムで、Terminal が必要に応じて engine を管理・起動します。入口と配布形態の説明は [`000_cli_tools.md`](../../000_cli_tools.md) を参照してください。

トップレベル parser は `-h/--help` と `--version` を定義し、必須のサブコマンドを一つ受け付けます。トップレベルで `strata` だけを実行すると、サブコマンド必須の usage error になります。各サブコマンドは用途ごとに parser と option scope が分かれています（`strata_cli/cli.py:40-46`）。

## 基本的な使い方

```sh
# トップレベルのコマンド一覧と概要
strata --help

# Terminal と Python の版情報
strata --version

# 既存の run config を使って前景サーバーを起動
strata serve --profile /absolute/path/to/strata-model.json

# 起動、監視、接続案内をまとめて行う
strata launch

# 現在のサーバー状態を一度確認
strata status --json
```

ソース checkout では `python strata.py ...` または POSIX wrapper の `bin/strata ...` を使えます。POSIX wrapper は checkout または install 配置から `strata.py` を見つけて選択した Python で起動します（`strata.py:1-4,30-43`、`bin/strata:90-100,128-133`）。

## 主なコマンドと実行モード

トップレベル help に登録された主なコマンドは次のとおりです（`strata_cli/cli.py:45-46,69-70,107-140,141-174,190-202,255-256,291-293,348-350,395-398,486-506`。遅延登録されるコマンドを含む一覧は help 出力も確認）。

| 用途 | 代表的なコマンド | 概要 |
| --- | --- | --- |
| 起動・利用 | `launch`、`serve`、`runtime`、`connect` | `launch` は対話式または option 指定で準備・起動し、monitor を開けます。`serve` は run config による前景起動、`runtime` は所有するローカル server の常駐管理、`connect` はアプリ用接続設定の表示・書き込みを行います。 |
| 状態確認 | `status`、`monitor`、`logs`、`doctor`、`components`、`models`、`config` | server/client telemetry、request activity、ローカル設定や component の確認を行います。read-only と説明される command もありますが、個々の条件は各文書を参照してください。 |
| 設定管理 | `profile`、`connection`、`presets`、`ops` | 保存 profile、monitor 接続、tuning preset、型付き operator recipe を管理します。 |
| engine・配布 | `install`、`update`、`engine`、`tune`、`drafting` | 明示的な install/update、engine tuning・calibration、補助モデルファイルの確認・取得などを行います。 |
| 計測・作業 | `bench`、`timeskip`、`code` | 明示的な serving benchmark、checkpoint 付きの bounded revision workflow、共有 Desktop harness 用 coding client です。`code` は共有 harness component がない環境では利用できません。 |

対話式の画面を使う `launch` / `monitor` のほか、`--no-tui` や one-shot の `status` のように画面を開かずに使う経路があります。server を前景で動かす `serve` と、端末を閉じた後も動作する常駐型 `runtime start` は異なる実行形態です（`strata_cli/cli.py:197-212`）。

## 主な動作と注意点

- `strata.py` は起動前に handover を確認し、`serve` / `bench` に必要な Python package が欠けていればエラーコード 5 で終了します。起動時に package を自動インストールすることはありません。他のコマンドはこの preflight の package 検査対象外です（`strata.py:14-27,30-43`）。
- POSIX wrapper は `serve` / `bench` についても依存 package を事前確認します。Release runtime が欠落した場合や `strata.py` が見つからない場合は stderr に案内を出して終了コード 5 で終了します（`bin/strata:80-105,109-126`）。Windows の wrapper の詳細な実行条件はこの調査では追跡していません。
- CLI の `--help` は argparse が生成します。トップレベル help は登録コマンドの一覧を示し、サブコマンドの詳細 option はそのサブコマンドの help を使って確認します（`strata_cli/cli.py:40-45`）。
- `--version` は `strata <product version> (build <build version>; python <version> at <interpreter path>)` を stdout に一行出し、終了します（`strata_cli/cli.py:30-37,40-45`）。表示される interpreter のパスは環境依存です。
- 通常の実行時は command に応じた handler へ dispatch し、引数外の失敗は種類に応じて stderr または JSON error と終了コードで返します。KeyboardInterrupt は終了コード 130 で、処理完了が不明な場合がある旨を報告します（`strata_cli/cli.py:527-533,2119-2193`）。command ごとのファイル・ネットワーク・server 等への副作用は個別ページに記載します。

## 関連文書

- [CLI オプション索引](../../README.md) — コマンド階層、option scope、個別文書へのリンク。
- [CLI の入口・配置一覧](../../../000_cli_tools.md) — Terminal CLI とネイティブ engine の区別、wrapper と配布形態。
- [`strata launch` 概要](../launch/README.md)
- [`strata profile` 概要](../profile/README.md)
- [`strata doctor` 概要](../doctor/README.md)

各コマンドの option 文書リンクは [CLI オプション索引](../../README.md) を参照してください。

## 根拠と調査範囲

- `strata_cli/cli.py:30-46` — version action、root parser、必須サブコマンドの定義。
- `strata_cli/cli.py:69-202,255-350,395-506` — 主なコマンド階層と遅延登録されるコマンド。
- `strata_cli/cli.py:2119-2193` — command dispatch と共通エラー経路。
- `strata.py:14-43`、`bin/strata:90-133` — checkout entry、依存確認、起動 wrapper。
- 同一 checkout の `python strata.py --help` と `python strata.py --version` を補助確認し、parser 定義と照合しました。`strata --help` 相当の出力は上記サブコマンド階層と一致します。
- GitHub Release の実体、Windows wrapper の挙動、各 command の詳細な副作用は本ページの調査対象外です。最新版 Release の実ファイル内容を確認したものとしては記載していません。
