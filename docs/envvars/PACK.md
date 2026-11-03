# `PACK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`PACK` は Strata 本体の実行設定ではなく、macOS Apple Silicon 向け DeepSeek-V4.1 engine component のビルドスクリプト `packaging/mac/build_dsv41_engine.sh` が、パッケージ後の自己完結性 smoke test に使う pack ディレクトリを選ぶための shell 変数です。ここでの読み取りは、engine をビルド・パッケージし、パッケージ検証を終えた後にだけ行われます（同ファイル:19-23,61-68）。

索引 `docs/envvars/000_envvers.md` の候補名はこの shell 展開に対応します。調査した Strata 所有ソースでは、実行時 engine や他の helper が環境変数 `PACK` を読む箇所は見つかりませんでした。ソース内の `PACK` の他の用例は、pack データや `--pack` / `--draft-model PACK` の引数・説明などで、環境変数の読み取りではありません。

## 値と判定

スクリプトは `PACK=${PACK:-$HOME/strata-mac/pack-2.25-real}` と代入します。`${name:-word}` の shell 展開なので、未設定または空文字なら `$HOME/strata-mac/pack-2.25-real` を使い、空でない設定値はそのままパスとして使います。数値・真偽値への変換、文字列形式の検査、範囲制限はありません（`packaging/mac/build_dsv41_engine.sh:67`）。

| `PACK` の状態 | スクリプトの処理 |
|---|---|
| 未設定または空文字 | `$HOME/strata-mac/pack-2.25-real` を選択 |
| 空でない値で、そのパスがディレクトリ | その値を `strata-dsv41 --pack` に渡して smoke test を実行 |
| 選択したパスがディレクトリでない | `== no pack at <path>: package built, smoke test skipped` を表示して終了コード 0 で終了 |

パスは引用符で囲んで検査・引数渡しされるため、空白を含む値も単一パスとして扱われます。ディレクトリ以外の内容検査や値の正規化はスクリプト内にありません（`packaging/mac/build_dsv41_engine.sh:67-73`）。

## 有効になる条件

- `PACK` を読むのは `packaging/mac/build_dsv41_engine.sh` のみです。通常の Strata CLI、server、CUDA/HIP/SYCL/Metal engine の起動時設定ではありません。
- スクリプトは対象を Apple Silicon / Metal の DeepSeek-V4.1 engine component と説明しています（`packaging/mac/build_dsv41_engine.sh:2,6-9`）。
- `PACK` の判定に達する前に、engine のビルド、package staging、パッケージ生成、`--verify` が実行されます。`PACK` はこれらの工程の選択や既定値を変えません（`packaging/mac/build_dsv41_engine.sh:41-64`）。このため pack がなくても component の生成・検証後に smoke test だけが省略されます。
- CLI 引数に `PACK` を上書きする専用 option はありません。スクリプトの引数解析は `--version`、`--build`、`--out`、`--build-id` のみです（`packaging/mac/build_dsv41_engine.sh:25-33`）。

## 実行時の詳細

有効なディレクトリがある場合、スクリプトはソースツリー内の `metal/kernels` と `metal/src/engine/msl` を一時的に `.hidden` 名へ移し、`/tmp` を作業ディレクトリとして、生成した `strata-dsv41` に `--pack "$PACK" --ids 0 --n 1` などを渡します。engine の出力は標準エラーとともに `prompt:`、`decode:`、`cannot read`、`failed` に一致する行だけを最大 3 行表示します。その後、隠したディレクトリを戻し、`== done: ... (rc=<値>)` を表示します（`packaging/mac/build_dsv41_engine.sh:69-77`）。したがって `PACK` は engine プロセスへ環境変数として転送されるのではなく、CLI の `--pack` 引数値として渡されます。

スクリプト先頭では `set -u` のみを有効にしており、smoke test のパイプラインは `pipefail` なしで実行されます。`rc=$?` は `grep | head` パイプラインの終了状態です。engine が失敗しても、それがこのスクリプトの最終終了コードに反映されるとは限りません（`packaging/mac/build_dsv41_engine.sh:19,72-77`）。有効な pack を使った場合に engine がどの条件で生成・失敗するかは、この環境変数の処理自体ではなく、engine の `--pack` 実装に属します。

## 根拠

- `packaging/mac/build_dsv41_engine.sh:2-9` — このスクリプトの対象と目的。
- `packaging/mac/build_dsv41_engine.sh:25-37` — CLI 引数と他の環境変数。`PACK` 用の CLI option はない。
- `packaging/mac/build_dsv41_engine.sh:41-64` — `PACK` 判定前の build・package・verify。
- `packaging/mac/build_dsv41_engine.sh:67-77` — `PACK` の既定値、ディレクトリ判定、skip ログと終了、`--pack` への引き渡し、出力処理。
