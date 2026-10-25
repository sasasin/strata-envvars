# `STRATA_COMMIT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。調査時の作業ツリーは clean。

## 役割

`packaging/package_terminal.py` がターミナル配布アーカイブの元になった Strata ソースの完全な Git commit SHA を決めるための環境変数。値が採用されると、アーカイブのルートに `COMMIT` ファイルとして書き込まれ、配布後の `strata bench run` がソース commit を報告できる。Strata のエンジンやサーバーの実行時動作を変える設定ではない。

## 値と判定

| 状態 | 処理 |
| --- | --- |
| `--commit` が有効な値 | 最優先で採用するため、環境変数は使わない。 |
| `--commit` が未指定または無効で、`STRATA_COMMIT` が有効 | `STRATA_COMMIT` を採用する。 |
| 上記がなく、`STRATA_BUILD_COMMIT` が有効 | `STRATA_BUILD_COMMIT` を採用する。これは Docker ビルドから渡す値。 |
| どの候補も有効でない | `git -C <ソースルート> rev-parse HEAD` を試す。得られた値が40桁の小文字16進数なら採用する。 |
| Git の実行ファイルがなく、または Git 出力も有効な SHA でない | commit を特定できず `None` になる。 |

候補文字列は前後の空白を除いてから、`[0-9a-fA-F]{40}` に全体一致するかを検査する。大文字を含む SHA も受け付け、保存前に小文字化する。40桁未満の短縮 SHA、40桁以外の文字列、空文字、空白だけの値は候補として採用されず、次の候補へ進む。先頭40桁だけを使うといった部分一致はしない。

候補の優先順位は `--commit` → `STRATA_COMMIT` → `STRATA_BUILD_COMMIT` → ソースツリーの Git HEAD。`STRATA_COMMIT` が無効でも `STRATA_BUILD_COMMIT` や Git HEAD に有効値があればそちらが使われる。

## 有効になる条件

対象は `packaging/package_terminal.py` によるターミナルアーカイブ作成経路だけ。通常の Strata サーバー、エンジン、CLI の起動時にこの環境変数を読むコードはない。Dockerfile はビルド引数 `STRATA_COMMIT` を受け、コンテナ内の `STRATA_BUILD_COMMIT` に設定する。Docker ビルドスクリプトはソースの commit を `--build-arg STRATA_COMMIT=...` として渡し、パッケージャーが `STRATA_BUILD_COMMIT` を候補にできるようにしている。

## 実行時の詳細

`main()` は引数を解析した後、`build_commit(args.commit)` を一度呼ぶ。`--skip-deps` を指定せず commit が得られなければ、`SystemExit` で「the commit of these sources is unknown ...」という理由を出し、配布可能なアーカイブ作成を止める。`--skip-deps` の場合は同じ理由を `warning: ` 付きで表示して続行するが、`COMMIT` ファイルは作られない。

commit が得られた場合、パッケージャーはアーカイブのルートにその SHA と改行を含む `COMMIT` ファイルを書いてからアーカイブ化する。ベンチマーク情報収集側は Git checkout でなければこのファイルを読み、値を検証して `strata_commit` / `runner_commit` に使う。値は `build_commit()` の呼び出し時に環境から読み取られるため、その後の環境変更はすでに決定した当該アーカイブには反映されない。

## 根拠

- `packaging/package_terminal.py:284-300`: SHA の形式、空白除去、小文字化、候補の順序、Git HEAD への fallback、および `source_commit()`。
- `packaging/package_terminal.py:311-313,327-333`: `--commit` 引数、優先して計算する箇所、値が不明な場合の停止または警告。
- `packaging/package_terminal.py:374-378`: commit が得られた場合に `COMMIT` ファイルを書き出す処理。
- `docker/Dockerfile:33-37`、`docker/build.sh:102-106`: Docker ビルド引数からパッケージャーの環境へ値を渡す経路。
- `strata_cli/bench_facts.py:330-340,378-380`: checkout がない配布物では `COMMIT` ファイルから値を読む処理と、値がない場合の記録上の扱い。
- `docs/BENCHMARK_PROTOCOL.md:326-332`: ベンチマーク記録の commit 出所と、値がない配布物の扱い。
