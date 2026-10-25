# `strata ops edit --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops edit` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし。ヘルプ表示用のフラグ。 |

## 役割

`strata ops edit` の引数形式と、その parser に登録されたオプションを表示する。`ops` の各サブコマンド parser は `argparse` の `add_parser()` で作られ、`--help` と `-h` は `argparse` が自動で追加する。

## 使い方

```sh
strata ops edit --help
```

短縮形は `strata ops edit -h`。表示される usage は `strata ops edit [-h] --profile PROFILE [--output {human,json}] [--json] [--quiet] name`。通常の編集呼び出しには位置引数 `name` と必須の `--profile PROFILE` が必要だが、ヘルプ表示時は編集処理に進まない。

## 値と既定値

値は取らない。`--help` の適用範囲は `ops edit` の parser であり、`strata --help` や他のサブコマンドのヘルプとは別である。対象 parser は `name`、必須の `--profile`、`--output`（`human` または `json`、既定 `human`）を登録する。one-shot parser 共通の `--json` と `--quiet` も表示される。

## 実行時の動作

CLI は parser を構築して引数を解析した後にコマンド dispatch を行う。`--help` を指定すると parser が usage と説明を標準出力に表示して終了するため、`recipes.edit()` は呼び出されず、レシピの読み込み・編集・保存や一時ファイル作成は起きない。ヘルプ出力は同一 revision の `python strata.py ops edit --help` でも照合した。

## 適用条件と副作用

ヘルプ表示は `strata ops edit` の引数 parser に限られる。`ops edit` 自体を実行する場合は `--profile` と `name` が必要で、`recipes.edit()` が `VISUAL` または `EDITOR` のエディタ起動やレシピ保存を扱うが、`--help` ではその経路に入りません。

## 出力とエラー

確認した同一 revision の CLI 出力では、usage と引数説明が標準出力に表示された。通常の `argparse` ヘルプ動作として表示後に終了し、終了コードは 0。ヘルプ表示自体に Strata 固有の警告やファイル出力はない。未知の引数は `main()` の引数解析後に `ap.error()` へ送られ、parser エラーとして扱われる。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser とサブコマンド parser の構築。
- `strata_cli/cli.py:255-267` — `ops` と `edit` を含む各 action parser、`name` / `--profile` / `--output` の定義。
- `strata_cli/cli.py:508-516` — one-shot parser に共通の `--json` と `--quiet` の追加。
- `strata_cli/cli.py:2217-2231` — parser 構築後の引数解析と parser エラー経路。
- `strata_cli/cli.py:1416-1422` — ヘルプでなく `ops edit` が dispatch された場合の `recipes.edit()` 呼び出し。
- `strata_control/recipes.py:299-326` — `ops edit` 実処理における `VISUAL` / `EDITOR`、一時 JSON、保存、編集失敗時の draft 保持。
