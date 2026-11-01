# `ALLOW_BAD_OCLOC`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

## 役割

`ALLOW_BAD_OCLOC=1` は、同梱 SYCL ビルドスクリプトの `ocloc` バージョン事前チェックを飛ばし、既知の問題があるバージョンでもビルド処理へ進めるための例外指定です。Strata の実行時設定ではなく、`sycl/tools/build.sh` を実行するときだけ評価されるビルド用環境変数です。値を CMake の cache やコンパイラへ渡す処理はありません。

このチェックは、`AOT` が `bmg` または `lnl` で始まり、かつ `I8_ESIMD` が厳密に `OFF` ではないときに限って行われます。チェック対象 `ocloc` のバージョンが `26.22.38646` 系と判定された場合、`ALLOW_BAD_OCLOC` が厳密に `1` でなければスクリプトはビルド開始前に終了コード `2` で停止します。`ALLOW_BAD_OCLOC=1` はその停止を解除するだけで、ビルド成功を保証しません。

## 値と判定

スクリプトは Bash の `${ALLOW_BAD_OCLOC:-}` を使って unset と空文字の両方を空文字にし、その結果を文字列 `1` と完全一致で比較します。数値変換、truthy 判定、先頭文字比較はありません。

| 値 | 事前チェックでの扱い |
|---|---|
| 未設定 | 空文字として扱う。該当する危険条件と既知バージョンが揃えば停止する |
| 空文字 | 未設定と同じ。停止を解除しない |
| `1` | 完全一致するため、`ocloc` バージョン確認と既知版による停止を丸ごと飛ばす |
| その他（例: `0`, `true`, `01`, `1 `） | `1` と一致せず、未設定と同様にチェックする |

判定箇所は `sycl/tools/build.sh:24-35` です。変数はこのスクリプトが起動した Bash プロセスでチェック時に評価され、値を static cache する処理はありません。スクリプト起動後に親プロセス側で値を変えても、実行中の Bash の環境は変わりません。

## 有効になる条件

判定順を含む条件は次のとおりです（`sycl/tools/build.sh:20-35`）。

1. `AOT` が正規表現 `^(bmg|lnl)` に一致する。値の先頭が `bmg` または `lnl` なら後続文字列は問われません。unset / 空文字や `acm-g10` などは対象外です。
2. `I8_ESIMD` が厳密に `OFF` ではない。unset の場合は比較時に `AUTO` とみなされるためチェック対象です。小文字 `off` や空文字も `OFF` とは一致しません。
3. `ALLOW_BAD_OCLOC` が厳密に `1` ではない。
4. `ocloc --version` からバージョン文字列が得られ、`26.22.38646` または `26.22.38646.` で始まるものとして認識される。

最後の条件を満たすと、スクリプトは stderr に `build.sh: this image's ocloc is ...` と対処案を出し、`exit 2` します。`ocloc` コマンドがない、バージョン出力から文字列を抽出できない、または既知版に一致しない場合は、このガードによる停止はありません。`ocloc_version()` は `ocloc --version` の出力から正規表現で最初の `数字.数字.数字`（任意で `.数字` 付き）を抽出し、`known_bad_ocloc()` が `26.22.38646` 系かを判定します（`sycl/tools/build.sh:14-22`）。

`I8_ESIMD=OFF` はこの事前チェックを避けます。スクリプトは `I8_ESIMD` を CMake の `STRATA_SYCL_I8_ESIMD` に渡し、CMake は `OFF` を有効値として受け入れ、ESIMD kernel を無効化します（`sycl/tools/build.sh:39-42`, `sycl/CMakeLists.txt:45-63`）。一方 `ALLOW_BAD_OCLOC` 自体は CMake 引数に含まれず、CMake cache の設定にもなりません（`sycl/tools/build.sh:37-43`）。既存の build directory は CMake cache を保持します。特に `I8_ESIMD` を省略した既存 build では guard 側の既定比較値 `AUTO` と既存 cache の値は別々に扱われます（`sycl/tools/build.sh:37-42`）。

## 実行時の詳細

スクリプトは先に oneAPI の `setvars.sh` を source し、その後に環境値と `ocloc` を確認します。`ALLOW_BAD_OCLOC=1` が設定されてガードを通過すると、スクリプトは通常の CMake configure / build 手順へ進みます。この変数に応じた追加の CMake option、ログ、コンパイラ設定はありません（`sycl/tools/build.sh:6-7,24-43`）。

対象の `AOT` は `bmg` だけでなく `lnl` も含みます。`AOT` を指定しない JIT build や、別の AOT target ではこのガードは実行されません。`I8_ESIMD=OFF` を使った場合は ESIMD kernels を含めないビルド設定になることを CMake が示し、コメント上は prompt の experts が XMX path を使う構成です（`sycl/CMakeLists.txt:45-63`）。

ガードを飛ばした後のビルドが失敗した場合、スクリプトは通常の build の終了状態を `BUILD EXIT <rc>` として出し、その状態で終了します。ログに `IGC: Internal Compiler Error` が含まれる場合には、追加で `build.sh: the device compiler ... crashed: try ...` という案内を出します（`sycl/tools/build.sh:43-50`）。これは `ALLOW_BAD_OCLOC` 自体の動作ではなく、ビルドログを見たスクリプトの後段処理です。

## 根拠

- `sycl/tools/build.sh:3-5` — 変数の用途を示すスクリプトの案内コメント。
- `sycl/tools/build.sh:6-7` — Bash 実行環境と oneAPI 環境設定の読み込み。
- `sycl/tools/build.sh:14-35` — `ocloc` バージョン抽出、既知版判定、条件、stderr の案内、終了コード `2`。
- `sycl/tools/build.sh:37-50` — CMake へ渡す引数、既存 build directory の扱い、build 終了状態と後段ログ。
- `sycl/CMakeLists.txt:45-63` — `STRATA_SYCL_I8_ESIMD` の CMake 側の有効値と ESIMD 無効時の構成。
- `docs/INTEL.md:85-95` — `build.sh` 用変数の説明と既知 `ocloc` 問題の記載。測定値はこの調査文書では扱っていません。
