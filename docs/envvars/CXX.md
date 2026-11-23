# `CXX`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

Strata のセットアップ処理でローカルビルドを行うときに、CMake の C++ コンパイラを指定する。`terminal/setup.py` の `host_compiler_defs()` が `CXX` を読み、`-DCMAKE_CXX_COMPILER=<値>` として CMake に渡す。これはビルド時の選択であり、ビルド済みエンジンの実行時動作は変えない。CUDA を使うエンジンと CUDA 画像エンコーダのビルド経路が対象である（`terminal/setup.py:6763-6774, 6852-6863, 6873-6881`）。

同梱の独立した Trellis ビルドスクリプトも `CXX` を参照する。`test`（引数省略時を含む）と `lib` でコンパイラコマンドに使うが、`hip` 分岐は `g++` と `hipcc` を直接指定する（`terminal/tools/trellis/build.sh:1-26`）。

## 値と判定

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `terminal/setup.py` の CMake ビルド | `os.environ.get("CXX", "")` は空文字になり、CXX 定義を追加しない | 空白を前後から除いた後に空でない文字列。例: `g++-14`、`/opt/tool chain/bin/c++` | 空文字、空白だけの値は `strip()` 後に空になり定義を追加しない。`true` / `false` など特別な真偽値判定はない |
| `terminal/tools/trellis/build.sh` の `test` / `lib` | 未設定または空文字なら `g++` | 空でない値をコンパイラコマンドとして使用。例: `clang++` | 空文字自体は `:-` により `g++` にフォールバック。コンパイラとして不正かどうかの検査はスクリプトにない |

`setup.py` は文字列を真偽値やバージョン番号として parse せず、前後の空白だけを除いて CMake 定義にします。中間の空白は保持されます。CLI 引数による `CXX` の上書きはこの実装にはありません。`CUDAHOSTCXX` が空でない場合は nvcc の host compiler にそちらを使い、未設定・空・空白のみの場合は `CXX` の整形後の値を使います。`CC` は別の `CMAKE_C_COMPILER` 定義です（`terminal/setup.py:6763-6774`）。

Trellis スクリプトは環境値を検査せず、シェル変数へそのまま代入し、引用符なしで展開します。そのため複数語の値は複数のコマンド語として渡されます（`terminal/tools/trellis/build.sh:7-12, 22-26`）。

## 有効になる条件

- `setup.py` では、ビルド済みエンジンが現在のソース等に合致して早期 return する場合、`host_compiler_defs()` はビルド呼び出しに至らず `CXX` は CMake に渡されない（`terminal/setup.py:6841-6846`）。
- ローカル CUDA エンジンの再ビルドでは毎回 `host_compiler_defs(True)` の戻り値を CMake 定義に追加する。CUDA 画像エンコーダをコンパイルする場合も `host_compiler_defs(vision == "gpu")` を渡す。既製エンジンの取得・利用だけの経路にはこの指定処理がない（`terminal/setup.py:6852-6863, 6873-6881, 9110-9116`）。
- `build_engine_hip()` は別経路で、`host_compiler_defs()` の呼び出しは確認できない。従ってこの `setup.py` の CXX 渡しは HIP エンジンのコンパイラ指定を行わない（呼び出し箇所 `terminal/setup.py:6763-6774, 6857-6881, 9541`）。
- Trellis スクリプトは `test`（既定）または `lib` の分岐でだけ `$CXX` を展開する。`hip` 分岐では `$CXX` を使わない（`terminal/tools/trellis/build.sh:10-26`）。

## 実行時の詳細

`setup.py` は `host_compiler_defs()` が呼ばれた時点の環境を読む。Python 側で値を static cache したり、実行中に再読込したりする処理はない。戻り値は `cmake_build()` に渡され、CMake の configure コマンド引数に含まれる。CMake の build コマンド自体には `CXX` 定義を付けず、configure で選んだビルド設定を使う（`terminal/setup.py:6763-6774, 6709-6718, 6857-6863`）。セットアップ処理の `run()` は起動環境を子プロセスへコピーし、CMake コマンドを表示する（`terminal/setup.py:1131-1157`）。

この処理は Strata の既存 CMake build folder を自動削除してコンパイラを切り替えるものではない。ソース内コメントは、環境変数自体はフォルダの初回 configure 時にしか CMake に届かないため、既存 folder にも適用できる `-D` 定義として渡すと説明している（`terminal/setup.py:6763-6768`）。既存キャッシュに対する CMake の受理可否や、指定コンパイラの実際の導入・動作は Strata のコードだけでは確定しない。

Trellis スクリプトはプロセス起動時に shell の `${CXX:-g++}` で選択する（`terminal/tools/trellis/build.sh:4-12`）。

## ログと測定値

`setup.py` は CMake 起動コマンドを `  > ...` と表示するため、設定値が空でない場合は `-DCMAKE_CXX_COMPILER=...` を確認できる。CMake コマンドが非ゼロ終了すると `run()` は `command failed (exit N): cmake` で失敗する。更新処理中のローカル再ビルドでは例外を捕捉し、`could not compile the updated engine...: starting the installed engine` と警告して既存エンジンで続行する経路がある（`terminal/setup.py:1141-1157, 6441-6452`）。`CXX` 専用の警告・測定値は確認できない。

Trellis スクリプトは各ビルド成功後に `built <出力先>` を表示し、コマンド失敗は `set -e` によりスクリプトを停止させる（`terminal/tools/trellis/build.sh:4, 28-29`）。

## 根拠

- `terminal/setup.py:6763-6774` — 環境値の取得・空白除去・CMake 定義、および `CUDAHOSTCXX` の fallback。
- `terminal/setup.py:6841-6863, 6873-6881` — ビルド済み判定と CUDA エンジン／画像エンコーダへの適用。
- `terminal/setup.py:6709-6718, 1131-1157` — configure/build の引数、起動ログ、失敗処理。
- `terminal/setup.py:6441-6452` — 更新時の再ビルド失敗警告。
- `terminal/tools/trellis/build.sh:4-29` — 独立ビルドスクリプトの既定値、使用分岐、結果表示。
