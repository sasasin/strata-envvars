# `CC`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数の意味は対象外。

## 役割

Strata の `setup.py` がソースから NVIDIA 用エンジンまたは画像 encoder をビルドするとき、CMake に C コンパイラを指定するための変数です。`CC` は `CMAKE_C_COMPILER` に渡されます。C++ コンパイラを指定する `CXX` とは別で、`CC` だけでは `CMAKE_CXX_COMPILER` や CUDA の host compiler は指定しません。

## 値と判定

| `CC` の状態 | setup.py の処理 |
|---|---|
| 未設定 | `CMAKE_C_COMPILER` の定義を追加しない |
| 空文字、または空白だけ | `.strip()` 後に空になるため定義を追加しない |
| その他 | 前後の空白を取り除いた文字列を `-DCMAKE_C_COMPILER=<値>` として CMake configure に渡す |

setup.py は値を数値・真偽値として解釈せず、コンパイラの存在確認や妥当性検証もしません。文字列を分割して複数の引数にする処理もありません。指定された compiler の解決と受理、既存 build cache との整合は CMake 側に委ねられます。

## 有効になる条件

- `setup.py` が実際にローカルビルドへ進み、CMake configure を実行する場合に参照されます。既存のエンジンと必要な encoder が利用可能で再ビルドをスキップした場合、`CC` は読み取られません。
- NVIDIA エンジンの configure では `host_compiler_defs(True)` が使われます。画像 encoder の configure でも同関数が使われ、CPU encoder では `False`、CUDA encoder では `True` が渡されます。
- AMD HIP エンジンは別の configure 経路で、`CC` を含む `host_compiler_defs()` を呼ばず、HIP compiler を明示します。この経路に `CC` は渡されません。
- Windows では `vcvars` の確認・呼び出しを含む別のビルド手順を通ります。`CC` の指定はこの手順を置き換えたり、ビルドツールの前提条件を解除したりしません。

## 実行時の詳細

`host_compiler_defs()` は configure の直前に `os.environ.get("CC", "").strip()` で値を読み、空でなければ `-DCMAKE_C_COMPILER=...` を定義リストへ追加します。エンジンと画像 encoder の両方をビルドする場合、それぞれの configure 呼び出しでこの関数が評価されます。`cmake_build()` はその定義を CMake configure コマンドに追加します。setup.py 自身は `CC` を別の環境変数へ転送・書き換えたり、ビルド後の実行エンジンに渡したりしません。

この指定はビルド時のみのものです。実行時の推論動作を変える `CC` 読み取り箇所は、Strata 所有ソースでは確認できません。関連する `CXX` と `CUDAHOSTCXX` の優先関係は別変数の説明対象です。

## 根拠

- `setup.py:3338-3349` — `CC` の取得、空白除去、`CMAKE_C_COMPILER` 定義の生成。`CUDAHOSTCXX` は `CXX` を既定値とし、CUDA ビルドの場合だけ別定義になります。
- `setup.py:3289-3310` — CMake configure に `defs` を渡し、Windows では vcvars を呼ぶバッチ経由で実行。
- `setup.py:3381-3433` — エンジンと画像 encoder の再ビルド判定および configure 呼び出し。
- `setup.py:2632-2673` — AMD HIP エンジンの独立した configure 経路。`CC` の compiler 定義は追加されません。
- `docs/TROUBLESHOOTING.md:52-56` — Linux の CUDA/compiler 不整合時に `CC` / `CXX` / `CUDAHOSTCXX` を指定でき、setup が CMake に渡す旨の説明。実際の値処理は上記のソースを根拠としています。
