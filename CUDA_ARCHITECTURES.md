# `CUDA_ARCHITECTURES`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

これは Strata エンジンの実行時設定ではなく、リポジトリのルート `Dockerfile` が Docker build argument として受け取り、CUDA 対象アーキテクチャを CMake に渡すための値です。Docker イメージを作るとき、値はエンジンのビルドに使われ、`BUILD_VISION=1` の場合は画像エンコーダーのビルドにも使われます。Docker を使わない通常のビルドでは、この名前の環境変数を Strata が読み取る実装は確認できません。

## 値と判定

| 状況 | Strata の扱い |
|---|---|
| Docker build argument 未指定 | Dockerfile の `ARG` 既定値 `75;80;86;89;120` を使う。 |
| 指定値あり | build 内の Python が同名の環境値を読み、前後の空白を除き、両端の `"` を除き、`,` を `;` に置換する。変換した文字列を `-DCMAKE_CUDA_ARCHITECTURES=...` として CMake に渡す。 |
| 値の不正・空文字 | Dockerfile の Python ラッパーでは数値やアーキテクチャ形式を検証しない。そのまま CMake に渡し、受理可否は CMake と CUDA コンパイラに委ねる。 |

例として `--build-arg CUDA_ARCHITECTURES=89` は単一アーキテクチャを指定し、`--build-arg CUDA_ARCHITECTURES=75,86,89` はラッパーで `75;86;89` に変換されます。区切り文字がすでにセミコロンならそのままです。CMake に渡る後の値は `CMAKE_CUDA_ARCHITECTURES` として処理されます。

## 有効になる条件

- Dockerfile に従ってルートディレクトリからイメージをビルドする場合に使われます。コンテナ起動時の `-e CUDA_ARCHITECTURES=...` は、Dockerfile のビルド工程が既に終わっているため、このビルド指定にはなりません。
- ルート CMakeLists は、CUDA 有効時に `CMAKE_CUDA_ARCHITECTURES` が定義されていなければ `120` を既定値にします。Dockerfile は常に明示値を渡すため、通常は Dockerfile 側の既定値または build argument が使われます。
- CUDA アーキテクチャの数値部分が `75` 未満の場合、`STRATA_EXPERIMENTAL_SM60` が無効なら CMake は configure 時に fatal error にします。実験オプションが有効でも `60` 未満は拒否されます。`native`, `all`, `all-major` はこの下限チェックを飛ばしますが、CMake / CUDA コンパイラがその値をサポートする必要があります。
- CUDA 13.0 未満で数値部分が `120` 以上なら、CMake は RTX 50 系向けビルドについて CUDA バージョンの警告を出します。

## 実行時の詳細

Dockerfile は build stage で Python の `os.environ.get("CUDA_ARCHITECTURES", "75;80;86;89;120")` を呼びます。この文字列を `setup.cmake_build()` に渡し、Strata エンジンの CMake configure/build を実行します。`BUILD_VISION` が文字列 `"1"` の場合は、同じアーキテクチャ指定を `tools/vision` の CMake build にも渡します。その他の `BUILD_VISION` 値では画像エンコーダーの build を省きます。

ビルド後、Dockerfile は `arch` をセミコロンで分割し、各要素の `-` より前が数字だけなら整数化して、`engine/BUILD.json` の `archs` に記録します。`-virtual` / `-real` の接尾辞はこのメタデータでは落ちます。値の読み取りは Docker build の Python 工程で行われるため、起動後の環境変更で既にビルド済みのバイナリや `BUILD.json` は変わりません。

この変数自体による実行時ログや分岐はありません。CMake configure 中は `Strata: CUDA enabled, arch ...` の status message が出ます。CMakeLists はアーキテクチャ下限違反で configure を失敗させる場合や、CUDA 13.0 未満かつ `120` 以上で警告を出す場合があります。

## 根拠

- `Dockerfile:13-15,57-60,72-101`: build argument の利用例と既定値、環境値の正規化、エンジン / vision への CMake 引き渡し、`BUILD.json` への記録。
- `CMakeLists.txt:157-189,196`: `CMAKE_CUDA_ARCHITECTURES` 未指定時の既定値、アーキテクチャ下限判定と CUDA バージョン警告、configure 時の表示。
- `docs/INSTALL.md:89-98`: Docker build で `--build-arg CUDA_ARCHITECTURES=89` を使う案内。
