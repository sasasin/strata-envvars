# `PKGVER`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。対象は Strata 所有ソースの環境参照。外部ライブラリの環境変数は対象外。

## 役割

`PKGVER` は一部の Linux engine パッケージ作成スクリプトが使うパッケージ版文字列です。AMD HIP の engine / DeepSeek-V4.1 package と Linux ARM64 CUDA package の生成時に参照されます。Strata の起動時設定や実行中の挙動を変える環境変数ではありません。

## 値と判定

いずれのスクリプトもシェルの `${PKGVER:-default}` 展開を使います。この形式では未設定と空文字の両方が既定値に置き換わります。空でない値は文字列のまま使われ、スクリプト内で形式・数値・範囲の検証や正規化はありません。

| 実行経路 | 未設定または空文字 | 空でない値 |
|---|---|---|
| AMD HIP engine (`packaging/build_hip_linux.sh`) | `0.1.56` | 指定文字列を `BUILD.json` の `version` と packer の `--version` に渡す |
| AMD HIP DeepSeek-V4.1 (`packaging/build_dsv41_hip_linux.sh`) | `0.1.56` | 指定文字列を `BUILD.json` の `version` と packer の `--version` に渡す |
| Linux ARM64 CUDA (`packaging/build_cuda_linux_aarch64.sh`) | `CMakeLists.txt` の最初の `project(... VERSION 数字...)` から抽出した値。調査時点では `0.1.56` | 指定文字列を `ver` として両方の `--version` に渡す |

根拠: `packaging/build_hip_linux.sh:22,30,95,122`、`packaging/build_dsv41_hip_linux.sh:21-23,61-64,77-80`、`packaging/build_cuda_linux_aarch64.sh:25-27,34-47`、`CMakeLists.txt:11`。

## 有効になる条件

値が使われるのは、該当するビルドスクリプトを実行して成果物または stage metadata を作る場合だけです。

- `build_hip_linux.sh` は `VISION_ONLY` が空の場合に engine を作り、stage の `BUILD.json` に版を記録します。`VISION_ONLY` が設定されていると 91 行で先に終了するため、版は使われません。`NO_PACKAGE` が空でない場合は stage 作成後に package 処理を省きますが、すでに `BUILD.json` には版が記録されています（118-123 行）。
- `build_dsv41_hip_linux.sh` は stage の `BUILD.json` に版を書き、`NO_PACKAGE` が空でなければ packer 呼び出しを省きます（61-81 行）。
- `build_cuda_linux_aarch64.sh` は Linux arm64 以外では `PKGVER` を読み取る行に進む前に終了します。適用後の `ver` は Qwen engine と DeepSeek engine の両 package 呼び出しに使われます（21-28, 34-47 行）。

CLI 引数による優先順位はありません。これらのスクリプトが選んだ版文字列を `packaging/package_engine.py --version` に渡します。packer はその値を出力ディレクトリ名と `engine-component.json` の `version` に使います（`packaging/package_engine.py:198-224,341-355`）。

## 実行時の詳細

シェルスクリプト実行時に一度展開され、その後はシェル変数として参照されます。AMD スクリプトでは、値を `BUILD.json` の JSON 文字列へシェル展開で書き込み、同じ値を引用符付きの `--version` 引数として packer に渡します。CUDA ARM64 スクリプトは `ver` に保持し、2回の packer 呼び出しへ渡します。packer は `version` を出力フォルダー名に含め、manifest の値として JSON シリアライズします。

`PKGVER` 専用の形式検査は見つかりませんでした。ただし HIP スクリプトは値を JSON escaping せずに `BUILD.json` の文字列へ埋め込み、その直後に `stage_tuning.py` が JSON として読み込みます。そのため、JSON 文字列として不正になる値（たとえば引用符を含む値）は同ツールの読み込みで失敗します（各 build スクリプトの `BUILD.json` 書き込み箇所、`packaging/stage_tuning.py:31-34`）。CUDA ARM64 経路は値を packer に引数として渡し、packer が manifest を `json.dumps` で生成します（`packaging/package_engine.py:213-224`）。パッケージ作成時の他の検証失敗は各スクリプトの通常の失敗処理に従います。CUDA ARM64 スクリプトは `set -eu` で、packer の失敗時にスクリプトが失敗します（`packaging/build_cuda_linux_aarch64.sh:16,37-52`）。HIP スクリプトは packer の終了コードを `chk` に渡し、非ゼロなら `ABORT packaged failed` を status に記録して終了します（`packaging/build_hip_linux.sh:47-48,122-126`、`packaging/build_dsv41_hip_linux.sh:34-35,79-84`）。

これはパッケージ build 用の環境入力であり、生成済みの Strata engine がプロセス環境から読む用途は、候補名の全参照検索では確認できませんでした。したがって、実行時に値を変更しても、すでに生成した package の版情報には反映されません。

## 根拠

- `packaging/build_hip_linux.sh:22-30,60-64,91-95,118-126` — 既定値、engine build / vision-only の分岐、`BUILD.json` と package 作成。
- `packaging/build_dsv41_hip_linux.sh:14-24,61-84` — 既定値、`BUILD.json`、package を省略する分岐。
- `packaging/build_cuda_linux_aarch64.sh:16-28,34-52` — platform 条件、CMake version fallback、2種類の package への受け渡し。
- `CMakeLists.txt:11` — ARM64 CUDA 経路が fallback に使う project version。
- `packaging/package_engine.py:198-224,287-355` — `--version` の必須引数、フォルダー名・manifest への反映。
- `packaging/stage_tuning.py:31-34` — HIP package の `BUILD.json` 読み込みと更新。
