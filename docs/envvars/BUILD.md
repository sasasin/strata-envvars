# `BUILD`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Linux 向けの CUDA / SYCL エンジンパッケージ作成スクリプトと DGX Spark 用エンジン作成スクリプトで、CMake の build tree の場所を指定します。Strata エンジンの実行時設定ではなく、これらのスクリプトを実行するときだけ参照されるビルド用環境変数です。

## 値と判定

3 スクリプトとも POSIX shell の `${BUILD:-既定値}` を使います。`BUILD` が未設定または空文字なら既定ディレクトリを選びます。空でない値は文字列のまま build path として使い、真偽値・数値・ディレクトリの存在を事前検査しません。

| スクリプト | unset / 空文字 | 空でない値 |
|---|---|---|
| CUDA Linux x86_64 package | リポジトリ直下の `build-cuda13`（`VARIANT=cuda13`）または `build-cuda12`（`VARIANT=cuda12`） | 指定値を CMake の build tree として使う |
| SYCL Linux x86_64 package | リポジトリ直下の `build-sycl` | 指定値を CMake の build tree として使う |
| DGX Spark engine | リポジトリ直下の `build-spark` | 指定値を CMake の build tree として使う |

相対パスは各スクリプトがリポジトリ直下へ `cd` した後に CMake へ渡されるため、そのディレクトリからの相対パスです。空白を含む値も引用符付きでパスとして渡されます。パスの有効性はこの変数の読み取り箇所では検査されず、使用時の CMake やファイル操作の結果に委ねられます。

## 有効になる条件

- `packaging/build_cuda_linux.sh` を Linux x86_64 向け CUDA package 作成に使う場合。`VARIANT` は `cuda12` または `cuda13` で、未設定時は `cuda13` です。選ばれた build tree は configure/build とそこからの package staging に使われます。
- `packaging/build_sycl_linux.sh` を Linux x86_64 向け SYCL package 作成に使う場合。選ばれた build tree は configure/build と staging 時の実行ファイル取得に使われます。
- `spark/build_engine.sh` を Linux aarch64 / DGX Spark 向けに使う場合。選ばれた build tree は configure/build、古い `strata-dsv41` の削除、成果物のコピー元に使われます。
- `packaging/build_cuda_linux_aarch64.sh` は `spark/build_engine.sh` を `sh` で起動します。`BUILD` の明示的な上書きはなく、呼び出し環境の値が子スクリプトへ継承されます。

これらのスクリプト以外に `BUILD` を読むエンジン・サーバー・CLI の実行時コードは見つかりませんでした。ビルドが済んだバイナリへこの変数を設定しても、Strata の実装による効果は確認できません。

## 実行時の詳細

各スクリプトは開始時に `BUILD` を一度 shell 変数 `build` へ代入します。CUDA スクリプトでは `cmake -B "$build"` と `cmake --build "$build"` に使い、後に `$build/strata` と `$build/libstrata_kq.so` を staging へコピーします（`packaging/build_cuda_linux.sh:23,33-37,51-52`）。`VARIANT` の確認や `nvcc` の版が合わない場合は `BUILD` の利用より前に stderr へエラーを出して終了コード 2 で終了します（同 `:15-20,25-29`）。

SYCL スクリプトでは CMake の configure/build に同じ build tree を使い、`$build/strata` を package staging へコピーします（`packaging/build_sycl_linux.sh:26,39,44-46,52`）。前提コマンドや oneAPI setup が失敗した場合は `BUILD` の build 操作へ進む前に診断を stderr に出して終了します（同 `:29-36`）。

Spark スクリプトでは CMake の configure/build、`$build/strata-dsv41` の削除、そこからの engine / DeepSeek engine / `libstrata_kq.so` のコピーに使います（`spark/build_engine.sh:20,58-68,80-83`）。アーキテクチャや CUDA toolkit の条件を満たさない場合などは build tree 使用前に stderr へ診断を出して終了します（同 `:27-48`）。

いずれも CMake または後続コマンドの失敗を個別に `BUILD` 用の fallback へ置き換える処理はありません。CUDA / SYCL スクリプトは `set -eu` により失敗コマンドで停止します（各 `:14`, `:17`）。Spark スクリプトも `set -eu` で失敗時に停止します（`spark/build_engine.sh:16`）。成功時は最終的に package または engine の出力先を `built: ...` と表示します。`BUILD` 自体に専用ログや値の警告はありません。

## 根拠

- 候補一覧に `BUILD` があること: `docs/envvars/000_envvers.md` の `BUILD` 項目（索引は候補名の手掛かりであり、動作根拠ではない）。
- CUDA package の読み取り、既定値、CMake への受け渡し、成果物参照: `packaging/build_cuda_linux.sh:14-16,22-24,33-37,51-52`。
- SYCL package の読み取り、既定値、CMake への受け渡し、成果物参照: `packaging/build_sycl_linux.sh:17-18,24-28,39,44-46,52`。
- DGX Spark engine の読み取り、既定値、CMake への受け渡し、成果物参照: `spark/build_engine.sh:16-23,58-68,78-83`。
- aarch64 packaging wrapper からの呼び出しと `BUILD` の非上書き: `packaging/build_cuda_linux_aarch64.sh:32`。
- 候補名の全参照を `rg` で確認したところ、環境から読む実装は上記 3 箇所の `${BUILD:-...}` でした。その他の `BUILD` はローカル shell 変数、ビルドログ・文書中の語、または `BUILD.json` 等のファイル名であり、環境変数の読み取りではありません。
