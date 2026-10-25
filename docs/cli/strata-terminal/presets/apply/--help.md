# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets apply` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし。指定するとこのサブコマンドの使用法を表示する |

## 役割

`strata presets apply` の使用法を表示します。`argparse.ArgumentParser` の標準ヘルプ action が `-h` と `--help` を登録します。このコマンドでは必須位置引数 `preset` と、出力形式を選ぶ `--output {human,json}` が表示されます。

## 使い方

```console
python strata.py presets apply --help
```

インストール済み Terminal CLI では `strata presets apply --help` と実行します。

## 値と既定値

このフラグは値を取りません。`-h` は同じ help action の短縮別名です。サブコマンド parser は `argparse` の既定設定で生成され、別の help action や formatter は指定されていません。help を出す場合は `preset` を省略しても引数不足エラーには進まず、通常の apply 処理も呼び出されません。

## 実行時の動作

`strata_cli/tune_commands.py` で `presets` の下に `apply` parser が追加され、その parser に共通引数 `--output` と必須位置引数 `preset` が登録されます。`-h` / `--help` が指定されると parser が使用法を表示して終了するため、`presets_command()` の `apply` 分岐が preset を検索・有効化する処理には到達しません。

実際のヘルプ出力は次の形式でした。

```text
usage: strata presets apply [-h] [--output {human,json}] preset

positional arguments:
  preset

options:
  -h, --help            show this help message and exit
  --output {human,json}
```

`--output` は help 出力内で案内される別オプションで、通常実行時の既定値は `human`、選択肢は `human` と `json` です。

## 適用条件と副作用

この help action は `apply` を実行しないため、保存済み preset の有効化や active index の更新は行いません。通常の apply 処理では preset を有効化して前の preset を undo 用に保持しますが、その処理は `presets_command()` の `cmd == "apply"` 分岐で行われ、help 表示経路とは別です。

ただし CLI 共通の前処理として、parser を作る前に `private_files.adopt_user_defaults()` が呼ばれます。実装上 POSIX では何もせず、Windows では現在の process token の owner / default DACL を設定します。これは help 専用の処理でも preset データへの変更でもありません。

## 出力とエラー

同一 revision のソース checkout で `python strata.py presets apply --help` を実行すると、上記の usage と引数一覧が表示されました。help action は parser 標準の終了経路を通るため、preset がなくても help を表示できます。通常の `apply` 実行時に preset 解決が失敗した場合は `PresetError` が処理されますが、これは help の失敗経路ではありません。

## 根拠

- parser と option scope: `strata_cli/tune_commands.py:49-65`（`presets`、共通 `--output`、`apply`、位置引数 `preset`）。
- help から apply 分岐までの処理: `strata_cli/cli.py:2217-2231`（parser の解析と余分な引数の処理）、`strata_cli/cli.py:2151-2152`（`presets_command()` への dispatch）、`strata_cli/tune_commands.py:289-313`（apply 時の preset 有効化）。
- CLI 共通の前処理: `strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-389`（POSIX では no-op、Windows では process token defaults を設定）。
- 適用時の検索・有効化: `strata_control/presets.py:218-231`（名前または ID による preset 解決と曖昧名の拒否）。
- 補助確認: checkout の `python strata.py presets apply --help` の表示。上記 parser 定義と照合済み。
