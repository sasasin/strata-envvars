# `ENGINE_VERSION`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

これは実行中の Strata engine が読む環境変数ではなく、ソースから engine component を作る `Dockerfile` 専用の Docker build argument です。指定すると、作成する engine component のバージョン表示を上書きします。Dockerfile では `ARG ENGINE_VERSION=` と宣言され、後続の `RUN` 内で shell 変数として参照されます（`Dockerfile:31-34,51-65`）。

## 値と判定

`ENGINE_VERSION` を文字列として検証・変換する処理はありません。shell の `${ENGINE_VERSION:-fallback}` 展開により、未設定または空文字なら `CMakeLists.txt` の `project(... VERSION ...)` から最初に見つかる数字とドットだけの version を取り出して使います。空でない値はそのまま `ver` に使われます（`Dockerfile:56`; fallback の元は `CMakeLists.txt:10-11`）。

| build argument の状態 | `ver` に使う値 |
|---|---|
| 省略（宣言の既定値は空） | `CMakeLists.txt` から抽出した version |
| 明示的な空文字 | `CMakeLists.txt` から抽出した version |
| 空でない文字列 | その文字列をそのまま使用 |

値の構文、長さ、数値としての妥当性を検査する分岐はありません。抽出対象がなかった場合に `sed` が出力する空文字も拒否されず、後続の packaging command に渡ります（`Dockerfile:56,64`; `packaging/package_engine.py:292,341-355`）。

## 有効になる条件

`Dockerfile` の `engine-build` stage を使ってソースから作るイメージにだけ適用されます。`docker build --build-arg ENGINE_VERSION=...` で値を渡せます。`ARG` は build stage 内の `RUN` に使われ、runtime stage に `ENV ENGINE_VERSION` として設定されていません（`Dockerfile:23-34,51-67,91-105`）。したがって、実行時にコンテナへ同名の環境変数を設定しても、この処理には影響しません。

## 実行時の詳細

この値は engine のコンパイル設定ではなく、package 作成時の `ver` として使われます。`BUILD.json` の `version`、`packaging/package_engine.py --version`、および `--build-id` の `docker-source-${ver}-cuda...` に渡されます（`Dockerfile:56-65`）。packager は `version` を component 出力フォルダー名と `engine-component.json` の `version` 欄に記録します（`packaging/package_engine.py:198,213-216`）。

読み取りは Docker build 中の該当 `RUN` の shell 展開時です。Strata runtime での再読込、cache、CLI 引数との優先順位はありません。Dockerfile と packager に `ENGINE_VERSION` 固有の警告やエラー分岐は見つかりませんでした。packager は `--version` の指定自体を必須としますが、渡された文字列をここで検証するコードは確認できません（`packaging/package_engine.py:292,341-355`）。

## 根拠

- `Dockerfile:31-34` — `ENGINE_VERSION` を空文字既定の build argument として宣言。
- `Dockerfile:51-65` — 未設定・空文字時の fallback と、BUILD.json および component package への受け渡し。
- `CMakeLists.txt:10-11` — fallback で抽出される project version。
- `packaging/package_engine.py:198,213-216,292,341-355` — version を package folder と manifest に記録し、CLI option から受け取る処理。

候補名の全参照を調べた結果、Strata の C++/Python runtime に `ENGINE_VERSION` の環境読み取り箇所はなく、参照は上記 Dockerfile の build 時処理のみでした。
