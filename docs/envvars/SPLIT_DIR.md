# `SPLIT_DIR`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Linux HIP 向けエンジンの梱包スクリプト `packaging/build_hip_linux.sh` で、既にビルド済みの `strata-split-*-amd` 実行ファイルを梱包用 stage に追加するディレクトリを指定します。Strata エンジン本体の実行時設定ではなく、このスクリプトを使うビルド・梱包時だけ参照されます。ソース全体での `SPLIT_DIR` の参照はこのスクリプト内の説明と処理だけで、他の Strata 実行経路からの読み取りは見つかりませんでした。

## 値と判定

| 値 | 処理 |
|---|---|
| 未設定 | `${SPLIT_DIR:-}` が空文字になり、コピー処理をスキップします。 |
| 空文字 | 未設定と同じくコピー処理をスキップします。 |
| 空でない値 | 値をディレクトリのパスとして使い、その直下の `strata-split-*-amd` に一致するファイルを stage にコピーします。 |

値の数値変換、文字列比較、正規化、ディレクトリの事前検証はありません。パスを引用しているため空白を含むパスも一つの引数として扱われます。Bash の glob に一致するファイルがない場合はパターンがそのまま `cp` に渡り、`cp` がエラーを stderr に出します。コピー失敗の終了状態はこのスクリプト内で検査されず、直ちに中断する処理もありません。

## 有効になる条件

- Linux HIP 梱包スクリプトを実行し、`VISION_ONLY` が空でないことが条件です。`VISION_ONLY` が空でない場合は engine と stage の作成前に終了するため、この変数のコピー処理には到達しません。
- 値が空でない場合でも、指定先に一致する実行ファイルがなければコピーは成功しません。
- コピーは stage 作成後、`NO_PACKAGE` の判定前に行われます。そのため `NO_PACKAGE` が空でなく梱包を省略する場合も、stage にはコピーを試みます。通常の梱包経路では、その stage が `package_engine.py` に `--tree` とともに渡されます。
- CLI 引数や別の環境変数から `SPLIT_DIR` を上書きする処理はありません。

## 実行時の詳細

この値は `build_hip_linux.sh` の実行中、stage を作成して標準の engine や vision バイナリを置いた後にシェルが展開します。シェル起動時の環境から使われ、スクリプト内にキャッシュや再読込処理はありません。空でない値なら `"$SPLIT_DIR"/strata-split-*-amd` を `"$STAGE/"` に `cp` します。スクリプトの冒頭で `set -u` は指定されていますが `set -e` はなく、この `cp` の終了状態を記録・検査する `chk` 呼び出しもありません。したがって、ここでの失敗は `cp` の stderr で観測できる一方、それだけでスクリプトが終了するとはコードから言えません。

## 根拠

- `packaging/build_hip_linux.sh:5-18` はこのスクリプトの設定値一覧で、`SPLIT_DIR` を split engine バイナリの所在フォルダーとして説明しています。
- `packaging/build_hip_linux.sh:22` は `set -u` を有効にし、`:60-91` は `VISION_ONLY` による早期終了を含む engine / reader のビルド経路です。
- `packaging/build_hip_linux.sh:92-110` は stage 作成後に標準バイナリを配置し、`SPLIT_DIR` が空でないときだけ一致するファイルを stage にコピーします。
- `packaging/build_hip_linux.sh:118-124` はコピーの後で `NO_PACKAGE` を判定し、梱包時には stage を `packaging/package_engine.py` に `--tree` とともに渡します。
- `packaging/package_engine.py:149-165,206-211` は `tree` 指定時に stage 配下のファイルを選び、梱包 staging へコピーする処理です。
