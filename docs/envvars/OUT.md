# `OUT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`OUT` は Strata 本体の engine 実行時設定ではなく、リポジトリ内の packaging/build・Docker smoke-test・E2E スクリプトが出力先を選ぶための環境変数である。Linux の CUDA / HIP / SYCL packaging ではパッケージまたは作業成果物の場所、Windows CUDA packaging ではパッケージ先、`engine/spark/build_engine.sh` では engine フォルダー、`tools/docker/smoke-test.sh` ではログフォルダー、Node の画像読み込み E2E では記録とスクリーンショットの保存先を指定する。対象はこれらのスクリプトを実行したときに限られ、通常の `strata` プロセスやサーバーの挙動を変える読み取りは確認できない（例: `tools/packaging/build_cuda_linux.sh:16-28`, `tools/packaging/build_hip_linux.sh:21-44`, `tools/packaging/build_cuda_windows.py:151-165`, `app/host/scripts/load-pictures-e2e.mjs:19-26`）。

## 値と判定

値はパス文字列として使われ、数値変換や値域検査はない。既定値と空文字の扱いは実装ごとに異なる。

| 実行経路 | unset | 設定時に使われる値 | 空文字・無効値 |
|---|---|---|---|
| Linux CUDA x86_64 packaging | `$repo/out-engine-$variant`（variant の既定は `cuda13`） | `OUT` の文字列 | `${OUT:-...}` のため空文字も既定値へ戻る。パスの存在・書き込み可能性は事前検査せず、後続コマンドで失敗する（`tools/packaging/build_cuda_linux.sh:17-28,76-82`）。 |
| Linux HIP packaging | `$PWD/work-$V`（`V` は必須の `VARIANT`） | `OUT` の文字列 | 空文字も既定値へ戻る。文字列のパス妥当性検査はない（`tools/packaging/build_hip_linux.sh:21-32,44`）。 |
| Linux SYCL packaging | `$repo/out-engine-sycl` | `OUT` の文字列 | 空文字も既定値へ戻る。パス検査はない（`tools/packaging/build_sycl_linux.sh:18-28,72-80`）。 |
| Linux CUDA aarch64 packaging | `$repo/out-engine-cuda13-aarch64` | `OUT` の文字列 | 空文字も既定値へ戻る。パス検査はない（`tools/packaging/build_cuda_linux_aarch64.sh:15-18,38-48`）。内部の `engine/spark/build_engine.sh` は別途 `OUT=$stage/engine` を渡されるため、親スクリプトの package 出力先 `OUT` はそこで上書きされる（同 `:32-35`）。 |
| DGX Spark engine build | `$repo/out-spark/engine` | `OUT` の文字列 | 空文字も既定値へ戻る。`rm -rf "$out"` を含むため、指定先は成果物の削除・再作成対象になる（`engine/spark/build_engine.sh:17-27,75-89`）。 |
| Windows CUDA packaging | `<repo>/out-engine-win-<variant>` | `os.environ.get("OUT")` が空でない場合の文字列 | Python の `or` により unset と空文字は既定値。値は `Path` に渡されるが、独自の値域検査はない（`tools/packaging/build_cuda_windows.py:151-165,191-203`）。 |
| Docker smoke-test | 既定値なし。必須 | `OUT` の文字列 | `${OUT:?}` で unset または空文字ならシェルがエラーとして停止する。その後、ディレクトリ作成と `test.log` の出力に使う（`tools/docker/smoke-test.sh:10-17`）。 |
| 画像読み込み E2E | `./lp-out` | `process.env.OUT` の値 | `??` 判定なので空文字は既定値へ戻らず、そのまま `mkdirSync` に渡される。数値・形式の検査はない（`app/host/scripts/load-pictures-e2e.mjs:19-26`）。 |

これらのパス値は大文字小文字を変換せず、そのまま使われる。相対パスの基準はスクリプトの作業ディレクトリに依存する。Linux CUDA / SYCL / aarch64 の各 packaging script は `OUT` を読み取った後に repo へ `cd` してから成果物を書き出すため、相対指定は repo 基準になる。HIP は初期の `mkdir -p "$OUT"` の後に `cd "$SRC"` するので、相対指定は初期ディレクトリで作業フォルダーを作り、その後の同じ相対表記の参照は `$SRC` 基準になる（`tools/packaging/build_hip_linux.sh:23-29,44,58-65`）。Spark build は `cd "$repo"` 後に出力先を操作する（`engine/spark/build_engine.sh:18-20,50,75-89`）。Windows は `Path` に渡した相対パスを実行時カレントディレクトリ基準で扱う（`tools/packaging/build_cuda_windows.py:161-165,191-203`）。

## 有効になる条件

