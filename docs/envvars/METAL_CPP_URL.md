# `METAL_CPP_URL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

この環境変数は `.github/workflows/metal-build.yml` の Metal build job 専用です。job が Metal C++ headers の固定 URL を環境に設定し、`metal-cpp` step の shell がその値を `curl` の引数として使います。通常の Strata 実行時設定ではありません。

Mac 上で利用者が実行するセットアップ経路は別で、`metal/setup_mac.py` の `METAL_CPP_URL` Python 定数から取得先を決めています。このスクリプトは `os.environ` から `METAL_CPP_URL` を読まず、シェルや環境変数での上書きは行いません。

## 値と判定

| 経路 | 値 | 判定・変換 |
|---|---|---|
| GitHub Actions の `metal-link` job | `https://developer.apple.com/metal/cpp/files/metal-cpp_26.zip` | job の `env` に固定文字列として設定。shell は `"$METAL_CPP_URL"` として展開し、文字列比較や URL parse は Strata 側で行わない。 |
| Mac の `metal/setup_mac.py` | 同じ URL の Python 定数 | 環境変数ではなくソース内定数。`METAL_CPP_URL` 環境変数の unset / 空文字 / 任意値は参照されない。 |

Workflow の定義上、job では unset や空文字を既定値として扱う分岐はありません。値の優先順位を CLI 引数や別環境変数と比較する処理もありません。workflow 内では URL と別に `METAL_CPP_SHA256` を固定し、ダウンロード後の zip を `shasum -a 256 -c -` で照合します。

## 有効になる条件

- `.github/workflows/metal-build.yml` の `metal-link` job でのみ定義されます。同 workflow は `pull_request`（指定された path に変更がある場合）または `workflow_dispatch` で起動する設定です。
- job は `macos-26` runner で実行されます。
- Strata の通常の CLI、サーバー、Metal engine の実行経路に、この名前を読むコードは見つかりませんでした。
- `setup.py` は macOS で通常の setup 経路に入ると `metal/setup_mac.py` を起動しますが、そこで使う URL は同スクリプト内の定数です。そのため、workflow の job 環境変数と利用者の Mac の setup は独立しています。

## 実行時の詳細

Workflow は job 環境に URL を設定し、`metal-cpp` step で shell 展開した値を `curl` に渡して `metal-cpp.zip` を作ります。続けて固定の SHA-256 を検査し、`_mcpp` に展開します。その後 CMake の `METAL_CPP_DIR` に展開先を渡して Metal engine を build します。これは CI のビルド準備であり、実行中の Strata engine の挙動を変えません。`curl` や `shasum` 自体の失敗時の詳細は、それら外部コマンドの挙動に属するためここでは Strata の挙動として説明しません。

Mac の setup script では、既存の `third_party/metal-cpp/Metal/Metal.hpp` があればそのディレクトリを返します。なければソース内 URL の zip をダウンロードし、固定 SHA-256 を検証してから展開します。この経路の取得値は `METAL_CPP_URL` 環境変数では制御されません。

## 根拠

- `.github/workflows/metal-build.yml:7-16` — workflow の起動条件。
- `.github/workflows/metal-build.yml:21-40` — `macos-26` job、URL と checksum の固定設定、shell からの URL 使用、検証と展開。
- `.github/workflows/metal-build.yml:48-53` — 展開した headers を CMake に渡して engine を build。
- `metal/setup_mac.py:42-44,82-97` — Mac setup の URL/checksum は Python 定数であり、download・検証に使う。
- `setup.py:7703-7707,9068-9069` — 通常の macOS setup が `metal/setup_mac.py` に委譲する。
