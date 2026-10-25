# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない（help 表示 action） |

## 役割

`strata components update` の usage と、このコマンドで受理されるオプションを表示して終了します。トップレベルや別コマンドの help とは別の parser scope です。索引のリンク先も `components/update` に配置されています。

## 使い方

```sh
python strata.py components update --help
# 同じ parser action の短縮別名
python strata.py components update -h
```

Strata の source checkout のルートで実行する例です。配布済み CLI では `strata components update --help` とします。

## 値と既定値

値は不要な真偽スイッチです。Strata は `argparse.ArgumentParser` とサブコマンドの `add_parser()` を使い、`add_help=False` を指定せず、help action を独自定義していません。このため Python `argparse` の標準 `-h` / `--help` action が適用されます。help 専用の既定値、値検証、重複指定時の追加処理は Strata 側にありません。

## 実行時の動作

この parser の help は `strata components update` の使用法とオプション一覧を表示します。一覧の根拠となる宣言は共通項目 `--feed`、`--components-dir`、`--backend`、`--wait`、`--force`、`--model-config`、`--output` と、update 固有の `--check`、`--app`、`--app-version`、`--no-engine`、`--no-control` です。各 option の値や更新動作の詳細はそれぞれの個別文書を参照してください。

`main()` は parser の結果を `_run()` に渡す前に解析します。標準 help action は解析中に表示して終了するため、`update_cmd.run()`、feed の読み込み、更新チェック、ダウンロード、インストールには進みません。`--help` は `--output` 等の出力形式によって変更されません。

## 適用条件と副作用

help action 自体は引数を検証・変換したり、コンポーネントやサーバーを変更したりしません。通常の `strata.py` 起動では parser より前に `refuse_old_updater()` / `maybe_hand_over()` が呼ばれますが、source checkout では `maybe_hand_over()` が checkout を検出して委譲を行わず、`components` は entry point の preflight による追加処理対象（`serve`、`bench`）ではありません。また `main()` の冒頭で呼ぶ `adopt_user_defaults()` は Windows のプロセストークンの既定 owner / DACL を調整する処理で、他 OS では何もしません。したがって配布 CLI では実行環境によって parser 到達前に新しい Control へ委譲されることがあります。

## 出力とエラー

標準 `argparse` の help action は help を stdout に表示して終了コード 0 で終了します。構文エラーなど help 以外の parser エラーは `argparse` の usage / error を stderr に出し、標準の終了コード 2 で終了します。Strata の `_run()` の例外処理や updater 固有の終了コードには到達しません。

この文書では同一 revision の CLI を起動して実際の表示幅・整形済み出力は採取していません。記載した一覧は parser の定義に基づきます。

## 根拠

- Strata `strata_cli/cli.py:40-46,114-116,139-140` — ルート parser と `components` の parser、`update_cmd.add_parsers()` の登録。
- Strata `strata_cli/update_cmd.py:30-40,42-59` — 共通オプションと `components update` 固有オプションの定義。`--help` を個別に再定義していない。
- Strata `strata_cli/cli.py:2217-2237` — parser 生成、`parse_known_args()`、解析後に `_run()` へ進む処理順。
- Strata `strata.py:14-18,30-43` — `serve` / `bench` に限る preflight と、CLI parser の前に行われる handover / preflight 呼び出し。
- Strata `strata_cli/handover.py:27-29,126-158` — checkout 判定と、適用時の Control 委譲処理。
- Strata `strata_control/private_files.py:349-389` — `adopt_user_defaults()` が Windows のプロセストークン既定値を扱い、他 OS では早期 return すること。
- `argparse` 標準動作については、この checkout の parser 構築が標準 help 設定を無効化・置換していないことを確認。実行時の help 出力は未採取。
