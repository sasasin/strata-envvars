# `STRATA_BUILD_COMMIT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。調査対象は Strata 所有ソースで、外部ライブラリの動作は含めない。

## 役割

`STRATA_BUILD_COMMIT` は、Git メタデータがないソースツリーからターミナル配布アーカイブを作る場合に、元の Strata commit をパッケージ作成処理へ渡す値です。`packaging/package_terminal.py` がアーカイブ内の `COMMIT` ファイルへ値を書き、`strata_cli/bench_facts.py` が配布物の `COMMIT` を読み取って commit を特定します。標準ベンチマークは commit が不明なら非準拠理由を追加します。GPU エンジンの実行時動作を切り替える環境変数ではありません。

## 値と判定

Python の `build_commit()` は候補値を前後の空白を除いてから検査します。40 桁の ASCII 16 進数だけを受け付け、大文字小文字は区別せず、小文字に正規化して返します。空文字、桁数違い、16 進数以外の文字を含む値は候補として無視します。数値変換や部分一致はありません。

優先順位は次のとおりです。

| 順位 | 値 | 無効または未設定の場合 |
|---|---|---|
| 1 | `package_terminal.py --commit` の引数 | 次へ |
| 2 | `STRATA_COMMIT` | 次へ |
| 3 | `STRATA_BUILD_COMMIT` | 次へ |
| 4 | `git -C <ソースルート> rev-parse HEAD` | 40 桁の小文字 16 進数でなければ不明（`None`） |

明示的な空文字は候補として無視され、後順位の値に進みます。`STRATA_COMMIT` が有効なら `STRATA_BUILD_COMMIT` より優先されます。

## 有効になる条件

- 配布アーカイブ作成処理が `build_commit()` を呼び出すときに参照されます。
- Docker ビルドでは `docker/build.sh` が `STRATA_BUILD_COMMIT` を優先してソース commit とし、Docker build arg `STRATA_COMMIT` に渡します。`docker/Dockerfile` はこれを `ENV STRATA_BUILD_COMMIT=${STRATA_COMMIT}` として設定し、`package_terminal.py` を実行します。
- Docker 用シェルスクリプト側の判定は Python と異なります。`STRATA_BUILD_COMMIT` が未設定または空なら `git rev-parse HEAD` を試します。その後、空または小文字の 16 進数以外を含む値を空にしますが、40 桁ちょうどかどうかはここでは検証しません。大文字を含む値もここで空になります。最終的にパッケージ作成 Python が40桁形式を再検査します。
- Docker の build context では `.git` を含まないソースを使うため、有効な commit 値が引き継がれなければ Python 側の Git fallback は使えません。
- 変数が未設定でも、`package_terminal.py` が実際の Git checkout 内で動けば `git rev-parse HEAD` に fallback できます。Git checkout も有効な候補値もなく commit が特定できない場合、通常の配布ビルドは `SystemExit` で停止し、`COMMIT` を持たない配布物を作りません。`--skip-deps` のレイアウト確認では警告を出して続行し、`COMMIT` ファイルは作成しません。

## 実行時の詳細

`build_commit()` は呼び出しごとに引数と `os.environ` を参照し、値を static cache しません。アーカイブ作成の `main()` はこの結果が `None` でなければ、ステージング中のアーカイブルートに `COMMIT` という名前で小文字化済みの SHA と改行を書き込みます。環境変数の値自体は `COMMIT` ファイルへは転記されません。

Docker の `ENV` はターミナルステージに設定され、同ステージのパッケージ作成 `RUN` に値を渡します。確認した Strata ソース内では `STRATA_BUILD_COMMIT` の直接参照は `docker/build.sh`、`docker/Dockerfile`、`packaging/package_terminal.py` に限られ、サーバーやエンジンの実行時処理で読む箇所はありません。

## 根拠

- `packaging/package_terminal.py:284-300` — 候補の優先順位、空値処理、40桁16進数の検証、小文字化、Git fallback。
- `packaging/package_terminal.py:303-333,376-378` — `--commit` 引数、未知 commit 時の通常ビルド停止と `--skip-deps` 警告、`COMMIT` ファイル出力。
- `strata_cli/bench_facts.py:330-340`; `strata_cli/bench_standard.py:810-811` — 配布物の `COMMIT` 読み取りと、commit 不明時に標準ベンチマークが非準拠理由を記録する処理。
- `docker/build.sh:59-61,102-106` — Docker 用の値選択・文字制約と build arg の受け渡し。
- `docker/Dockerfile:33-41` — `.git` のないソースをコピーし、build arg から `STRATA_BUILD_COMMIT` を設定してパッケージ作成を実行。
