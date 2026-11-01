# `STRATA_TUNE_NO_QUIET_CHECK`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata Desktop のホストプロセスがネイティブ自動調整（`tune auto`）を起動するとき、他の Strata engine や CPU 負荷を確認して静かになるまで待つ処理を省くためのスイッチです。環境変数を読むのは Python CLI や engine ではなく `apps/host/server/native-autotune.mjs` です。有効時は子 CLI に `--no-quiet-check` を付けます。

## 値と判定

| `process.env.STRATA_TUNE_NO_QUIET_CHECK` | 挙動 |
|---|---|
| 文字列 `1` | `tune auto` の引数に `--no-quiet-check` を追加 |
| 未設定、空文字、その他すべての文字列 | 引数を追加しない |

JavaScript の厳密な文字列比較（`=== '1'`）で、数値変換や trim、大文字小文字変換はありません。したがって `01`、`true`、` 1` は無効です。値は `createAutoTune().start()` が autotune の引数を組み立てる時点で読み、static cache はありません。ホスト起動後に `process.env` が変更された場合も、その後の呼び出しでは変更後の値が参照されます。設定値を子プロセスに渡して Python が環境変数として読む実装ではなく、ホストが CLI 引数に変換します。

## 有効になる条件

- Desktop のネイティブ操作から `tune` または `autotune` を実行する経路です。モデルが準備済みで、処理開始時に外部実行 engine がなく、処理中の request がないことを確認した後に tuner を起動します（`apps/host/server/native-control.mjs:482-492`）。
- OS や GPU backend による環境変数判定分岐はありません。環境変数自体は host の Node.js 側で判定されます。
- `recheck` 経路ではこの変数を見ず、`presets recheck` の引数にも `--no-quiet-check` を追加しません（`apps/host/server/native-autotune.mjs:85-98`）。
- CLI を直接実行する場合、この環境変数を読む箇所はありません。直接の `strata tune auto` で同じ待機を省くには CLI 引数 `--no-quiet-check` を指定します。
- 静穏確認を省いても、メモリ不足を待つ／候補を skip する guard など、tuning の他の処理は無効になりません。

## 実行時の詳細

Desktop が autotune job を開始すると、host は `tune auto` の引数を作成し、この変数が厳密に `1` の場合だけ `--no-quiet-check` を追加して子 CLI を起動します（`apps/host/server/native-autotune.mjs:79-100`）。CLI はこの flag を argparse の boolean として受け、`check_busy=not a.no_quiet_check` として tuner に渡します（`strata_cli/tune_commands.py:41,174-197`）。

既定では各 engine run の開始前に、lock を取得した後で quiet check が行われます。他の Strata engine が動いているか、CPU 使用率が 25% を超えている場合は `Waiting for the PC to be quiet (...)` を進捗に出し、10 秒間隔で確認します。最大 300 秒待つと `measured while the machine was busy (...)` を結果 note に加えて続行します。`--no-quiet-check` がある場合、この確認関数は直ちに戻るため待機ログや busy note はこの確認由来では発生しません（`strata_control/autotune.py:242-266,303-324`）。

Desktop 側は tuner の status file を poll して進捗を更新し、CLI の stdout JSON を結果として処理します。CLI 起動失敗、JSON の `ok: false`、または JSON を得られない終了は Desktop の job error になります（`apps/host/server/native-autotune.mjs:100-123`）。この変数が busy check を外すこと自体はエラーや終了条件を追加しません。なお、CLI の `--no-quiet-check` は静穏確認だけに作用し、前述の RAM guard は引き続き実行されます。

## 根拠

- 環境変数の唯一の実読み取りと引数変換: `apps/host/server/native-autotune.mjs:85-100`。
- Desktop の tune/recheck 操作経路、モデル準備・外部 engine・request の条件: `apps/host/server/native-control.mjs:478-494`。
- CLI flag の定義と `check_busy` への変換: `strata_cli/tune_commands.py:25-46,174-197`。
- quiet wait の判定、既定の busy 条件、待機上限・進捗 note と run 前 guard: `strata_control/autotune.py:242-266,303-324`。
- CLI 終了結果の Desktop 側処理: `apps/host/server/native-autotune.mjs:113-123`。

`000_envvers.md` には候補として掲載されていますが、値を読むのは Desktop host のみです。CLI の `--no-quiet-check` という引数名や engine 向け環境変数ではありません。
