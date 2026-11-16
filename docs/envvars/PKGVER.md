# `PKGVER`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`PKGVER` は Strata エンジンの実行時設定ではなく、2 つの Linux リリース用パッケージ作成スクリプトがパッケージのバージョン文字列を選ぶための環境変数です。HIP スクリプトでは `BUILD.json` の `version` と `package_engine.py --version` に、CUDA ARM64 スクリプトではパッケージャーの `--version` と build ID に使われます。モデル選択、推論、エンジン起動時の動作を変える読み取りはありません。`packaging/build_hip_linux.sh:30,90,116`、`packaging/build_cuda_linux_aarch64.sh:25,37,40`。

## 値と判定

どちらもシェルの `${PKGVER:-既定値}` 展開を使います。未設定または空文字なら既定値になり、空でない文字列はそのまま採用されます。文字列全体のバージョン形式検査、数値変換、大文字小文字変換、空白除去はこの処理では行われません。

| スクリプト／条件 | unset | 設定時に採用される値 | 空文字・形式外の値 |
|---|---|---|---|
| `packaging/build_hip_linux.sh` | `0.1.60` | 空でない値をそのまま採用（例: `0.1.60`, `0`, `v1`, `0anything`） | 空文字は `0.1.60`。形式外も値の文字列として後段へ渡され、ここでは拒否されない |
| `packaging/build_cuda_linux_aarch64.sh`（Linux ARM64） | `CMakeLists.txt` の `project(... VERSION ...)` から抽出した値。調査対象 commit では `0.1.61` | 空でない値をそのまま採用（例: `0.1.61`, `0`, `v1`, `0anything`） | 空文字は CMake の値に戻る。形式外も値の文字列として後段へ渡され、ここでは拒否されない |

HIP の既定値は `packaging/build_hip_linux.sh:30`、値の利用箇所は同 `:90,116`。CUDA ARM64 は `packaging/build_cuda_linux_aarch64.sh:20-25` で Linux ARM64 以外を終了させてから値を決め、`CMakeLists.txt:13` と同スクリプト `:25` に既定値の根拠があります。`packaging/package_engine.py:165-170,195,211-214` は渡された文字列を出力フォルダー名と manifest の `version` に使いますが、バージョン形式を検査していません。したがってこの処理の範囲では、`0` や `0anything` も `PKGVER` として有効です。

## 有効になる条件

- HIP 側は `packaging/build_hip_linux.sh` を使い、必須の `VARIANT` と `HP` が設定されたビルドで適用されます（同スクリプト `:21-30`）。ただし `VISION_ONLY` が空でない場合はパッケージ用 `BUILD.json` を作る前に終了するため、選択した値は成果物に使われません（同 `:86`）。`NO_PACKAGE` が空でない場合は `BUILD.json` まで作成しますが、`package_engine.py` 呼び出し前に終了します（同 `:89-90,113-117`）。
- CUDA 側は `packaging/build_cuda_linux_aarch64.sh` の Linux ARM64 経路でのみ読み取ります。その他の OS／CPU では値の選択前に終了します（同 `:20-25`）。このスクリプトはステージング後にパッケージャーを呼びます（同 `:34-42`）。
- これらはスクリプト内の既定値より環境値を優先します。ラッパースクリプトに `PKGVER` 用の CLI 引数はありません。`package_engine.py` 自体には `--version` 引数がありますが、ラッパーが `PKGVER` から選んだ文字列を渡します（`packaging/package_engine.py:288-294,339-353`）。
- 変数を読む箇所はこの 2 スクリプトだけです。実行時エンジンや他の backend の実行経路を有効にする条件はありません。

## 実行時の詳細

両スクリプトとも、起動後のシェル評価時に一度値を選びます。実行中に環境を変更して再評価する仕組みや cache はありません。

- HIP は選択値を `BUILD.json` の `version` に埋め込み、パッケージ化時には `--version "$PKGVER"` として渡します（`packaging/build_hip_linux.sh:30,87-90,113-118`）。パッケージャーはこの値を `<version>-<platform>-<backend>[-<variant>]` のディレクトリー名と manifest の `version` に格納します（`packaging/package_engine.py:195-214`）。
- CUDA ARM64 は `ver` に選択値または CMake から抽出した値を保存し、`release-${ver}-...` という build ID と `package_engine.py --version "$ver"` に渡します（`packaging/build_cuda_linux_aarch64.sh:25,36-42`）。パッケージャーは同様にフォルダー名と manifest に保存します（`packaging/package_engine.py:195-214`）。
- 引数は後続コマンドへ明示的に渡されます。調査した `PKGVER` 参照に、モデル状態、CLI 実行設定、別の環境変数による上書きはありません。

## ログと測定値

`PKGVER` 専用の警告やログはありません。パッケージ作成が成功すると `package_engine.py` は作成先フォルダーを出力します（`packaging/package_engine.py:354-356`）。パッケージャーは同名の出力フォルダーが既にある場合に `<folder> already exists; remove it first (packages are immutable)` で終了します（同 `:195-198`）。HIP スクリプトではパッケージャーの出力を `$OUT/package.log` に記録し、失敗時は build status に `ABORT packaged failed (rc=...)` を記録して終了します（`packaging/build_hip_linux.sh:46-47,116-119`）。CUDA スクリプトは `set -e` のためパッケージャー失敗時に終了します（`packaging/build_cuda_linux_aarch64.sh:15,40-42`）。測定値は該当しません。

## 根拠

- `packaging/build_hip_linux.sh:21-30,86-90,113-119` — HIP スクリプトでの既定値、値の利用、パッケージ処理の条件。
- `packaging/build_cuda_linux_aarch64.sh:15-27,34-46` — CUDA ARM64 の OS 条件、既定値、build ID とパッケージ引数。
- `CMakeLists.txt:13` — CUDA ARM64 スクリプトの既定バージョンの抽出元。
- `packaging/package_engine.py:165-170,188-214,288-294,339-356` — バージョン文字列の検証有無、格納先、出力と失敗経路。
