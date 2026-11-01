# `CMAKE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの調査開始時の状態は `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

Strata 本体や実行時機能を制御する変数ではありません。Strata 同梱の build script 2 本が、起動時に CMake 実行ファイルのパス／コマンド名を選ぶために読みます。

- `spark/build_engine.sh` は DGX Spark 向け CUDA engine の configure と build に使うコマンドを選びます。
- `packaging/mac/build_dsv41_engine.sh` は macOS 向け DeepSeek-V4.1 Metal engine の configure に使うコマンドを選びます。

## 値と判定

どちらも POSIX shell の `${CMAKE:-既定値}` を使います。この形式では `CMAKE` が未設定、または空文字なら既定値になり、空でない値ならその文字列が使われます。数値や真偽値への変換、文字列検証、範囲制限はありません。選ばれた文字列は引用符付きでコマンド位置に展開されるため、空白を含むパスも一つのコマンド名として扱われます。

| 読み取り箇所 | 未設定または空文字 | 非空の値 |
|---|---|---|
| `spark/build_engine.sh` | `cmake` | 指定されたコマンド名／パス |
| `packaging/mac/build_dsv41_engine.sh` | `command -v cmake` の結果。見つからなければ `$HOME/strata-mac/tools/bin/cmake` | 指定されたコマンド名／パス |

CLI オプションによる `CMAKE` の上書きはありません。両スクリプトにある `--build` 等の引数は別の build/output directory 等を選びます。

## 有効になる条件

この値を読むのは上記スクリプトを実行した場合だけです。Strata engine の通常起動、CUDA/HIP/SYCL backend の実行、サーバーモードでは参照されません。

Spark script は起動時に値を `cmake` shell 変数へ代入し、その後同じ値で configure と build を呼びます。プラットフォーム検査や CUDA toolkit 検査などが先に失敗した場合、CMake 呼び出しには到達しません。macOS script は値を `CMAKE` shell 変数に代入し、`strata_ds4` 実行ファイルが存在しない場合の configure に使います。既に実行ファイルがある場合はこのコマンドで configure しませんが、後続の Ninja build は実行します。

## 実行時の詳細

Spark では `"$cmake"` を使って `cmake -G Ninja ...` configure を行い、続けて `cmake --build ...` を実行します。configure/build が失敗すると `set -e` により script は失敗終了します（`spark/build_engine.sh:16,59-68`）。

macOS では `"$CMAKE"` を使って Metal 用 CMake configure を行います。configure が失敗した場合は `|| exit 1` で終了します（`packaging/mac/build_dsv41_engine.sh:19,41-47`）。両方とも選択値を再評価する cache はなく、代入はスクリプト実行ごとに一度です。設定された `CMAKE` の値そのものについて Strata 独自のログや警告はありません。実行ファイルが見つからない等の失敗は shell のコマンド実行失敗となり、Spark では `set -e`、macOS では configure 行の `exit 1` により後続処理へ進みません。

## 根拠

- `spark/build_engine.sh:16-24,27-43,59-74` — strict shell 設定、`CMAKE` の既定値、プラットフォーム／toolkit 条件、CMake を用いた configure/build。
- `packaging/mac/build_dsv41_engine.sh:19-20,34-47` — `CMAKE` の既定値選択と、実行ファイルがない場合だけ行う configure。
- 呼び出し経路の記載: `docs/DGX_SPARK_LINUX.md:37,59` は Spark setup/build で `spark/build_engine.sh` を使うことを説明し、`docs/DEEPSEEK_MAC.md:88` は macOS engine packaging script を案内しています。

候補一覧 `docs/envvars/000_envvers.md` に名前がありますが、確認できた参照はこの2つの shell build script に限られます。engine/runtime の環境変数ではありません。
