# `STRATA_HANDOVER`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

この変数は、Control のコマンドを新しい Control へ引き継いだ後、引き継ぎ先で再度引き継ぎ処理を始めないためのループ防止フラグです。`strata.py` の起動時に `STRATA_HANDOVER` が空でない値なら、更新先を探す前に現在の Control の処理を続けます。利用者がこの変数を設定しても、引き継ぎ機能を有効化する指定にはなりません。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | ガードなし。ほかの条件を満たせば引き継ぎ先を調べる |
| 空文字 | Python の真偽値が偽となるためガードなし |
| 空でない任意の文字列 | 真となり、引き継ぎ先の探索をせず現在の Control を続行 |

文字列比較や数値変換は行いません。`"0"`、`"false"`、`"1"` はいずれも空でないため同じくガードとして働きます。判定は `maybe_hand_over()` の呼び出しごとに `environ.get()` で行われます。通常の CLI ではプロセス起動時に一度実行されるため、その起動時の環境値が使われます。

## 有効になる条件

`STRATA_HANDOVER` が未設定または空文字でも、実際の引き継ぎには次の条件が必要です。

- `STRATA_NO_HANDOVER` が未設定または空文字である。これも設定有無ではなく、空でないかどうかで判定される。
- 通常のソースチェックアウト起動ではない。`strata.py` は `.git` があるソースチェックアウトからの起動時に引き継ぎを行わない。コード上のテスト用フック `STRATA_HANDOVER_IN_CHECKOUT` が空でない場合は、この制限を迂回する。
- `active.json` から得た Control のバージョンが、現在の Control のバージョンより新しく、更新先のバンドル Python、`strata.py`、`strata_control` ディレクトリが揃っている。

更新先が存在しない、同じか古い、またはポインター情報を読めない場合は通常どおり現在の Control が続行します。更新先が新しいと特定できたのに破損している場合は、stderr に警告を1行出して現在の Control に戻ります。

## 実行時の詳細

`strata.py` は `strata_cli.cli` などの重い import より前に `maybe_hand_over(sys.argv[1:])` を呼びます。引き継ぎ処理は、既定では `STRATA_COMPONENTS_DIR` 配下の `control/active.json` を読みます。同変数が空でない場合はそのパスを使い、未設定または空文字なら OS ごとのユーザーコンポーネントディレクトリを使います。ポインター先のフォルダー名と解決後の親ディレクトリを検査し、Control ディレクトリ外を指すポインターを拒否します。バージョンはフォルダー内の `VERSION`、次に `BUNDLE.json` を優先し、いずれも有効でなければポインターの `version` を使います。

引き継ぎが決まると、更新先の同梱 Python と `strata.py` を使い、元の CLI 引数をそのまま渡します。子プロセス環境には `STRATA_HANDOVER=1` を設定し、`PYTHONNOUSERSITE=1` を加え、`PYTHONHOME` と `PYTHONPATH` を除きます。POSIX では `execve` で現在のプロセスを置き換え、Windows では subprocess を実行してその終了コードを返します。起動に失敗した場合は stderr に警告を出して現在の Control を続けます。Windows の子プロセスが Ctrl-C で中断された場合は終了コード 130 を返します。

また、`strata update` がステージした Control の `--version` を検査する際にも、子プロセス環境へ `STRATA_HANDOVER=1` を設定します。これは検査対象が別のアクティブ Control へ再引き継ぎするのを防ぎます。

## 根拠

- `strata.py:30-39` — CLI 起動時、heavy import 前の呼び出し位置。
- `strata_cli/handover.py:22-24,126-146` — 環境変数名、ガード、ソースチェックアウト条件、警告と fallback。
- `strata_cli/handover.py:34-43,70-114` — コンポーネントディレクトリ、active pointer、バージョン比較、更新先の完全性とパス検査。
- `strata_cli/handover.py:117-123,148-162` — 子プロセス環境、POSIX/Windows の起動方法、失敗時の fallback。
- `strata_control/updater.py:963-981` — staged Control の `--version` 検査時に `STRATA_HANDOVER=1` を渡す箇所。
