# `METAL_CPP_SHA256`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

これは Metal エンジンの GitHub Actions ビルドで、ダウンロードする metal-cpp ZIP のチェックサム文字列を shell に渡すための job-level 環境変数です。Strata の実行時設定やユーザー向けセットアップ用の環境変数ではありません。workflow は値を `shasum -a 256 -c -` に渡してから ZIP を展開します。

## 値と判定

workflow の `env` には `4df3c078b9aadcb516212e9cb03004cbc5ce9a3e9c068fa3144d021db585a3a4` が固定記載されています。workflow_dispatch の入力や CLI 引数で値を選ぶ処理、Strata 独自の文字列 parse・空値 fallback はありません。YAML の job 環境を shell が `"$METAL_CPP_SHA256"` として展開し、同じ run コマンド内でチェックサム検証コマンドへ渡します。値の書式検査や比較そのものは Strata のコードではなく、呼び出される `shasum` コマンド側です。

| 状況 | Strata workflow の処理 |
|---|---|
| 通常の workflow 実行 | job の固定値を参照し、ダウンロードした `metal-cpp.zip` の検証コマンドへ渡す |
| 空・不正な値 | Strata 側の補正や代替値はない。検証コマンドへそのまま渡す |
| ローカルの Mac セットアップ | この環境変数は参照しない。Python 定数に固定された値を使う |

## 有効になる条件

GitHub Actions の `Metal build` workflow 内だけで使われます。workflow は `workflow_dispatch` で手動起動でき、pull request では `src/**`、`include/**`、`metal/**`、`third_party/**`、`CMakeLists.txt` または当該 workflow ファイルに変更がある場合を対象にします。job は `macos-26` runner 上で実行されます。アプリの OS/backend、モデル状態、Strata CLI、他の Strata 環境変数による条件分岐はありません。

## 実行時の詳細

`metal-build.yml` の job 環境で SHA-256 値を定義し、`metal-cpp` step が Apple の `metal-cpp_26.zip` を取得して検証コマンドに渡し、その後に展開します。以後の Configure step は展開した headers のパスを `-DMETAL_CPP_DIR` に渡します。この環境変数自体を Strata のビルド済み engine や通常実行プロセスへ渡す処理はありません。

同じ名前は `metal/setup_mac.py` にもありますが、そこでは環境変数ではなく、同じ固定 SHA を持つ Python モジュール定数です。Mac セットアップの `metal_cpp()` は既存 headers がなければ ZIP をダウンロードし、`S.verify_sha256()` に定数を引数として渡します。したがって `METAL_CPP_SHA256` の環境値を設定しても、このセットアップ経路の期待値は変わりません。既存 headers がある場合は関数がそのまま戻るため、その実行ではダウンロードもハッシュ検証も行われません。

## 根拠

- `.github/workflows/metal-build.yml:21-31` — Metal build job、runner、固定された job 環境値。
- `.github/workflows/metal-build.yml:36-40` — ZIP の取得、`"$METAL_CPP_SHA256"` の参照と検証コマンド、展開。
- `.github/workflows/metal-build.yml:48-53` — Configure で展開済み headers を渡し、engine をビルド。
- `.github/workflows/metal-build.yml:7-16` — 手動起動と pull request の対象条件。
- `metal/setup_mac.py:42-45,82-97` — 同名の Python 定数と、ローカルセットアップでの利用。環境変数参照ではない。
- `metal/setup_mac.py:126-144` — Metal engine build の流れ。
- `setup.py:3217-3263` — セットアップが期待値引数 `sha` でファイルを検査し、不一致時（通常ファイル）は削除して失敗する処理。
- `docs/MAC.md:89-100` — Metal headers を SHA-256 で pin するセットアップ説明。
