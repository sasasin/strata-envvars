# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `quick-benchmark` |
| コマンド | `tools/strata_bench.py`（`bench.sh` / `BENCH.bat` から起動可能） |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる |

## 役割

quick benchmark の進捗メッセージと通常の結果案内を抑制します。ベンチマークの実行、サーバーの利用・起動、レポート保存を無効化するフラグではありません。

## 使い方

Strata リポジトリのルートで次のように実行します。

```sh
python tools/strata_bench.py --quiet --url http://127.0.0.1:8080
```

`--url` は既に稼働している Strata サーバーを使う例です。`bench.sh` と `BENCH.bat` も引数を Python スクリプトへ渡します。

## 値と既定値

- `argparse` の `store_true` として登録されており、値や短縮 alias はありません。
- 省略時は偽（quiet 無効）、指定時は真です。追加の値を付ける構文ではありません。
- `--quiet` 自体に専用の validation はありません。未定義の値・引数の扱いは通常の `argparse` に従います。

## 実行時の動作

parser は `a.quiet` を使い、真なら `say` を何もしない関数、偽なら flush 付きの `print` 関数にします。モデル選択、サーバー確認または起動、計測、結果生成の通常経路で使う案内や進捗、Suite のログがこの `say` 経由のため、指定時は表示されません（`tools/strata_bench.py:932-950, 968, 984, 993-1007, 1019-1033`）。

quiet の有無にかかわらず、通常実行では結果ディレクトリを作り、`results.json` と `README.md`、ログがあれば `engine-log-excerpt.txt` を書き込みます。自動起動したサーバーも終了時に停止します（`tools/strata_bench.py:910-918, 1017-1018, 1035-1037`）。

`--compare-only` の経路では比較表を `say` でなく直接 `print` するため、`--quiet` を併用しても表は標準出力に残ります（`tools/strata_bench.py:951-955`）。また、設定不足、URL 先に Strata がいない、ポート競合、起動 timeout などのエラーは標準エラーへ直接出力され、quiet でも抑制されません（`tools/strata_bench.py:969-972, 985-999`）。

## 適用条件と副作用

このフラグは `tools/strata_bench.py` の表示関数にだけ作用します。計測内容・サーバー選択や起動・結果保存を切り替える分岐には使われていません（`tools/strata_bench.py:947-949, 982-1037`）。したがって、通常実行では quiet 指定時もベンチ処理とファイル出力は行われます。

ラッパー経由では、Python CLI を起動する前の案内はこのフラグの作用範囲外です。POSIX の `bench.sh` は `exec` 前に案内を `echo` し（`bench.sh:6-10`）、Windows の `BENCH.bat` も Python 起動前に案内を表示します（`BENCH.bat:8-16`）。Windows wrapper は終了時に `pause` も実行します（`BENCH.bat:17-19`）。ラッパーの準備不足メッセージも Python parser より前に出ます（`bench.sh:11-13`, `BENCH.bat:9-13`）。完全に無表示にしたい場合、wrapper を介さず `python tools/strata_bench.py --quiet ...` を実行してください。

## 出力とエラー

- quiet が抑制するのは `say` 経由の通常メッセージです。標準出力全体や標準エラー全体をリダイレクトする機能ではありません。
- `--compare-only` の比較表は標準出力に残ります。また parser の usage/error と上記の実行エラーは抑制されません（`tools/strata_bench.py:951-955, 969-999`）。
- quiet の指定自体に対応する警告や終了コード変更はありません。終了値は計測結果によって決まり、失敗があり、かつ chat / prompts / agent のいずれにも結果がない場合は `1`、それ以外は `0` です（`tools/strata_bench.py:1034`）。

## 根拠

- 索引上のツール ID とコマンド階層: `docs/cli/README.md:1522-1544`（調査対象の strata-envvars リポジトリ）。
- wrapper から委譲する対象の説明と利用者向け範囲: `tools/strata_bench.py:1-29`。
- parser、既定値、表示切替: `tools/strata_bench.py:932-950`。
- 比較表とエラー出力: `tools/strata_bench.py:951-999`。
- レポート作成および終了処理: `tools/strata_bench.py:910-918, 1017-1037`。
- wrapper の引数転送・事前表示: `bench.sh:6-13`, `BENCH.bat:8-19`。

調査対象 checkout の `git status --short --branch` は `## main...origin/main` で、未コミット変更は確認されませんでした。CLI の実行や `--help` の起動は行わず、同一 revision の parser と利用箇所をソース上で確認しました。
