# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets rename` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ |

## 役割

`strata presets rename` の argparse が生成する使い方と、そのサブコマンドで有効な引数・オプションを表示して終了します。Terminal CLI のトップレベルや他の `presets` サブコマンドの help とは別スコープです。

## 使い方

```sh
strata presets rename --help
strata presets rename -h
```

## 値と既定値

値は不要です。`strata presets` と `rename` は `argparse` の `add_parser()` で作られ、`add_help=False` の指定はありません。このため標準の `--help` と `-h` が有効です。`rename` parser には位置引数 `preset` と `name`、共通オプション `--output {human,json}`（既定値 `human`）が定義されています。help はこれらの位置引数を指定しなくても表示でき、`--output` の値は help 表示形式を切り替えません。

## 実行時の動作

`strata_cli.cli.parser()` が `add_presets()` を root parser に登録し、そこで `presets` の必須サブコマンドと `rename` parser を構成します。`--help` / `-h` は `rename` の処理関数へ進む前に argparse が help を出力して終了するため、`presets.rename()` は呼び出されず、プリセット名の検索・変更やプリセットファイルの書き込みは行いません。

ただし CLI の `main()` は parser を呼ぶ前に `private_files.adopt_user_defaults()` を呼び出します。これは Windows では現在のプロセスの既定 owner / DACL を設定しようとし、Windows 以外では何もしません。従って Windows では help 表示でもこのプロセス設定処理は通りますが、ソース上、help 自体がプリセット保存データを変更する経路はありません。

## 適用条件と副作用

- `strata presets rename` の parser に対してのみ適用されます。`strata presets --help` は親コマンドの help、`strata --help` は root help を表示します。
- 通常実行では `preset` と `name` が必要です。help を指定した場合、parser の help action が先に終了するため、これらの値を省略できます。
- help 表示は argparse の標準出力を使い、プリセットストアを読み書きしません。Windows での CLI 起動前処理については「実行時の動作」を参照してください。

## 出力とエラー

argparse がこの parser の usage、`--help` / `-h`、`--output {human,json}`、位置引数 `preset` と `name` を表示し、正常終了します。help の具体的な折り返しは実行環境の表示幅などに依存するため、固定の出力全文は記載しません。

通常実行時に必須位置引数が欠ける、または未知の引数がある場合は、argparse の parser error 経路になります。`main()` は未知引数を検出すると `ap.error()` に渡します。これらのエラー出力は help 表示とは別経路です。

## 根拠

- `strata_cli/tune_commands.py:49-67` — `presets` / `rename` parser、`preset`・`name` 位置引数、共通の `--output` 定義。
- `strata_cli/cli.py:40-45,487-488` — Terminal CLI root parser と `presets` parser の登録。
- `strata_cli/cli.py:2217-2231` — parser より前の起動処理、引数解析、未知引数の parser error 経路。
- `strata_cli/cli.py:2151-2153` — 通常実行時に `presets_command()` へ委譲する分岐。
- `strata_cli/tune_commands.py:314-316` — 通常の rename 処理でプリセット名変更を呼び出す箇所。
- `strata_control/presets.py:349-389` — Windows の `adopt_user_defaults()` はプロセスの既定 owner / DACL を設定しようとし、非 Windows では `False` を返す。
- `strata_control/presets.py:361-371` — プリセットの rename は名前を検証し、保存 JSON を書き換える処理。help 経路からは呼ばれません。

調査は上記 revision のソースに基づきます。同一 revision の CLI help は実行しておらず、出力の詳細は parser 定義から確認できる範囲に限定しています。
