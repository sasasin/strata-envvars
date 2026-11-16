# `LIBW`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`LIBW` は Linux/HIP 用 packaging スクリプトが ROCm libraries root を指定する build-time 入力である。未設定または空文字なら `HP`（ROCm devel root）を代わりに使う。指定した root は CMake の prefix 探索パスと、HIP package の共有ライブラリ・rocBLAS/hipBLASLt データ収集元に使われる。エンジンの通常実行時に読み取るコードは見つからず、生成されるバイナリの実行時設定ではない（`packaging/build_hip_linux.sh:11,26-28,55,93-98`、`packaging/build_split_hip.sh:10,19-21,33`）。

## 値と判定

両スクリプトとも Bash の `${LIBW:-$HP}` を一度評価してシェル変数 `LIBW` に代入する。`:-` は未設定と空文字の両方で fallback する。文字列を boolean や数値として parse せず、空白除去・パス正規化・存在確認もしない。非空ならその文字列を root として使うため、`0`、`false`、`0anything` もパス文字列として有効扱いになる。大文字小文字は Bash の変数名どおり区別される。

| 条件 | unset | 空文字 | 非空の値 |
|---|---|---|---|
| `packaging/build_hip_linux.sh` | `$HP` を使う | `$HP` を使う | 指定文字列を使う |
| `packaging/build_split_hip.sh` | `$HP` を使う | `$HP` を使う | 指定文字列を使う |

`HP` は両スクリプトで必須であり、未設定なら `${HP:?…}` で処理が止まる。`LIBW` による別の値域検査や無効値 fallback はない（`packaging/build_hip_linux.sh:21,26-28`、`packaging/build_split_hip.sh:17,20-21`）。

## 有効になる条件

- `packaging/build_hip_linux.sh` または `packaging/build_split_hip.sh` を実行する場合にだけ参照される。どちらも Linux/HIP 用 build script で、通常の Strata CLI・server 起動では使われない（`packaging/build_hip_linux.sh:1-5,22-28`、`packaging/build_split_hip.sh:1-3,17-21`）。
- `HP` が必須である。`LIBW` が未設定または空なら `HP` が libraries root として兼用される。
- `build_hip_linux.sh` では `LIBW` が CMake の prefix path に入るため、エンジンと HIP vision reader の configure に渡される。`VISION_ONLY` が非空ならエンジン build と後段の package/data collection を飛ばすが、HIP vision reader の configure には引き続き prefix path が渡る（`packaging/build_hip_linux.sh:55,60-70,79-85`）。
- `build_hip_linux.sh` の通常 packaging 経路では、`$LIBW/lib` が `collect_libs.py` の共有ライブラリ検索先に含まれ、`$LIBW/lib/rocblas/library` と `$LIBW/lib/hipblaslt/library` がデータ収集元になる。`build_split_hip.sh` は CMake prefix path にだけ含める（`packaging/build_hip_linux.sh:93-100`、`packaging/build_split_hip.sh:31-35`）。
- `LIBW` の root が存在しない、または期待するサブディレクトリを欠く場合の明示的な検査はない。共有ライブラリは他の検索 root から見つかることがあり、データ収集は該当ファイルがなければコピー対象がなくても処理を続ける（`packaging/build_hip_linux.sh:93-99`、`packaging/collect_libs.py:154-180,224-238`）。

## 実行時の詳細

両スクリプトの冒頭で一度 shell parameter expansion され、後続処理は代入済みの値を使う。プロセス実行中に環境側の `LIBW` を変更して再評価する処理や cache はない。

`build_hip_linux.sh` では `-DCMAKE_PREFIX_PATH=$HP;$LIBW$SYSDEPS` の一部として CMake configure に渡し、package stage では `$LIBW/lib` を `collect_libs.py --search` に渡す。また rocBLAS/hipBLASLt の data source を `$LIBW/lib/...` として渡す。`build_split_hip.sh` は同様に CMake prefix path を設定する（`packaging/build_hip_linux.sh:52-56,63-65,93-99`、`packaging/build_split_hip.sh:27-35`）。

変数は Strata の build artifact の作成元を切り替える入力であり、スクリプトはその値を環境変数として runtime engine に設定する処理をしていない。`build_hip_linux.sh` の configure/build/収集が失敗すると `chk` が build.status に失敗と `ABORT` を記録して終了コード 1 で終了する。CMake ログは `$OUT/cfg.log` 等、collect のログは `$OUT/collect.log` に出る（`packaging/build_hip_linux.sh:44-47,63-68,95-100`）。`build_split_hip.sh` は `set -eu` で、CMake または ninja 等の失敗時にその場で非 0 終了する。`LIBW` 専用の警告文はない（`packaging/build_split_hip.sh:17,31-40`）。

## 根拠

- `packaging/build_hip_linux.sh:5-17,21-29` — 対象スクリプトと入力の説明、必須 `HP`、`LIBW` の fallback。
- `packaging/build_hip_linux.sh:52-68,71-85` — CMake 設定への適用、`VISION_ONLY` 条件、失敗記録。
- `packaging/build_hip_linux.sh:87-100` — stage/package の条件、`LIBW` 配下の data と共有ライブラリ検索。
- `packaging/build_split_hip.sh:10,17-35` — `LIBW` の説明、fallback と CMake prefix path への適用。
- `packaging/collect_libs.py:154-180,224-238` — 検索 root の利用と、指定 data directory 配下にあるファイルのコピー処理。
