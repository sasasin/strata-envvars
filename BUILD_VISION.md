# `BUILD_VISION`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソースで、外部ライブラリや Docker 自身の動作は説明対象外。

## 役割

Docker イメージをビルドするとき、画像 encoder `strata-vision` をイメージに含めるか決めます。これはコンテナ実行時の設定ではなく、`Dockerfile` の `ARG` を Python のビルド用 `RUN` から読む値です。通常の `setup.py` 起動時に `BUILD_VISION` を読む箇所はありません。

## 値と判定

Dockerfile は `BUILD_VISION` の既定値を `1` にし、ビルド用 Python コードは環境値が未設定ならさらに `"1"` を既定値として使います。値が文字列 `"1"` と完全一致すると `vision = "gpu"`、それ以外は `vision = "none"` です。数値変換、trim、大文字小文字変換はありません。

| ビルド時の値 | 判定 | 結果 |
|---|---|---|
| 未指定 | `"1"`（Dockerfile の ARG 既定値） | GPU image encoder をビルドしてイメージに含める |
| `1` | `"1"` と一致 | 同上 |
| 空文字、`0`、`true`、`01`、その他 | `"1"` と不一致 | image encoder をこの Docker build ではビルドせず、イメージにコピーしない |

Dockerfile では `ARG` として宣言され、`ENV BUILD_VISION=...` への変換はありません。そのため、この ARG の値自体はコンテナの実行時環境変数として設定されません。

## 有効になる条件

この判定が使われるのは `Dockerfile` のイメージ build 内だけです。`VISION` は別の起動時設定で、両者は連動して自動設定されません。`BUILD_VISION=0` でも後の初回セットアップまたは再セットアップで `VISION=yes` / `gpu` を選ぶと、`setup.py` は必要な encoder がなければ CUDA 版 encoder のビルドを試みます。`VISION=cpu` なら CPU 版のビルド経路です。従って `BUILD_VISION=0` は「イメージ作成時に encoder を作らない」指定であり、以後の画像機能を恒久的に禁止する指定ではありません。

起動時に画像を無効にするには `VISION=no` を使います。画像有効の設定を行わず encoder もないまま画像入力を受けると、server は `this server was started without the vision encoder (run setup again and choose 'vision'), so it cannot read images` を返します。既存の `/data` にセットアップ済み config がある場合、entrypoint は通常その config を使ってセットアップを省略します。設定変更のために再セットアップする経路は `REINSTALL=1` です。

## 実行時の詳細

Docker build の Python は値を `os.environ.get("BUILD_VISION", "1") == "1"` で判定します。`vision` が `"gpu"` の場合、Strata engine の build に続けて `tools/vision` を `STRATA_VISION_CUDA=ON` で build し、生成された `strata-vision` を `engine/` にコピーします。`vision` が `"none"` の場合、この build とコピーを飛ばします。どちらの場合も `engine/BUILD.json` に `vision` の値を記録し、encoder がない場合の `vision_src` は `null` です。

entrypoint は初回セットアップ時に runtime の `VISION` を `setup.py --vision` に渡します。`setup.py` が `gpu` または `cpu` の encoder を必要とし、ローカル engine に encoder がない（または source hash が古い）と判定した場合、`build_engine()` が encoder をビルドして engine directory にコピーします。この処理は build arg の値を再読せず、セットアップに渡された `vision` と build metadata / ファイルの有無を見ます。画像を有効化した config では encoder の実行ファイル、mmproj、model path を記録します。

この変数の読取りは Docker build の該当 `RUN` 中だけです。既に作ったイメージや起動中コンテナで値を変更しても、そのイメージ内に同梱されたファイルは変わりません。別の値を反映するにはイメージを再 build する必要があります。

## 根拠

- `Dockerfile:57-60`: `CUDA_ARCHITECTURES` と `BUILD_VISION=1` の build ARG 宣言、および encoder を省略できる旨。
- `Dockerfile:72-101`: `BUILD_VISION` の完全一致判定、GPU encoder の build/copy 条件、`BUILD.json` への `vision` / `vision_src` 記録。
- `docs/INSTALL.md:95-105`: `--build-arg BUILD_VISION=0` で image encoder build を省略する案内と、起動時 `VISION` の別設定。
- `docker-entrypoint.sh:23,46-48,70-87`: runtime `VISION` の既定値、config がある場合の再セットアップ条件、初回・再セットアップでの `--vision` 引き渡し。
- `setup.py:3397-3409,3433-3448`: encoder の必要判定、欠落時の build、build metadata。
- `setup.py:5362-5375,5496-5504,5792-5798`: runtime `--vision` の解釈と有効設定時の build / config 登録。
- `serve/server.py:3605-3609`: encoder がない server が画像入力を拒否するエラー。
