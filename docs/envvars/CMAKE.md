# `CMAKE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`CMAKE` は Strata の実行エンジンではなく、同梱のビルド・パッケージ用シェルスクリプトが起動する CMake 実行ファイルを指定する。DGX Spark 向け `engine/spark/build_engine.sh` では configure、ビルドツリー内のターゲット判定、ビルドに使い、Apple Silicon 向け `tools/packaging/mac/build_engine.sh` では Metal エンジンの configure に使う。したがって通常の Strata 実行や生成内容を直接制御する環境変数ではない（`engine/spark/build_engine.sh:25,51-65`; `tools/packaging/mac/build_engine.sh:42,60-66`）。

## 値と判定

両スクリプトとも POSIX/Bash の `${CMAKE:-既定値}` 展開を使う。未設定または空文字なら既定値、空でない値ならその値を採用する。文字列の検証、真偽値・数値変換、空白除去、実行ファイル探索（明示値について）は行わない。採用した値全体を引用符付きでコマンド位置に置くため、値は実行ファイル名またはパスとして扱われ、追加引数を含む文字列にはならない（`engine/spark/build_engine.sh:25`; `tools/packaging/mac/build_engine.sh:42,64`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Spark スクリプト | `cmake` | `cmake`、`/opt/cmake/bin/cmake` | 書式上の無効値判定はない。存在しないパスや実行できないファイルは起動時に失敗する |
| Mac パッケージスクリプト | `command -v cmake` が成功すればその出力、失敗すれば `$HOME/strata-mac/tools/bin/cmake` | `cmake`、`/opt/cmake/bin/cmake` | 書式上の無効値判定はない。存在しないパスや実行できないファイルは起動時に失敗する |

いずれも `CMAKE=''` は unset と同じ既定値になります。`0`、`1`、`true`、`false`、`0anything` も、文字列としてそのまま実行ファイル名と解釈されます。大文字小文字の正規化や値の部分比較はありません（同上）。

## 有効になる条件

- Spark 用は `Linux-aarch64` または `Linux-arm64` であり、CUDA Toolkit の検出結果が許可された 13.x 経路に進む必要がある。その他の OS/CPU は `build_engine.sh:31` で終了し、CUDA バージョン不一致等は `build_engine.sh:44` で終了する。これらを通過した後に configure と build を実行する（`engine/spark/build_engine.sh:29-46,51-65`）。
- Mac 用は `--version` が指定されている必要があり、`--stages`（既定値 `engine vision pkg`）に `engine` が含まれる場合にだけ `CMAKE` を起動する。`--stages` から `engine` を外せば CMAKE は設定されても実行されない（`tools/packaging/mac/build_engine.sh:29-42,60-68`）。
- CLI に CMake 実行ファイルを指定する引数はない。両スクリプトで非空の `CMAKE` が各スクリプトの既定値より優先される。Mac スクリプトでは `NINJA` は別に解決され、configure 後のビルド自体は `$NINJA` を起動する（`tools/packaging/mac/build_engine.sh:42-44,64-66`）。
- Spark スクリプトは `CMAKE` を `engine_targets` に引数として渡し、その helper も同じ実行ファイルで `strata_kq` ターゲットの dry-run 判定を行う（`engine/spark/build_engine.sh:62-65`; `tools/packaging/engine_targets.sh:3-4,10-19`）。

## 実行時の詳細

値は各スクリプトの開始処理でシェル変数へ一度展開される（Spark は `engine/spark/build_engine.sh:25`、Mac は引数処理後の `tools/packaging/mac/build_engine.sh:42`）。関数内 cache や後続の再読み込みはないため、スクリプト実行中にプロセス環境を変更しても再評価されない。CMake への引数は Spark では `-G Ninja -S engine -B "$build"` とビルド設定、Mac では `-S engine/metal -B "$BUILD" -G Ninja` 等である。Spark は同じ値で configure 後にターゲット検査と `--build` を行い、Mac は configure 後に `NINJA` でビルドする（`engine/spark/build_engine.sh:51-65`; `tools/packaging/mac/build_engine.sh:64-66`）。

## ログと測定値

`CMAKE` 固有の値確認ログや警告はない。実行ファイルが起動できない、または CMake が非ゼロで終了した場合、Spark 側は `set -eu` によりその場で終了する。Mac 側では configure の標準出力・標準エラーを `$WORK/metal-cfg.log` に記録し、失敗時に末尾 30 行を表示して終了コード 1 で終わる。Spark の `engine_targets` 判定で既知の `strata_kq` 不在以外の probe エラーが起きると、probe 出力と `engine_targets.sh: cannot tell whether the build tree ... has the strata_kq target` を標準エラーに出して失敗する（`engine/spark/build_engine.sh:17,51-65`; `tools/packaging/mac/build_engine.sh:64-66`; `tools/packaging/engine_targets.sh:11-19`）。CMAKE の変更による性能測定値は該当しない。

## 根拠

- `engine/spark/build_engine.sh:17-25,29-46,48-65`
- `tools/packaging/mac/build_engine.sh:23-44,56-68`
- `tools/packaging/engine_targets.sh:1-19`
