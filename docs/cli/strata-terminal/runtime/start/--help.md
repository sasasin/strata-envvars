# `strata runtime start --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime start` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし。ヘルプ表示用のフラグ |

## 役割

`strata runtime start` の使用法と、その parser に登録されたオプションを表示します。`strata_cli/cli.py` は `argparse.ArgumentParser` でトップレベル parser を作り、`runtime` と `start` を subparser として登録します。`--help` と `-h` は明示的な個別宣言ではなく、`argparse` が各 parser に標準で加える同じヘルプ action の別名です（`strata_cli/cli.py:40-46,197-212`）。

## 使い方

ソース checkout のルートで実行する例です。

```sh
python strata.py runtime start --help
```

短縮形も使えます。

```sh
python strata.py runtime start -h
```

`runtime start` では `--profile` が必須ですが、help action は引数解析時にヘルプを出して終了するため、ヘルプだけを見るときに profile 値は不要です。

## 値と既定値

`--help` と `-h` は値を取りません。同一 parser の help には必須の `--profile PROFILE`、`--die-with-pid PID`、`--plan`、既定値 300 の `--wait WAIT`、既定値 30 の `--shutdown-timeout SHUTDOWN_TIMEOUT`、`--output {human,json}`（既定値 `human`）が表示されます。one-shot command 共通 option として `--json`（`--output json` の alias）と `--quiet` も追加されます（`strata_cli/cli.py:203-212,508-515`）。これらは help の対象範囲を示すもので、`--help` 自体の動作は変えません。

## 実行時の動作

`main()` は parser を作り `parse_known_args()` で引数を解析します。標準 help action は使用法と option の説明を stdout に出して parser を終了させるため、通常の `_runtime()` / `management.runtime_action()` による起動処理には進みません。従って help 表示は profile の起動や server の開始を行いません（`strata_cli/cli.py:2217-2231,1331-1357`）。

同一 revision の source checkout で `python strata.py runtime start --help` を実行すると、usage と上記 option 一覧が stdout に出力され、終了コードは `0` でした。Release 配布物や他 platform の表示は確認していません。

## 適用条件と副作用

ヘルプ解析より前に、CLI の `main()` は `private_files.adopt_user_defaults()` を呼びます。この処理は Windows 以外では何もせず、Windows では現在の process token の既定 owner と DACL の設定を試みます。従って Windows ではヘルプ表示でもこの前処理が先に実行されます（`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-390`）。

`strata.py` の entry point は parser 起動前に旧 updater 拒否判定と Control handover 判定も呼びます。source checkout からの実行は通常 handover の対象外です。インストール済み CLI ではより新しい Control が見つかった場合に同じ引数で引き継ぐことがあり、破損した更新先などの条件では警告を出して現行 Control で継続します（`strata.py:30-42`; `strata_cli/handover.py:126-164`）。

## 出力とエラー

通常の help 表示は stdout に出力され、終了コード `0` で終了します。help action が実行されず、`--profile` など必須値が欠ける場合や未認識引数がある場合は parser error の経路で usage/error が stderr に出て終了コード `2` になります。`main()` は未認識引数を `ap.error()` に渡します（`strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/cli.py:40-46,197-212` — argparse parser、runtime/start の階層と start 固有 option。
- `strata_cli/cli.py:508-515` — `--json` と `--quiet` を含む one-shot parser への共通 option 追加。
- `strata_cli/cli.py:1331-1357,2217-2231` — runtime の実行経路と、引数解析・エラー処理。
- `strata.py:30-42`、`strata_cli/handover.py:126-164` — entry point の旧 updater 判定と Control handover。
- `strata_control/private_files.py:349-390` — help 解析前に呼ばれる Windows 向け既定 owner/DACL 設定処理。

