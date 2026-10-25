# `STRATA_TEST_RAM`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Strata 本体の実行設定ではなく、`bench/results` に置かれた community benchmark 用 Python スクリプトが、native engine のログを置くディレクトリを指定する。対象 revision の `src`、`include`、`serve` など本体ソースにはこの名前の読み取りがない。実行中の Strata バイナリがこの変数を読んで動作を変える根拠は確認できない。

## 値と判定

| 読み取り箇所 | 未設定 | 設定時 | CLI との優先順位 |
|---|---|---|---|
| `2026-10-05-community-arc-b65/benchmark.py`、`2026-10-07-community-arc-b65-v01402/benchmark.py`、同じ場所の `frozen-community.py` | `os.environ.get()` の fallback `/run/strata-community` を `Path` にする | 値を文字列として `Path` に渡す。数値変換や文字列検証はしない | `--ram` が明示された場合は argparse の値が環境変数由来の default を上書きする |
| `2026-10-07-community-arc-b65-v01402/public-fixtures.py` | `os.environ['STRATA_TEST_RAM']` が `KeyError` を送出する | 値を文字列として `Path` に渡す | `--ram` オプションはなく、環境変数を直接使う |

前者3スクリプトでは `args.ram.resolve()` の文字列表現が `/run/` で始まることと、`args.ram.is_dir()` が真であることを `assert` で要求する。従って相対パス、空文字、存在しないディレクトリなどは、resolve 後の場所や実在性に応じて assertion に失敗する。空文字は `Path('')`（カレントディレクトリ相当）となり、専用の空値処理はない。`/run` 自体は文字列が `/run/` で始まらないため、この prefix 条件を通らない。

## 有効になる条件

値を使うのは上記の benchmark スクリプトを実行する場合に限られる。前者3スクリプトでは有効なディレクトリが必要で、ディレクトリの作成はこの変数用には行わない。`--ram` を指定すれば環境変数の値は採用されない。`public-fixtures.py` は `/run/` prefix やディレクトリ存在の事前検査をせず、環境変数から得た場所にログを作ろうとする。

## 実行時の詳細

前者3スクリプトは選択した RAM ディレクトリの下に `native-1.log` などのログパスを組み立て、`StrataEngine` に `log` 引数として渡す。`public-fixtures.py` は同様に `native.log` と `native-1.log` などを組み立てる。後者は `STRATA_TEST_RAM` を `main()` の実行時に読み、前者も `main()` 内で argparse の default を設定するときに一度読み取る。プロセス起動後の環境変更を再読する処理はない。

engine 起動時にはこれらのスクリプトが `dict(os.environ)`（または環境辞書 `env`）を `StrataEngine` に渡すため、変数自体は子プロセスの環境にも含まれ得る。しかし調査した Strata 本体側に `STRATA_TEST_RAM` の読み取りはなく、本体への転送が本体の挙動を変えるとは説明できない。観測される主な差は、Python 側がログパスを選ぶことと、パス検査またはファイル操作が失敗した場合に例外・assertion で処理が止まること。

## 根拠

- `bench/results/2026-10-05-community-arc-b65/benchmark.py:32-43,160-165` — `--ram` default、`/run/` prefix と存在確認、ログパス、および engine 起動時の環境辞書。
- `bench/results/2026-10-07-community-arc-b65-v01402/benchmark.py:32-43,164-169` — 同じ default、検査、ログパスの使い方。
- `bench/results/2026-10-07-community-arc-b65-v01402/frozen-community.py:32-43,154-159` — 同じ default、検査、ログパスの使い方。
- `bench/results/2026-10-07-community-arc-b65-v01402/public-fixtures.py:12-19,57,106-110` — 必須の環境変数参照と RAM ディレクトリ配下のログパス。
- 同ファイル群以外の Strata ソースを含むリポジトリ全体を名前で検索した結果、この環境変数の追加読み取り箇所は見つからなかった。
