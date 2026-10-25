# `strata presets show --help`（alias: `-h`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets show` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ |

## 役割

`strata presets show` の使用法、必須の位置引数 `preset`、同じ parser が受け付ける `--output` を表示します。`--help` と `-h` はこの `show` サブコマンドの help を表示します。`strata presets` や別の `presets` サブコマンドの help とはスコープが異なります。

## 使い方

```sh
strata presets show --help
strata presets show -h
```

## 値と既定値

値は不要です。`strata` のトップレベル parser は標準の `argparse.ArgumentParser` で作成され、`presets show` も `add_parser("show", ...)` で作成されています。どちらも `add_help=False` を指定していないため、Python `argparse` が標準の `-h` / `--help` action を追加します。通常の表示オプション `--output` は `human` または `json` を受け付け、既定値は `human` ですが、help action 自体に値や既定値はありません。

## 実行時の動作

help action が選ばれると `argparse` がこの parser の使用法と help 文を標準出力へ出して終了します。通常のコマンド処理には進まず、preset の検索・読み出しや `--output` に応じた preset 内容の表示は行いません。通常実行時は必須位置引数 `preset` を id、4文字以上の id prefix、または大文字小文字を区別しない完全一致名として検索し、見つかった preset 全体を表示します。後者は help なしの実行経路であり、`--help` の動作ではありません。

CLI の `main()` は parser を構築して引数解析する前に `private_files.adopt_user_defaults()` を呼びます。この処理は Windows でのみユーザートークンの既定 owner / DACL を設定し、他 OS では何もしません。したがって help 表示でもこの前処理は通りますが、help action 自体は preset store を参照・変更しません。

## 適用条件と副作用

このオプションは `strata presets show` の parser で利用できます。preset id/name の指定は不要で、引数に誤りがなければ `show` の実処理へ進みません。`--help` だけでなく、コマンド起動時の前処理として前述の Windows token default 設定が試みられます。ソースには失敗時に例外を外へ送らない実装があり、help 表示を止めません。

## 出力とエラー

正常な help 表示は `argparse` による usage / 説明 / 引数一覧の標準出力で、help action が parser を終了させます（標準の終了 status は 0）。`--help` と `-h` の競合する複数指定や、help と `--output` の併記による出力形式の変更はソースで個別に定義されておらず、標準 `argparse` の処理に委ねられます。位置引数の不足や未知の引数など通常の parser error は `main()` の `parse_known_args()` 後に `ap.error()` へ渡されます。正確なエラー文・status は実行して照合していません。

## 根拠

- `strata_cli/cli.py:40-45` — 標準 `argparse.ArgumentParser` とトップレベル subparser の作成。
- `strata_cli/tune_commands.py:49-62` — `presets` / `show` parser の作成、共通 `--output`、必須位置引数 `preset`。`show` に独自の help 設定はありません。
- `strata_cli/cli.py:487` — `add_presets()` を Terminal CLI の parser に登録。
- `strata_cli/cli.py:2217-2231` — 引数解析前の Windows user-default 前処理、`parse_known_args()` と parser error の経路。
- `strata_control/private_files.py:349-385` — `adopt_user_defaults()` が Windows 以外では何もせず、Windows で owner / default DACL を設定する処理。
- `strata_cli/cli.py:2151-2153` — help action を通らず `presets` コマンドとして dispatch する通常経路。
- `strata_cli/tune_commands.py:289-309` — `show` の通常処理は `presets.find(a.preset)` と内容出力。
- `strata_control/presets.py:218-231` — preset の id / prefix / 名前検索、および見つからない・曖昧な場合の `PresetError`。

調査は上記 commit の parser と処理経路に限定しました。同 revision の実行可能 CLI の help 出力は実行しておらず、出力の具体的な整形は確認していません。