- Linux CUDA x86_64 は Linux 向け build script の実行時に使う。`VARIANT` の検査、CUDA toolkit の一致確認、CMake build が先にあり、`OUT` はその成果物のパッケージ場所を選ぶだけ（`tools/packaging/build_cuda_linux.sh:17-32,43-50,76-82`）。
- Linux HIP は `VARIANT` と `HP` が必須で、build 条件に応じて engine / vision / package を生成する。`VISION_ONLY` や `NO_PACKAGE` などで後続処理を早期終了する場合、`OUT` が指定されても package 出力まで到達しない（`tools/packaging/build_hip_linux.sh:21-32,60-86,127-141`）。
- Linux SYCL は oneAPI / `icpx` が必要で、`AOT` が空なら JIT package、Battlemage device list なら AOT build となる。`OUT` はどちらも package 出力先（`tools/packaging/build_sycl_linux.sh:20-37,49-50,71-80`）。
- Linux aarch64 packaging と Spark engine build は arm64 Linux 専用。外側の `OUT` は package 先、内側では一時 stage を `OUT` に設定し直す（`tools/packaging/build_cuda_linux_aarch64.sh:16-24,32-40`; `engine/spark/build_engine.sh:18-32`）。
- Windows packaging は Windows 上で実行する必要がある。非 Windows では `this builds the Windows engine; on Linux use tools/packaging/build_cuda_linux.sh` を出して失敗する（`tools/packaging/build_cuda_windows.py:151-158`）。
- Docker smoke-test は `IMAGE`、`NAME`、`BASE` と `OUT` が設定済みである必要がある（`tools/docker/smoke-test.sh:10-17`）。
- E2E スクリプトは `HOST_URL` が必要で、未設定なら `HOST_URL is required` を出して終了コード 2。`OUT` はホストへの接続・モデル操作の成否を変えず、記録ファイルの保存先だけを変える（`app/host/scripts/load-pictures-e2e.mjs:19-26,48-87`）。

## 実行時の詳細

各スクリプトの起動時に `OUT` をローカル変数または定数へ一度取り込む（Docker smoke-test は起動時に必須性を展開確認し、後続で値を利用）。実行中に親プロセス環境の値を変更しても、取り込み済みの出力先は変化しない。値をモデル、生成結果、server request、子プロセスへ一般設定として転送する処理はない。例外的に aarch64 packaging は engine build 子プロセスへ `OUT=$stage/engine` を明示的に渡し、そこで一時的な engine folder を作らせる（`tools/packaging/build_cuda_linux_aarch64.sh:32-40`; `engine/spark/build_engine.sh:19-27,75-89`）。

Linux CUDA / SYCL / aarch64 と Windows の `OUT` は package 出力ディレクトリ、HIP と Spark の `OUT` は build 作業ディレクトリも兼ねる。Spark build は指定ディレクトリを `rm -rf` してから再作成する。HIP は `build.status` と各 configure/build ログ、stage、components を配下に作る。Node E2E は出力ディレクトリを再帰作成し、スクリーンショット、`timeline.json`、失敗時の `error.txt` を保存する（`tools/packaging/build_hip_linux.sh:44-45,86-100,129-140`; `engine/spark/build_engine.sh:75-89`; `app/host/scripts/load-pictures-e2e.mjs:26,46,81-87`）。

## ログと測定値

通常の成功時には packaging/build script が `built: <path>` を表示する（CUDA x86_64 `tools/packaging/build_cuda_linux.sh:81-82`、SYCL `tools/packaging/build_sycl_linux.sh:76-80`、aarch64 `tools/packaging/build_cuda_linux_aarch64.sh:43-48`、Spark `engine/spark/build_engine.sh:87-89`）。Windows は最後に `built: <folder>` を表示する（`tools/packaging/build_cuda_windows.py:200-203`）。HIP は `build.status` に工程記録を書き、package log を同ファイルへ追記する（`tools/packaging/build_hip_linux.sh:44-47,135-141`）。Docker smoke-test は `$OUT/test.log` に標準出力・標準エラーを tee する（`tools/docker/smoke-test.sh:15-17`）。E2E は JSON の結果概要を標準出力に出し、失敗時はエラーメッセージを標準エラーにも出す（`app/host/scripts/load-pictures-e2e.mjs:81-87`）。`OUT` 自体に関する測定値は該当しない。

## 根拠

- Linux packaging / build: `tools/packaging/build_cuda_linux.sh:16-28,76-82`; `tools/packaging/build_hip_linux.sh:21-45,58-65,86-100,120-141`; `tools/packaging/build_sycl_linux.sh:18-28,40-50,72-80`; `tools/packaging/build_cuda_linux_aarch64.sh:15-48`; `engine/spark/build_engine.sh:17-27,50,75-89`。
- Windows packaging: `tools/packaging/build_cuda_windows.py:151-165,189-203`。
- Docker smoke-test: `tools/docker/smoke-test.sh:10-17`。
- E2E output: `app/host/scripts/load-pictures-e2e.mjs:19-26,46,81-87`。
