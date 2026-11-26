# `strata --families`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンのトップレベル引数） |
| オプション | `--families` |
| 別名 | なし |
| 値 | 取らない |

## 役割

このエンジンのビルドが実行対象とする GGUF architecture 名を、空白区切りで標準出力へ返す問い合わせモードです。モデルをロードしたり GPU を初期化したりせず終了します。セットアップ側はこの出力を読み、インストール済みエンジンが扱えるモデル family を判断します。

## 使い方

```sh
strata --families
```

## 値と既定値

値を指定しません。既定値や値の validation はありません。エンジンの `main` は `argv[1]` と `argv[2]` を調べ、どちらかが `--families` ならその場で応答します。したがって通常の `strata --families` のほか、2 番目の引数に置かれた場合も認識されます。3 番目以降の引数はこの早期判定では調べられず、通常の引数解析に進んだ場合は未知引数として扱われます（`engine/src/program/generate.cpp:3701-3715`、`engine/src/program/generate.cpp:4268-4274`）。

## 実行時の動作

出力は実行ファイルのビルド条件で決まります。通常の CUDA/HIP/Metal 系 parser を持つ `engine/src/program/generate.cpp` では、`STRATA_HAVE_QWEN35` が定義されたビルドは `qwen4exp qwen35moe`、未定義なら `qwen4exp` を改行付きで出力します（`engine/src/program/generate.cpp:3707-3715`）。Qwen3.6 用エンジンのリンクとこの定義は、gfx906 を除く該当 GPU ビルドで設定されています（`engine/cmake/strata_gpu_engine.cmake:565-584`）。

Intel SYCL 版は `qwen4exp` のみを出力します。SYCL 側には `qwen35moe` 用の engine path がないためです（`engine/sycl/src/program/generate.cpp:1835-1839`）。これらの文字列は GGUF の `general.architecture` に対応し、共通の family 定義では `qwen4exp` と `qwen35moe` が別 family として扱われています（`engine/include/strata/artifact/model_family.hpp:15-28`）。

`terminal/setup.py` はエンジン実行ファイルへ `--families` を渡し、標準出力を空白で分割して family 集合にします。起動・実行時の OS/subprocess 例外が発生した場合、または出力に `qwen4exp` がない場合は `qwen4exp` のみを返す互換 fallback を使います。戻りコード自体はこの処理で確認していません（`terminal/setup.py:9634-9642`）。Feed 由来モデルでは、この集合に含まれない family を既存エンジンで実行できないものとして扱います（`terminal/strata_control/feed_models.py:204-207,227-235`）。

## 適用条件と副作用

出力は実行時に検出した GPU やモデルではなく、コンパイル時の対応状況を示します。早期判定で応答するため、通常の初期化・推論処理へ進まず、確認できる範囲ではファイル変更や GPU 操作もありません（`engine/src/program/generate.cpp:3701-3715`、`engine/sycl/src/program/generate.cpp:1822-1845`）。オプションの認識時は常に終了コード `0` です。

## 出力

標準出力に family 名を空白区切りで一行出力します。エンジン側のこの経路は診断文を標準エラーへ出さず、`0` を返します。値やオプション位置のエラー経路はありません。早期判定で認識されない位置に置かれ、通常 parser に到達した場合は `unknown argument: ...` と usage を標準エラーへ出して `2` を返します（`engine/src/program/generate.cpp:4268-4274`）。

## 根拠

- `engine/src/program/generate.cpp:3701-3715` — 通常 engine の早期判定、`STRATA_HAVE_QWEN35` による出力、終了コード。
- `engine/sycl/src/program/generate.cpp:1822-1845` — SYCL engine の早期判定と `qwen4exp` のみの出力。
- `engine/include/strata/artifact/model_family.hpp:15-28` — GGUF architecture 名と family の対応。
- `engine/cmake/strata_gpu_engine.cmake:565-584` — Qwen3.6 engine のリンクと `STRATA_HAVE_QWEN35` の定義条件。
- `terminal/setup.py:9634-9642`、`terminal/strata_control/feed_models.py:204-235` — 出力の読み取りと Feed モデルの適用。
- `engine/src/program/generate.cpp:4268-4274` — 通常 parser に進んだ未知引数の失敗経路。
