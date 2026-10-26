# `RUNNER_TEMP`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

この候補名は Strata の実行時設定ではなく、GitHub Actions workflow が CI 中の一時ファイルや Python 仮想環境の配置先を組み立てるために読む。Strata のエンジン、サーバー、通常の CLI が `RUNNER_TEMP` を読む実装は確認できなかった。

## 値と判定

workflow 内の Python は `os.environ['RUNNER_TEMP']` で値を取得し、その文字列を `pathlib.Path` に渡す。値の独自 parse、空文字の検査、既定値、fallback、範囲制限はない。変数が環境にない場合、この添字参照は Python の `KeyError` になる。shell の `$RUNNER_TEMP` 参照には、workflow 内で別の fallback を設けていない。

## 有効になる条件

GitHub Actions の二つの workflow の該当 job/step が実行される場合に限る。アプリケーションの設定、起動時オプション、GPU/backend の選択には関与しない。

## 実行時の詳細

- `terminal-portable-monitor.yml` は `RUNNER_TEMP` の下に `minimal-cli-smoke.json` を置き、monitor の `.pyz` bundle と複数の smoke-test report も同じディレクトリに置く。対象 job は Ubuntu/Windows と Python 3.10/3.11 の matrix である。
- `terminal-minimal-server.yml` は同変数の下に `strata-runtime-venv` を作り、その Python で server smoke test と server test suite を実行する。また `minimal-server-smoke.json` を配置する。
- inline Python の `os.environ[...]` は各 step が走るときに評価される。値は子プロセスに渡す report パスや Python 実行ファイルのパスを作るために使われる。

## 根拠

- `.github/workflows/terminal-portable-monitor.yml:33-41` は client job と OS/Python matrix を定義する。同ファイル `:58-60` は CLI report パスを、`:72-78`, `:93-99`, `:110-114` は bundle/report パスを `RUNNER_TEMP` から作る。
- `.github/workflows/terminal-minimal-server.yml:31-42` は Linux の fake-engine job を定義する。同ファイル `:46-47` は venv の作成と利用を、`:56-60` は smoke report と venv Python のパス作成を、`:62-65` はその Python による server test suite 実行を示す。
- リポジトリ全体で `RUNNER_TEMP` の参照を検索し、上記二つの workflow 以外に該当する読み取り箇所がないことを確認した。
