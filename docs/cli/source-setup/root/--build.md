# `--build`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat` / update wrappers |
| オプション | `--build` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる（`terminal/setup.py:11535`）。 |

## 役割

モデルのセットアップで既製 engine を選ぶ代わりに、対象 engine をこの Strata checkout のソースからローカルでコンパイルします。インストール済みモデルの更新と組み合わせる場合は `--update --build` で engine を再コンパイルします（`terminal/setup.py:9597-9625`、`terminal/setup.py:8497-8510`、`terminal/setup.py:6452-6458`）。

## 使い方

Linux の checkout でモデルのセットアップ時に engine をビルドする例です。`--no-start` を付けると、セットアップ後にモデルを起動しません。

```sh
./setup.sh --setup --build --no-start
```

Windows では同じ root parser を使う `START-HERE.bat` にフラグを渡せます。既存モデルの更新時は次のように指定します。

```sh
./setup.sh --update --build
```

`--update` はモデルを起動せずに更新処理を行います（`terminal/setup.py:11530-11535`、`terminal/setup.py:8497-8502`）。

## 値と既定値

値は不要で、既定では無効です。`argparse` の `store_true` で定義されており、数値・文字列・選択肢の validation はありません（`terminal/setup.py:11535`）。

## 実行時の動作

通常のモデルセットアップでは、CUDA または Linux の HIP 経路で既製 engine の検索を飛ばし、`build_engine()` または `build_engine_hip()` を呼びます。コンパイル結果は Strata の engine 用フォルダーに置かれ、ビルド記録も保存されます。既存のローカルビルドが現在のソース・GPU アーキテクチャ等に合致している場合、ビルド関数は「すでにビルド済み」として戻ることがあります（`terminal/setup.py:9597-9631`、`terminal/setup.py:5656-5713`、`terminal/setup.py:6902-6957`）。

`--update --build` は `update_install()` から `update_installed_engine(..., rebuild=True)` へ渡されます。既製 engine もローカル engine も再ビルド対象になり、通常の `--update` のように engine のバージョンやローカルソースの変更有無だけで更新を省略しません。モデルファイルは触らず、モデルも起動しません（`terminal/setup.py:8497-8518`、`terminal/setup.py:6452-6517`）。

`--build` を付けただけの既存モデルの通常起動は、セットアップ用の engine 選択処理を通らず、build を実行しません。既存モデルの engine を再ビルドする目的では `--update --build` を使います。`--setup` や `--model` を指定する経路はセットアップ処理に入り、engine 選択を行います（`terminal/setup.py:11676-11698`、`terminal/setup.py:9597-9625`）。

## 適用条件と副作用

- CUDA / HIP のローカルビルドではコンパイラや CMake 等の build tool が必要になり、engine ソースを構成してコンパイルし、engine ファイルや build metadata を書き込みます。CUDA のビルドは `build/`（CUDA 12 は `build-cuda12/`）などを使い、engine 出力先の既存ファイルを更新します（`terminal/setup.py:6902-6957`、`terminal/setup.py:6793-6820`）。
- `--backend hip` の Windows 経路では既製 AMD engine が必要で、`--build` でローカルコンパイルには進みません。既製品が見つからない場合は案内を出して失敗します（`terminal/setup.py:9606-9612`）。
- `--backend sycl` は Intel 用の別 setup に委譲され、同ファイルの通常 CUDA/HIP engine 経路とは異なります。Intel のセットアップはソースビルドを使う実験的経路です（`terminal/setup.py:11635-11638`、`terminal/setup.py:9297-9320`）。
- Apple Silicon の通常 setup は Metal 用 `engine/metal/setup_mac.py` に委譲され、索引上も別 scope の `source-setup/mac/` です。この文書は `terminal/setup.py` の root scope を対象とします（`terminal/setup.py:9290-9294`、`docs/cli/README.md:1661-1668`、`docs/cli/README.md:1725-1731`）。
- `CONTROL` モードは通常の engine step で `control_engine_step()` に分岐するため、root の `--build` が通常の CUDA/HIP engine ビルドを起動する経路とは異なります。shape engine（Hy4 / Inkling）の非 `CONTROL` 経路では `--build` により個別の `strata-hy4` / `strata-inkling` をローカルコンパイルします（`terminal/setup.py:9597-9603`、`terminal/setup.py:9512-9584`）。
- `--build` は `--update` と他の setup 引数を排他的にはしません。通常のセットアップで実際にどの engine が対象になるかは、backend、モデルの shape、制御モードにより分岐します（`terminal/setup.py:9597-9625`）。

## 出力とエラー

通常のコンパイルでは進行状況を表示し、完了時に engine の保存先を表示します。setup の `fail()` 経由の失敗はエラーを出力して終了コード 1 となり、JSONL 出力モードでは `error` event に `exit_code: 1` を含めます。例えば Windows AMD で既製 engine がない場合や、shape engine のビルドに CMake がない場合は失敗経路があります（`terminal/setup.py:1039-1056`、`terminal/setup.py:5702-5713`、`terminal/setup.py:9524-9528`、`terminal/setup.py:9606-9612`）。

## 根拠

- parser と既定値: `terminal/setup.py:11530-11536`
- update の分岐と再ビルド引数: `terminal/setup.py:8497-8518`、`terminal/setup.py:6452-6517`
- 通常の engine 選択とローカルビルド: `terminal/setup.py:9597-9631`、`terminal/setup.py:5656-5713`、`terminal/setup.py:6902-6957`
- setup build tool と CMake 実行: `terminal/setup.py:6793-6820`
- backend / shape / platform 分岐: `terminal/setup.py:9290-9320`、`terminal/setup.py:9512-9603`、`terminal/setup.py:11635-11638`
- 索引上のコマンド階層と scope: `docs/cli/README.md:1659-1671`、`docs/cli/README.md:1725-1731`
