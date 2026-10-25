# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune run` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ |

## 役割

`strata tune run` 専用の使い方と、この parser に登録された引数を表示する。`--help` は `argparse.ArgumentParser` の既定動作で追加されるため、run parser の明示的な `add_argument()` 宣言はない。run parser は tune サブコマンド階層の中で作られており、トップレベルや `strata tune` 自体のヘルプとは別スコープである（`strata_cli/cli.py:395-396,414-415`）。

## 使い方

```sh
strata tune run --help
```

短縮別名も同じヘルプを表示する。

```sh
strata tune run -h
```

## 値と既定値

値は不要。`--help` と `-h` は同一 parser の同じヘルプ表示 action で、別の既定値や値の validation はない。ヘルプ本文には run parser に定義されたオプションと各説明が反映される（`strata_cli/cli.py:414-459`）。

## 実行時の動作

CLI の `main()` は parser を作成して `parse_known_args()` を呼ぶ。ヘルプ action は引数解析中にヘルプを出力し、成功ステータスで parser を終了させるため、`_run()` や tune の実行分岐、エンジン計測、ジョブ保存には進まない（`strata_cli/cli.py:2217-2225`; run 分岐は `strata_cli/cli.py:1708-1709`、計測とジョブ実行は `strata_cli/cli.py:1757-1803`）。

## 適用条件と副作用

このヘルプは `run` の下に限られる。`strata tune --help` は tune 全体のヘルプを表示する。`run` の計測条件や `--mode` などの値検査はヘルプ表示では行われない。

通常の `strata.py` 入口では、CLI parser の前に handover 判定と preflight を通る。`tune run` は `serve` / `bench` 向け依存パッケージ preflight の対象外。さらに `main()` は parser 構築前に `private_files.adopt_user_defaults()` を試みるが、これは Windows でプロセスの既定ファイル所有者・ACL をユーザー向けに設定する処理で、他 OS では何もしない。ヘルプ処理自体がチューニング job、モデル、プロファイルを変更する処理はない（`strata.py:30-43`; `strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-357`）。

## 出力とエラー

通常の argparse ヘルプ本文は標準出力に表示され、終了コード `0` で終了する。通常の引数エラーは `main()` の後続処理で `ap.error()` に渡されるため、使用法を標準エラーに表示して終了コード `2` となる（`strata_cli/cli.py:2223-2231`）。ヘルプ表示では `tune run` の計測結果や JSON report は出力しない。

## 根拠

- `strata_cli/cli.py:395-396` — `tune` parser と必須サブコマンド parser の作成。
- `strata_cli/cli.py:414-459` — `run` parser の作成と、その parser に属する引数。
- `strata_cli/cli.py:2217-2231` — `main()` の事前処理、引数解析、未知引数のエラー経路。
- `strata_cli/cli.py:1708-1709,1757-1803` — 通常実行時の分岐、計測方法の準備と job 実行。
- `strata.py:30-43` — Terminal CLI の入口、handover と preflight。
- `strata_control/private_files.py:349-357` — Windows におけるプロセスの既定所有者・ACL 設定。

調査対象 checkout は `git status --short --branch` で `## main...origin/main` と確認し、未コミット変更は表示されなかった。CLI を実行して help 出力を採取することはせず、実装ソースの parser 定義と制御フローを根拠とした。
