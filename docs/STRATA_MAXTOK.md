# `STRATA_MAXTOK`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

この HEAD の Strata 本体ソースには `STRATA_MAXTOK` の読み取り箇所がなく、Strata 実行ファイルの挙動を制御する環境変数としては確認できませんでした。調査した `src`、`include`、`sycl`、`serve`、`setup.py`、`tools` などの Strata 所有コードから完全一致の参照は見つかりません。

名前の出現は `bench/results/2026-10-04-community-2x-rtx3060/bench.py` と `bench-0.1.39.py` に限られます。これらは `bench/results/` 内のベンチマーク記録に属するため、調査手順の規定に従い、Strata 本体の実装根拠には含めません。

## 値と判定

Strata 本体での未設定値、空文字、値の parse、無効値時の fallback は該当コードがなく、定義されていません。

参考情報として、除外対象の2つのベンチマークスクリプトでは `int(os.environ.get("STRATA_MAXTOK", "256"))` と読み取っています。したがって、そのスクリプト内に限れば未設定時は整数 `256`、設定時は Python の `int()` 変換が使われ、整数に変換できない値は例外になります。変数はスクリプトの HTTP リクエストに含める `max_tokens` および記録する protocol 値に使われています。この挙動を Strata サーバーや実行ファイルの環境変数仕様として一般化できません。

## 有効になる条件

Strata 本体で有効になる条件や、CLI・設定ファイル・他の環境変数との優先順位は確認できませんでした。ベンチマークスクリプト側では、スクリプト実行時にのみ上記の値が使われます。

## 実行時の詳細

Strata 本体では読み取り時期、キャッシュ、子プロセスへの転送、ログ、警告、エラーなど、`STRATA_MAXTOK` による実行時処理は確認できませんでした。

ベンチマークスクリプトではモジュール読み込み時に値を整数化し、その値を非ストリーミングおよびストリーミングのリクエストの `max_tokens` に設定し、protocol 情報にも記録します。これはベンチマーククライアントの動作です。

## 根拠

- 候補一覧: 作業リポジトリ `docs/000_envvers.md:335`。
- 対象 HEAD と作業ツリー: 調査対象リポジトリで `git rev-parse HEAD` は上記 SHA、`git status --short --branch` は `## main...origin/main`。
- 本体ソース検索: `STRATA_MAXTOK` の完全一致で `bench/results/` を除外した検索では参照なし。
- 除外対象スクリプトでの記述と用途: `bench/results/2026-10-04-community-2x-rtx3060/bench.py:21,46,119,152,202` および `bench-0.1.39.py:21,46,119,152,202`。

本調査の結論は上記 HEAD の Strata 所有コードに限ります。ベンチマーク記録以外の外部コードや過去 revision の挙動は対象外です。
