# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets list` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`strata presets list` の使い方と、その parser に登録されたオプションを表示して終了します。保存済み tuning preset の一覧を表示する処理とは別です。

## 使い方

```sh
strata presets list --help
# ソース checkout から実行する場合
python strata.py presets list --help
```

## 値と既定値

値は不要です。`strata_cli.cli.parser()` は `argparse.ArgumentParser` を `add_help=False` なしで生成し、`presets` と `list` は標準の subparser として追加されています。したがって Python `argparse` が各 parser に標準の `-h` / `--help` action を追加します。list parser 固有の引数は `--model`（既定値 `None`）と `--output {human,json}`（既定値 `human`）です。 (根拠: `strata_cli/cli.py:40-45, 486-488`; `strata_cli/tune_commands.py:49-58`)

## 実行時の動作

`--help` action は選択した `list` parser の説明・usage・引数説明を出力し、通常は終了コード 0 で parser を終了します。出力内容には list 固有の `--model` と `--output` が含まれます。引数解析後に `presets_command()` が呼ばれ、`presets.list_presets(model=a.model)` を実行する経路はありますが、help action はその前に終了するため、preset の読み出し・一覧生成・JSON/human 出力には進みません。`--output` の値も help 表示形式には影響しません。 (根拠: `strata_cli/tune_commands.py:53-58, 289-300`; `strata_cli/cli.py:2217-2225, 2151-2152`)

## 適用条件と副作用

このオプションは `strata presets list` の parser に対するものです。親 parser の `strata presets --help` や他のサブコマンドの help は別スコープです。短縮形 `-h` は同じ標準 help action の別名です。

help の実行でも `main()` は parser を組み立てる前に `private_files.adopt_user_defaults()` を呼び出します。この関数は Windows 以外では何もせず、Windows では現在のプロセス token の既定 owner と default DACL を設定しようとします（失敗時は `False` を返し、例外を送出しません）。したがって通常の Windows 環境では出力ファイルを作成するものではありませんが、昇格実行時にはそのプロセスの後続作成ファイルに関わる token 既定値を変更する場合があります。 (根拠: `strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-385`)

## 出力とエラー

標準の `argparse` help action により help は標準出力へ表示され、正常終了します。help と関係なく、必須のサブコマンドを指定しない `strata presets` など parser の構文エラーでは usage とエラーが標準エラーへ出力され、終了コード 2 になります。`presets` parser が `required=True` であることはソースで確認できます。 (根拠: `strata_cli/tune_commands.py:50-51`)

## 調査範囲

同一 revision の parser 定義と dispatch 経路を確認しました。CLI `--help` 自体は補助実行していません。標準出力・終了コードの記述は Strata 独自実装ではなく、使用している Python `argparse` の標準動作に基づきます。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser と必須 subcommand 定義。
- `strata_cli/cli.py:486-488` — `presets` parser 群の登録。
- `strata_cli/cli.py:2217-2225, 2151-2152` — token defaults の呼び出し順、引数解析、`presets` dispatch。
- `strata_cli/tune_commands.py:49-58` — `presets list` parser、`--output` と `--model` の定義。
- `strata_cli/tune_commands.py:289-300` — list の通常実行経路。
- `strata_control/private_files.py:349-385` — Windows token defaults の処理。
