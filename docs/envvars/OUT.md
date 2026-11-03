# `OUT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`OUT` は Strata のエンジン実行時設定ではなく、リポジトリ内のビルド・パッケージ用スクリプトや Docker smoke test が生成物・ログを置くディレクトリを指定する環境変数です。Strata の C++/Python 実行経路で `OUT` を読む箇所は見つかりませんでした。

## 値と判定

| 読み取り箇所 | 未設定または空文字 | 非空文字列 | 判定・優先順位 |
|---|---|---|---|
| `packaging/build_cuda_linux.sh:22` | リポジトリ直下の `out-engine-<variant>` | 指定値をパッケージ出力先にする | `${OUT:-default}`。未設定と空文字は同じ既定値。`${VARIANT}` の既定は `cuda13`（同:15）。スクリプト内に別の `--out` 上書きはない。 |
| `packaging/build_cuda_linux_aarch64.sh:19` | リポジトリ直下の `out-engine-cuda13-aarch64` | 指定値を最終パッケージの出力先にする | `${OUT:-default}`。空文字は既定値。子の `spark/build_engine.sh` には一時 staging path を `OUT` として明示的に渡す（同:30-32）。 |
| `packaging/build_sycl_linux.sh:25` | リポジトリ直下の `out-engine-sycl` | 指定値をパッケージ出力先にする | `${OUT:-default}`。空文字は既定値。他の CLI 出力指定での上書きはない。 |
| `packaging/build_hip_linux.sh:29` | 起動時の作業ディレクトリにある `work-<VARIANT>` | 指定値を作業・stage・package のルートにする | `${OUT:-default}`。空文字は既定値。`VARIANT` は必須（同:23）。 |
| `packaging/build_dsv41_hip_linux.sh:21` | 起動時の作業ディレクトリにある `work-dsv41-<VARIANT>` | 指定値を作業・stage・package のルートにする | `${OUT:-default}`。空文字は既定値。`VARIANT` は必須（同:15）。 |
| `spark/build_engine.sh:19` | リポジトリ直下の `out-spark/engine` | 指定値を完成エンジンフォルダーにする | `${OUT:-default}`。空文字は既定値。他の CLI 出力指定での上書きはない。 |
| `docker/smoke-test.sh:11` | エラー終了 | 指定値を smoke test のログ置き場にする | `${OUT:?}`。空文字と未設定のどちらも、シェルがパラメーター展開エラーを出して終了する。 |

いずれも値を数値や列挙値として parse せず、パス文字列として使います。文字列比較、範囲検査、正規化、相対パスの一律な基準化はありません。相対パスは各スクリプトがその後 `cd` するディレクトリとの組み合わせで解決されます。ディレクトリ作成や後続コマンドが失敗すればビルド／テスト処理も失敗します。

## 有効になる条件

- 6 つのビルドスクリプトを実行したときに、そのスクリプト内で出力先が決まります。CUDA Linux x86_64 / arm64、SYCL、HIP、HIP DeepSeek-V4.1、DGX Spark 用エンジンの経路が該当します。
- Docker smoke test では `OUT` が空でないことが必須で、`OUT/test.log` を作り、以後の標準出力・標準エラーをそのログへ tee します（`docker/smoke-test.sh:11-17`）。
- これらはスクリプトのシェル変数展開であり、OS/backend/build macro によるエンジン内の機能切替はありません。ビルドされた `strata` へこの値を環境設定として転送する処理も見つかりません。
- `packaging/mac/sign-and-notarize.sh` の `--out`、`packaging/mac/build_dsv41_engine.sh` の `--out`、デスクトップ補助 script の `OUT` は、それぞれ引数から設定するシェル変数です。`OUT` 環境変数を読むものではありません（例: `packaging/mac/sign-and-notarize.sh:52,65-70`）。

## 実行時の詳細

各ビルド script は開始時に一度 `OUT` を展開してローカルの `out` または `OUT` に保持し、その値を作業ディレクトリ、stage、パッケージ出力先に使います。CUDA x86_64 と SYCL は `mkdir -p` 後に `package_engine.py --out` へ渡し、成功時に `built: <path>` を表示します（`packaging/build_cuda_linux.sh:61-67`; `packaging/build_sycl_linux.sh:65-74`）。arm64 CUDA は `OUT` を最終パッケージ先に使い、内側の Spark build の出力は一時ディレクトリへ分けます（`packaging/build_cuda_linux_aarch64.sh:30-32,35-53`）。

HIP の2 script は `OUT` 配下に build tree、ログ、stage、components を作ります。通常の HIP script は `NO_PACKAGE` が空でない場合、package 作成前に stage 完了として終了します（`packaging/build_hip_linux.sh:45,60-123`）。DeepSeek-V4.1 専用 script も同様に `OUT` 配下へ置き、`NO_PACKAGE` 指定時は stage 後に終了します（`packaging/build_dsv41_hip_linux.sh:33-81`）。DGX Spark script は `OUT` をエンジン、ライブラリ、`BUILD.json` の配置先として使います（`spark/build_engine.sh:77-94`）。

読み取り後にプロセス環境の `OUT` を変更して再評価する処理や cache はありません。値がファイルシステム上で使えない場合、`mkdir`、リダイレクト、copy、build、packaging のいずれかがエラーになります。CUDA/SYCL script は `set -e` で失敗時に停止し（各 `:14`, `:17`）、HIP script はコマンド結果を status に記録して `ABORT ... failed` で終了する経路があります（例: `packaging/build_hip_linux.sh:47-48,64-90`; `packaging/build_dsv41_hip_linux.sh:34-35,49-52`）。Docker smoke test は必須 `OUT` が空なら先へ進まず、後続のテスト失敗は標準ログと `test.log` に `FAIL` として出力されます（`docker/smoke-test.sh:11-17,21-22`）。

## 根拠

- 環境値の読み取り・既定値: `packaging/build_cuda_linux.sh:15-24`; `packaging/build_cuda_linux_aarch64.sh:17-19`; `packaging/build_sycl_linux.sh:17-28`; `packaging/build_hip_linux.sh:22-32`; `packaging/build_dsv41_hip_linux.sh:14-24`; `spark/build_engine.sh:16-25`。
- `OUT` 必須の smoke test: `docker/smoke-test.sh:10-17`。
- 候補一覧上の名前: `docs/envvars/000_envvers.md:744`（この一覧だけでは実装の有無は確定しない）。
