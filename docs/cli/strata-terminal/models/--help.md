# `strata models --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout の状態は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ |

## 役割

`models` コマンドの使用法と、その直下のサブコマンド（`list`、`inspect`、`import`、`move`）を表示します。この文書は `strata models` parser の help を対象にします。たとえば `strata models list --help` は別の parser の help です。

## 使い方

```sh
strata models --help
strata models -h
```

## 値と既定値

引数値は不要です。`strata_cli.cli.parser()` はトップレベル parser を `argparse.ArgumentParser(...)` で作り、`models` parser を `sp.add_parser("models", ...)` で追加しています。どちらも `add_help=False` を指定していないため、Python `argparse` の既定 help action（`-h` と `--help`）が有効です。Strata 独自の既定値・値検証・複数回指定時の処理はありません。

## 実行時の動作

help action は `models` parser の使用法、説明文「inspect setup-written local model run configs」、および登録済みのサブコマンドを表示して引数解析を終了します。通常の `models` 処理（モデル一覧取得、検査、import plan、ファイル移動）には進みません。`models` parser はサブコマンドを `required=True` で定義していますが、help はサブコマンドを指定しなくても表示できます。

この option は `models` の parser に限られます。子 parser の help はそれぞれの parser が持つもので、表示範囲も異なります。

## 適用条件と副作用

- `strata.py` 経由では、CLI parser の作成・引数解析より先に `private_files.adopt_user_defaults()` が呼ばれます。この関数は Windows でプロセス token の既定 owner / DACL 設定を試み、POSIX では何もしません。失敗しても例外を外へ出さない実装です。したがって `--help` がモデルファイルを変更する処理はありませんが、Windows ではこの前段処理が実行されます。
- `strata.py` は `maybe_hand_over()` で新しい Control への引き継ぎを試みます。ただしソース checkout からの起動では引き継ぎ先探索を行わず現在のコードを使う条件があります。配布・インストール環境で引き継ぎが成立する場合は、実際に help を表示する revision が切り替わる可能性があります。
- 調査時には help を実行していません。端末幅による折り返しを含む実際の表示は確認していません。

## 出力とエラー

`argparse` の標準 help action により usage と help 文が標準出力へ表示され、解析は終了コード `0` で終わります。表示の具体的な整形は端末幅などに依存します。`--help` 自体に値を付けた場合の拒否や、`strata models` だけを実行して必須サブコマンドがない場合の usage error は、help action とは別の parser エラー経路です。実際の出力文面・stderr の改行や終了コードを Strata 固有コードからは確認できないため、ここでは `argparse` の既定動作として記載しています。

## 根拠

- 索引での配置と scope: `docs/cli/README.md:264-284`（`strata models` と `strata models list` を別階層として列挙）。
- parser とサブコマンド定義: `strata_cli/cli.py:40-46`（トップレベル `ArgumentParser` と subparsers）、`strata_cli/cli.py:141-171`（`models` parser、必須サブコマンド、各子 parser）。`add_help` を上書きしていないことから既定 help action が有効です。
- parse と通常 dispatch の順序: `strata_cli/cli.py:2217-2237`（前処理後に `parse_known_args()`、解析後に `_run()`）。help action は argparse 解析中に終了するため `_run()` には到達しません。
- Windows 前処理: `strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-388`。
- CLI entrypoint と handover / preflight: `strata.py:30-43`、`strata_cli/handover.py:126-164`。checkout での handover 抑止条件は `strata_cli/handover.py:129-134`。
