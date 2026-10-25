# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engine` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 値を取らない |

## 役割

`strata components engine` の使い方と、その parser に登録されたオプションを表示して終了します。これは `strata --help` や `strata components --help` とは別のスコープです。`engine` parser 自体は、ローカルの component folder からこの PC が起動する engine package を調べるコマンドとして登録されています（`strata_cli/cli.py:114-115,132-138`）。

## 使い方

```sh
strata components engine --help
# または
strata components engine -h
```

## 値と既定値

`--help` と `-h` は値を取りません。`components_engine.add_argument(...)` に help option の個別定義はありませんが、最上位 parser は `argparse.ArgumentParser(...)` で作成され、各階層の parser は `add_subparsers(...).add_parser(...)` で作成されています。`add_help=False` の指定もないため、Python `argparse` が既定で各 parser に `-h` / `--help` を追加します（`strata_cli/cli.py:40-41,114-115,132-133`）。この parser に固有の値、既定値、または値の validation はありません。

## 実行時の動作

`--help` / `-h` を指定すると `argparse` が engine parser のヘルプを stdout に出し、通常の引数処理を終了します。このため `--backend`、`--components-dir`、`--full`、`--output` などの値に応じた処理や、engine component の状態確認には進みません。通常実行時は `main()` が `parse_known_args()` を呼び、その後 `components engine` を `_components_engine()` に振り分けます（`strata_cli/cli.py:2217-2225,2129-2134`）。`_components_engine()` が component 状態を取得して出力するのは、この通常経路に限られます（`strata_cli/cli.py:2014-2041`）。

オプションの位置は `engine` の後です。トップレベルまたは `components` の `--help` を使うと、それぞれの階層のヘルプになります（parser 階層: `strata_cli/cli.py:40-46,114-115,132-133`）。同じ呼び出しで他の engine option を並べても、ヘルプ action が終了するため、それらを使った状態確認は実行されません。

## 適用条件と副作用

help action 自体は、engine package の scan・解決・ファイル hash、download、unpack、更新を行いません。これらの処理に対応する通常経路は `_components_engine()` から `engine_component.status(...)` を呼び出します（`strata_cli/cli.py:2014-2023`; `strata_control/engine_component.py:969-987`）。

起動経路全体では、ソース checkout の `strata.py` は `refuse_old_updater()` と `maybe_hand_over()` の確認後に CLI を読み込みます（`strata.py:30-43`）。ただし handover 実装は通常の source checkout から実行する場合に installed Control への切り替えを行いません（`strata_cli/handover.py:126-134`）。また `main()` は parser を作る前に `private_files.adopt_user_defaults()` を呼びます。これは Windows でプロセスの既定 owner/ACL を設定する処理で、他 OS では何もしません（`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-358`）。これは `--help` action 自体の副作用ではなく、CLI 起動時の前処理です。

## 出力とエラー

ヘルプ本文は stdout に出ます。`argparse` の既定 help action は表示後に成功として parser を終了します。通常引数の parse に進んだ場合、未知引数は `ap.error(...)` に渡されるため、usage とエラーを出して終了コード 2 になります（`strata_cli/cli.py:2223-2231`）。help option に対する Strata 独自の warning、JSON 出力、または専用エラー処理は確認できません。

## 根拠

- parser 階層と engine parser の説明: `strata_cli/cli.py:40-46,114-115,132-138`
- `parse_known_args()`、未知引数の処理、通常コマンドへの dispatch: `strata_cli/cli.py:2217-2231,2129-2134`
- 通常の engine component 確認と出力: `strata_cli/cli.py:2014-2041`; 状態取得: `strata_control/engine_component.py:969-987`
- 起動前処理と checkout handover 条件: `strata.py:30-43`; `strata_cli/handover.py:126-134`; `strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-358`

調査対象 checkout で既存 CLI の `--help` は実行せず、parser と dispatch のソースを確認しました。表示文言の実行時確認や異なる Python `argparse` バージョンでの整形差は調査範囲外です。
