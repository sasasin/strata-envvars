# `ONEAPI`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata の実行時設定ではなく、二つの Strata 所有 SYCL ビルドスクリプトが Intel oneAPI インストール先を選ぶためのシェル環境変数である。Linux SYCL エンジンのパッケージ作成では `tools/packaging/build_sycl_linux.sh` が `setvars.sh` の場所と同梱ライブラリ探索先を選び、Hy4-Flash SYCL runner のビルドでは `engine/src/hy4flash/sycl/build_hy4_sycl.sh` が `icpx` が PATH にない場合の `setvars.sh` の場所を選ぶ。Strata のエンジン実行時に `ONEAPI` 自体を読む Strata 所有コードは見つからなかった（同じ名前の候補一覧掲載は実装を保証しない）。

根拠: `tools/packaging/build_sycl_linux.sh:25,34,61-62`; `engine/src/hy4flash/sycl/build_hy4_sycl.sh:16-24`。

## 値と判定

両スクリプトとも `${ONEAPI:-/opt/intel/oneapi}` 形式で展開する。未設定と空文字は既定パスに置き換わる。空白だけの値を含む非空値はパスとしてそのまま使われ、真偽値や数値には変換されない。`0`、`true`、`false` も、同名のディレクトリを指す文字列として扱われる。文字列の trim、パス正規化、存在確認以外の形式検査、数値境界検査はない。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `tools/packaging/build_sycl_linux.sh` | `/opt/intel/oneapi` | `ONEAPI=/opt/intel/oneapi` など、`setvars.sh` がその位置にあり実行環境を整えられるパス | `ONEAPI=''` は無効値ではなく既定パスへ fallback。`ONEAPI=/missing` は初期化に失敗して終了。`0` / `true` は特別なスイッチでなくパス名 |
| `engine/src/hy4flash/sycl/build_hy4_sycl.sh` かつ PATH に `icpx` がない | `/opt/intel/oneapi` | `ONEAPI=/opt/intel/oneapi` など、その位置に `setvars.sh` があり、実行後に `icpx` を PATH から見つけられるパス | `ONEAPI=''` は既定パスへ fallback。`ONEAPI=/missing` など `setvars.sh` がない値は source を試さず、その後 `icpx` がなければ終了。`0` / `true` はパス名 |
| Hy4-Flash ビルドで PATH に `icpx` が既にある | 読み取りに使わない | 該当なし | `ONEAPI` の値はこの分岐で参照されず、既存の `icpx` を使う |

SYCL パッケージ作成スクリプトでは選んだパスを引用符付きで `setvars.sh` に渡し、その後 `cd "$repo"` してから同じ値を `--search` のライブラリディレクトリに使う。そのため相対パスは初期化時にはスクリプト起動時の作業ディレクトリ基準、ライブラリ探索時には Strata リポジトリ基準となる。相対値を使う場合に両者が同じ場所を指すかは呼び出し元の作業ディレクトリに依存する。根拠: `tools/packaging/build_sycl_linux.sh:25,34,40,61-62`。

## 有効になる条件

- `tools/packaging/build_sycl_linux.sh` は `ONEAPI` の値にかかわらず `patchelf` を PATH から必要とし、選んだ場所の `setvars.sh` を source できる必要がある。source 後に `icpx` が PATH に必要で、`AOT` が空でない場合はさらに `ocloc` が必要。これらは同スクリプトの前提であり、`ONEAPI` の値判定ではない（`tools/packaging/build_sycl_linux.sh:18-38`）。
- パッケージ作成では選んだ oneAPI ルートの `compiler/latest/lib` と `mkl/latest/lib` が収集対象になる。ビルド設定は `icx` / `icpx` をコンパイラとして指定する（`tools/packaging/build_sycl_linux.sh:49-50,61-62`）。
- Hy4-Flash ビルドで `icpx` が PATH に既にあると `ONEAPI` による探索・初期化は行わない。PATH にない場合、選んだ場所に `setvars.sh` があること、および source 後に `icpx` が PATH から見つかることが必要（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:16-24`）。
- いずれもビルド用シェルの設定で、実行時 OS / backend / モデル状態や CLI 引数によってエンジンが `ONEAPI` を読み直す経路は確認できなかった。

## 実行時の詳細

パッケージ作成スクリプトは起動時に一度 `oneapi` シェル変数へ値を展開し、`set +u` の区間で `setvars.sh` を source する。source の stdout/stderr は捨て、source が失敗すると独自メッセージを stderr に出して終了コード 2 で終了する。後続では `icpx --version` を取り、CMake build を行い、oneAPI の compiler / MKL ライブラリディレクトリを収集先候補として渡す。`ONEAPI` の再読み取りや実行中変更の反映はない（`tools/packaging/build_sycl_linux.sh:18,25,31-38,49-62`）。

Hy4-Flash ビルドスクリプトは起動時、`icpx` が PATH にない場合にだけ環境変数を展開する。選んだディレクトリに `setvars.sh` があれば source するが、その source の失敗は `|| true` で無視し、続けて `icpx` の有無を確認する。`ONEAPI` を読み直すループや cache はない（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:16-24`）。

どちらも CLI 引数から `ONEAPI` の上書きはしない。Hy4-Flash の第1・第2引数はアーキテクチャモードと出力先である。パッケージスクリプトでは別の環境変数 `OUT` が出力先を、`AOT` が AOT 対象を決めるが、`ONEAPI` の値を上書きしない（`tools/packaging/build_sycl_linux.sh:4-6,20-29`; `engine/src/hy4flash/sycl/build_hy4_sycl.sh:3,9-14`）。

## ログと測定値

パッケージ作成スクリプトは `setvars.sh` の出力を抑制する。source が失敗した場合は stderr に `build_sycl_linux.sh: $oneapi/setvars.sh not found or failed` と出して終了コード 2、source 後に `icpx` が PATH にない場合は `build_sycl_linux.sh: icpx is not on PATH after setvars.sh` と出して終了コード 2。成功時に選択した `ONEAPI` パスを表示するログは確認できない（`tools/packaging/build_sycl_linux.sh:31-38`）。

Hy4-Flash ビルドで `icpx` が PATH に見つからない場合は stderr に `build_hy4_sycl.sh: icpx not found (source oneAPI setvars.sh)` と出して終了コード 2。`setvars.sh` の出力は抑制され、source 自体の失敗は直接報告しない（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:17-24`）。`ONEAPI` による測定値の記録はない。

## 根拠

- `tools/packaging/build_sycl_linux.sh:8-17,18-38,40-62` — パッケージ作成用途、既定値、oneAPI 初期化、コンパイラ確認、ライブラリ探索。
- `engine/src/hy4flash/sycl/build_hy4_sycl.sh:1-24,42-70` — Hy4-Flash のビルド用途、PATH を先に確認する条件、初期化と失敗経路。
- `docs/INTEL_ARC.md:101-110,148-150` — oneAPI を使う SYCL パッケージの手動ビルド説明との照合。
- `tools/packaging/ENGINE-COMPONENT.md:115` — SYCL パッケージビルドと実行時同梱物の説明との照合。
