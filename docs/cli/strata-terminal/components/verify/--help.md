# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components verify` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。引数 parser が組み込みの help action として登録する |

## 役割

`strata components verify` の usage と、このコマンドで受け付けるオプションを表示して終了します。`-h` は同じ help action の短縮別名です。トップレベルや `strata components` の help とは対象 parser が異なります。

## 使い方

```sh
strata components verify --help
```

source checkout では次の形の出力を確認しました（usage の折り返しは端末幅で変わります）。

```text
usage: strata components verify [-h] --profile PROFILE [--live]
                                [--output {human,json}] [--json] [--quiet]

options:
  -h, --help            show this help message and exit
  --profile PROFILE
  --live                query host GPUs and compare selected device indices
  --output {human,json}
  --json                alias for --output json
  --quiet               suppress human informational output
```

## 値と既定値

値を指定しません。help action が実行されると usage と説明を標準出力に表示し、parser を終了します。明示的な既定値はありません。`--help` 自体に値の validation はありません。

## 実行時の動作

`components` の subparser に `verify` parser が作られ、`--profile`、`--live`、`--output` が宣言されています。さらに one-shot コマンド共通の登録ループが `components_verify` に `--json` と `--quiet` を追加します。`argparse` の parser は既定で `-h` / `--help` を追加するため、この parser の help 表示にもそれらが現れます。

help action は引数解析中に実行されて parser を終了するので、通常の `_run()` dispatch や component 検査には進みません。従って `--profile` が必須でも、`strata components verify --help` は profile を要求せず help を表示します。`--json`、`--quiet`、`--output` を併記しても help action の表示形式は変わりません。

## 適用条件と副作用

この help は `components verify` parser のみを説明します。たとえば `strata components --help` は親 parser の別の help です。

`strata_cli.cli.main()` は parse の前に `private_files.adopt_user_defaults()` を呼びます。POSIX では同関数は何もしません。Windows では、昇格プロセスが後で作るファイルの既定 owner と DACL をユーザー向けに設定しようとします（失敗時も例外を外へ送出しない実装です）。この起動時処理は help action より前に実行されます。一方、`components verify` の component/profile 検査自体は help では実行されません。

## 出力とエラー

通常の help 表示は標準出力に行われ、同一 revision の source CLI で確認した呼び出しは終了コード 0 でした。help を指定せず `--profile` を省略した場合や認識されない引数を渡した場合は parser error となり、usage とエラーを標準エラーに出して終了コード 2 になります。`--help` はその parse error より先に処理されます。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser と argparse の既定 help action を持つ parser 構築。
- `strata_cli/cli.py:114-119` — `components verify` parser、必須 `--profile`、`--live`、`--output` の定義。
- `strata_cli/cli.py:508-515` — `components_verify` への共通 `--json` / `--quiet` 追加。
- `strata_cli/cli.py:2217-2237` — parse 前の起動処理、引数解析、通常 dispatch。
- `strata_cli/cli.py:1023-1045` — 通常 dispatch 後に呼ばれる component 検査と出力。help action ではここへ到達しない。
- `strata_control/private_files.py:349-380` — `adopt_user_defaults()` の Windows 向け処理と POSIX での no-op 条件。
- 同一 revision の `python strata.py components verify --help` — 上記の usage とオプション一覧を照合。調査補助として source CLI の help のみ実行しました。
