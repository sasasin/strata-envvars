# `strata launch` `--set`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--set` |
| 別名 | なし |
| 値 | `KEY=VALUE`。engine 引数または環境変数の設定を一つ指定する。繰り返し指定可能。 |

## 役割

保存済み preset または今回起動するモデルに、engine の追加引数や環境変数を重ねます。指定した engine 引数は今回の launch の明示値として run config に反映され、設定の優先順位では保存済みの利用者指定値や較正値より上になります。`STRATA_*` など大文字を含む環境変数名は run config の `env` に設定され、サーバーが engine 子プロセスを起動するときにその環境へ反映します（`terminal/strata_control/arg_layers.py:3-18,75-108`; `terminal/strata_cli/launch/runner.py:801-815`; `terminal/serve/server.py:4007-4028`）。

## 使い方

```sh
# preset の今回の起動だけに engine 引数と環境変数を追加
strata launch --preset Office --set prefill=65536 --set STRATA_PIN_BY_NEED=1 --no-tui

# サーバー設定の idle-unload を300秒にする
strata launch --preset Office --set idle-unload=300 --no-tui
```

## 値と既定値

- `--set` は `action="append"`、既定値 `[]` で登録されており、値は必須です（`terminal/strata_cli/launch/cmd.py:124-125`）。この option 自体に既定の設定値はありません。
- 最初の `=` でキーと値を分け、前後の空白を除きます。`=` より後ろにある追加の `=` は値に残ります。通常のキーは小文字始まりの `[a-z][a-z0-9-]*` に合い、`--prefill` のような `--` 付きも指定できます。通常キーの `_` は `-` に正規化されます。大文字を一つ以上含む環境変数キーは `[A-Za-z_][A-Za-z0-9_]*` の形式です（`terminal/strata_cli/launch/settings.py:361-377`）。
- `=` を省略した場合も値は空文字として受理されます。engine の値を取る引数では空値は変更なしとして扱われますが、環境変数では空文字が設定値になります（`terminal/strata_cli/launch/settings.py:365-385,392-417`）。
- 同じ正規化後のキーを複数回指定した場合は後の値が残ります（`terminal/strata_cli/launch/settings.py:380-385`）。preset に同じキーがある場合も CLI の `--set` が上書きします（`terminal/strata_cli/launch/cmd.py:215-221,302-303`）。

## 実行時の動作

parser は値を文字列のリストとして受け取り、`settings_from_args()` が preset の `extra` に CLI 指定をマージします。engine 引数キーは `--key` 形式に正規化され、真偽値 option では空値または `on` / `true` / `yes` が有効化、`off` / `false` / `no` / `none` が除去を表します。その他は値として適用されます。環境変数キーは値をそのまま保持し、`off` / `unset` / `none`（大文字小文字を区別しない）なら run config の `env` からそのキーを除去します（`terminal/strata_cli/launch/settings.py:392-417`; `terminal/strata_cli/launch/runner.py:801-806`; `terminal/strata_control/tune_knobs.py:536-543`）。

通常の engine 引数は `arg_layers.layer()` で今回の明示値として `args` と `user_args` に反映されます。設定ソースの優先順は今回の launch 指定、保存済み利用者指定、適合する較正値、Auto です。ただし `launch_set` に今回限りの指定を記録するため、次回起動時に今回の `--set` が利用者の恒久設定として引き継がれるわけではありません（`terminal/strata_control/arg_layers.py:3-18,75-108`）。`--save-preset NAME` を併用すると、マージ後の選択をその名前の preset に保存または置換します。保存しない場合は preset 自体は更新せず、起動履歴のみ更新します（`terminal/strata_cli/launch/cmd.py:893-895,962-966`; `terminal/strata_cli/launch/store.py:76-86`）。

`idle-unload` は engine 引数ではなくサーバー設定 `idle_unload_s` に変換され、engine argv には渡りません。数値文字列は秒数として数値化され、整数値なら整数で保存されます。`off` 等は設定キーを削除します。数値に変換できない値は launch error になります（`terminal/strata_cli/launch/runner.py:586-610,801-815`）。

## 適用条件と副作用

- 起動対象を `--preset` または `--model` などで指定して使います。`--set` だけでは `have_choices` に数えられず、非対話または `--no-tui` では起動対象を指定するよう終了コード 2 で拒否されます（`terminal/strata_cli/launch/cmd.py:849-862`）。
- engine 引数名が実際の engine に存在するかは、CLI の `--set` 値を設定へ変換する段階では検証しません。対話画面で手入力する advanced 設定には未知 flag の警告処理がありますが、CLI parser の `--set` 経路からは呼び出されません（`terminal/strata_cli/launch/settings.py:365-385`; `terminal/strata_cli/launch/params.py:212-221`; `terminal/strata_cli/launch/screens.py:1619-1625`）。engine が知らない引数を受け取った場合の起動可否やメッセージは対象 engine に依存し、この CLI の検証では保証されません。
- 起動処理では private run config を作成・更新し、そこから server が engine 子プロセスを起動します。環境変数指定はその子プロセス環境へ反映されます（`terminal/strata_cli/launch/runner.py:2204-2238`; `terminal/serve/server.py:4007-4028`）。

## 出力とエラー

- 空の設定名や形式に合わない名前は `ValueError` となり、通常出力では `strata: <理由>` を stderr に出して終了コード 2、`--output json` では error JSON を stdout に出して同じコードで終了します（`terminal/strata_cli/launch/settings.py:365-377`; `terminal/strata_cli/launch/cmd.py:759-764,1011-1012`）。
- `idle-unload` が数値に変換できない場合も同じ launch error 経路で失敗します（`terminal/strata_cli/launch/runner.py:592-609`; `terminal/strata_cli/launch/cmd.py:950-961`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:73-80,124-125` — `strata launch` の parser、用途説明、`--set` の反復指定。
- `terminal/strata_cli/launch/settings.py:361-385,392-417` — キーの形式、正規化、重複統合、値の解釈。
- `terminal/strata_cli/launch/cmd.py:215-221,302-303,849-862` — preset への上書きと適用条件。
- `terminal/strata_control/arg_layers.py:3-18,75-108` — engine 引数の優先順位と今回限りの明示指定。
- `terminal/strata_cli/launch/runner.py:586-610,801-815,2204-2238` — `idle-unload` 特例、run config 組み立てと保存。
- `terminal/strata_control/tune_knobs.py:536-543`; `terminal/serve/server.py:4007-4028` — 環境変数の run config 反映と engine 子プロセス環境への適用。
- `terminal/strata_cli/launch/params.py:212-221`; `terminal/strata_cli/launch/screens.py:1619-1625` — 対話画面での未知 flag 警告。CLI `--set` の設定変換経路にはこの検査呼び出しがない。
