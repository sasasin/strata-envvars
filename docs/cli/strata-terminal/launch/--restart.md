# `--restart`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--restart` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は `False`。 |

## 役割

指定した launch の選択内容が、すでに稼働中のモデルと異なる場合などに、確認を挟まず既存サーバーを停止して新しい選択で起動します。対話画面では再起動確認を省略し、`--no-tui` など画面を使わない経路では、通常なら既存サーバーが異なるため拒否されるケースを実行可能にします（`terminal/strata_cli/launch/cmd.py:146-148`, `terminal/strata_cli/launch/runner.py:2554-2589`）。

## 使い方

```sh
# Office プリセットを、同じ launch が別設定で稼働中でも置き換えて起動する
strata launch --preset Office --restart --no-tui
```

このコマンドは停止・起動を伴います。`--restart` は確認フラグではなく、確認なしで置き換える指定です。

## 値と既定値

- `argparse` では `action="store_true"` として登録されており、引数値・選択肢・範囲の validation はありません（`terminal/strata_cli/launch/cmd.py:141-149`）。
- 省略時は偽です。同じフラグを複数回指定しても真のままです。値を付ける形式（例: `--restart=true`）は定義されていません。
- `--yes` は別の質問（エンジンがない場合のダウンロード確認など）に使われる設定であり、再起動の許可にはなりません（`terminal/strata_cli/launch/cmd.py:146-152`, `terminal/strata_cli/launch/runner.py:978-986`）。

## 実行時の動作

引数値は TUI の `run_tui` と通常の `Runner` の両方へ渡され、Runner の `restart` 属性になります（`terminal/strata_cli/launch/cmd.py:871-877`, `terminal/strata_cli/launch/cmd.py:945-950`, `terminal/strata_cli/launch/app.py:693-712`, `terminal/strata_cli/launch/runner.py:975-986`）。通常起動ではモデル等のファイル確認後、モデル取得や停止より前に `check_serving()` が現在の launch を調べます（`terminal/strata_cli/launch/runner.py:3296-3314`）。

- 同じ profile で同じ選択・同じ port がすでに稼働し、再調整 (`--retune`) もしない場合は既存サーバーをそのまま再利用します。`--restart` を付けても停止・再起動しません（`terminal/strata_cli/launch/runner.py:2562-2570`）。
- 同じ profile の異なる設定、または指定 port を使う別 profile がブロック対象です。`--restart` があれば確認を求めず、その profile を停止対象にします（`terminal/strata_cli/launch/runner.py:2571-2589`）。
- 停止対象はエンジンの用意後、モデル準備より前に停止します。置き換え対象が保持する GPU メモリをモデル準備に使うためです。別 profile の停止時には関連 tunnel も停止します（`terminal/strata_cli/launch/runner.py:3311-3316`, `terminal/strata_cli/launch/runner.py:2591-2608`, `terminal/strata_cli/launch/runner.py:2632-2643`）。
- 置き換え対象がなく、別 port で動いている launch だけの場合は並行起動となり、そのモデルが GPU メモリに収まらず起動に失敗する可能性について通知します。`--restart` は別 port のサーバーを止めません（`terminal/strata_cli/launch/runner.py:2571-2577`）。
- `--plan` を指定すると `Runner.plan()` の結果を表示して終了し、起動時の `Runner.run()` と `check_serving()` には進みません。そのため `--restart --plan` でも既存サーバーは停止しません（`terminal/strata_cli/launch/cmd.py:897-925`, `terminal/strata_cli/launch/runner.py:3123-3145`, `terminal/strata_cli/launch/runner.py:3296-3314`）。

## 適用条件と副作用

- 同じ設定のサーバー再利用、置き換え対象のない起動、`--plan` では停止副作用はありません。`--restart` は「常に再起動」ではなく、Runner が差異と port の競合を見つけた場合に確認を省略する指定です（`terminal/strata_cli/launch/runner.py:2562-2589`）。
- TUI ではこのフラグがない場合、ブロック対象があれば一度だけ確認します。キャンセルすると稼働中のモデルをそのままにします。フラグがある場合はこの確認を通りません（`terminal/strata_cli/launch/app.py:498-503`, `terminal/strata_cli/launch/app.py:563-584`, `terminal/strata_cli/launch/runner.py:2579-2589`）。
- TUI を使わない経路でフラグがなく、異なる設定または port の競合がある場合は `LaunchError` code 6 で拒否し、`--restart` または先に `strata launch --stop` を使うよう案内します（`terminal/strata_cli/launch/runner.py:2579-2585`）。
- 置き換えの停止前に、モデル取得に必要な空きディスク容量を確認します。容量不足が分かった場合は code 6 で失敗し、稼働中サーバーは停止しません。停止そのものに失敗した場合も code 6 で失敗し、`strata launch --stop` を案内します（`terminal/strata_cli/launch/runner.py:2591-2608`, `terminal/strata_cli/launch/runner.py:2609-2625`）。

## 出力とエラー

通常の非 JSON 出力では失敗文を `stderr` に `strata: ...` として出し、JSON 出力 (`--output json`) では `ok: false` と code・message を JSON にして、同じ code を終了値にします（`terminal/strata_cli/launch/cmd.py:759-764`, `terminal/strata_cli/launch/cmd.py:949-961`）。置き換えを実行した場合は停止中の profile を示す進行メッセージが出ます（`terminal/strata_cli/launch/runner.py:2602-2607`, `terminal/strata_cli/launch/runner.py:2632-2642`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:141-152` — launch parser の定義、`--restart` の説明、`--yes` と `--plan` の別定義。
- `terminal/strata_cli/launch/cmd.py:849-877`, `terminal/strata_cli/launch/cmd.py:897-925`, `terminal/strata_cli/launch/cmd.py:945-961` — 対話判定、フラグの伝達、plan の早期終了、起動時のエラー処理。
- `terminal/strata_cli/launch/app.py:498-503`, `terminal/strata_cli/launch/app.py:563-584` — TUI Runner への伝達と再起動確認の挙動。
- `terminal/strata_cli/launch/runner.py:975-986`, `terminal/strata_cli/launch/runner.py:2554-2589` — Runner の値保持、稼働状態・設定・port の判定、再利用・確認・拒否・置き換え対象の決定。
- `terminal/strata_cli/launch/runner.py:2591-2625`, `terminal/strata_cli/launch/runner.py:2632-2643`, `terminal/strata_cli/launch/runner.py:3296-3349` — 停止順序、ディスク容量・停止失敗、通常実行経路。
- `docs/cli/README.md:836-884` — `strata launch` の索引上のスコープと作成対象リンク。

調査制約: 同一 revision の CLI `--help` は実行していません。parser 定義と Strata 内の呼び出し・実装を根拠にしています。
