# `--gpu`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision` / `strata-vision-hip` / `strata-vision-sycl` |
| オプション | `--gpu` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

画像読み取り CLI の vision encoder を GPU 利用モードで初期化します。CPU 版を既定としており、このフラグを指定すると `mtmd_context_params.use_gpu` に `true` を渡します。ビルドにより GPU backend は CUDA、HIP、SYCL、Metal のいずれかです（`tools/vision/strata_vision.cpp:89-101,214-215`; `tools/vision/CMakeLists.txt:18-20,31,68-80`）。

## 使い方

```sh
strata-vision --mmproj mmproj.gguf --model model.gguf --gpu
```

`--mmproj` と `--model` は必須です。HIP / SYCL ビルドでは実行ファイル名がそれぞれ `strata-vision-hip` / `strata-vision-sycl` になります。Apple では Metal 有効ビルドの `strata-vision` が CPU/GPU 両方に対応します（`tools/vision/CMakeLists.txt:71-80,96-116`）。

## 値と既定値

値は不要です。省略時は `gpu=false` で CPU 実行になり、指定すると `gpu=true` になります。複数回指定した場合も同じ真偽値を設定するだけです（`tools/vision/strata_vision.cpp:88-101`）。

`--mmproj` または `--model` が空・未指定なら usage を stderr に出して終了コード 2 で終了します。値を伴う別 option が値なしで末尾にあるときは `<option> needs a value` を stderr に出し、同じく終了コード 2 です（`tools/vision/strata_vision.cpp:93-100,125-128`）。

## 実行時の動作

- フラグを省略すると、CUDA / HIP の可視 GPU を隠すため `CUDA_VISIBLE_DEVICES=-1` と `HIP_VISIBLE_DEVICES=-1` をプロセス内環境に設定してから backend を初期化します。指定時はこの変更をしません（`tools/vision/strata_vision.cpp:130-143`）。
- encoder の `cp.use_gpu` にフラグ値を渡します。CPU 実行では `--threads` が正値ならその値を使い、未指定または 0 以下なら CPU thread 数を hardware concurrency の半分（1〜16 に制限）にします。GPU 実行ではこの CPU thread 自動設定を行いません（`tools/vision/strata_vision.cpp:214-228`）。
- GPU モードでは起動時に 2048×2048 の画像を encode して GPU work buffer を warm-up し、所要時間と token 数を stderr に出します。CPU モードでは warm-up を行いません（`tools/vision/strata_vision.cpp:249-283`）。
- サーバーの画像 reader は設定の `gpu` が有効なときにこの option を付けます。設定上限 `max_tokens` があれば `--max-tokens` も併せて渡します（`serve/server.py:2792-2805,2807-2817`）。

## 適用条件と副作用

実際に GPU を使えるかは実行ファイルの build backend と実行環境に依存します。CMake は CUDA、HIP、SYCL を相互排他の別構成として定義し、Apple では `STRATA_VISION_METAL`（既定 ON）により Metal を設定します（`tools/vision/CMakeLists.txt:18-31,68-83`）。HIP / SYCL の GPU モードは backend device 一覧に GPU / integrated GPU がない場合、説明行を stdout に出して終了コード 3 になります。HIP は加えて、検出した gfx architecture が build 対象外なら、`STRATA_VISION_ARCH_CHECK` が設定されていないか 0 以外の場合に同じく終了コード 3 で拒否します（`tools/vision/strata_vision.cpp:144-174`）。Metal ビルドも GPU モードで Metal GPU が見つからなければ stdout にエラーを出し、終了コード 3 です（`tools/vision/strata_vision.cpp:176-192`）。

CUDA については、この実装内に HIP / SYCL / Metal と同型の GPU 有無チェックはありません。CUDA の GPU 初期化失敗時の挙動や backend 側の fallback はここからは確認できません。GPU モードで GPU がない場合の挙動を保証するものではありません。

この option 自体は入力ファイルを書き換えません。通常起動後は stdin の `ENC <image> <output>` 要求ごとに出力パスを `wb` で開くため、同名ファイルがあれば上書きします。出力ファイルを開けない場合などは `ERR ...` を stdout に返して次の要求へ進みます（`tools/vision/strata_vision.cpp:286-334`）。GPU warm-up は実際の処理より前に実行されるため、GPU memory を初期化時に確保します（`tools/vision/strata_vision.cpp:249-255`）。

## 出力とエラー

- GPU がない HIP / SYCL / Metal build、および対象外 HIP architecture: `ERR ...` を stdout に出し、終了コード 3（`tools/vision/strata_vision.cpp:159-172,186-190`）。
- encoder の初期化失敗: `ERR cannot load the vision encoder ...` を stdout に出し、終了コード 1（`tools/vision/strata_vision.cpp:231-235`）。
- GPU が利用できるかの確認とは別に、テキストモデルを開けない場合はエラーを stdout に出し、終了コード 1（`tools/vision/strata_vision.cpp:210-212`）。
- reader が起動して `READY` を返した後の画像読み込み・encode・出力エラーは `ERR ...` を stdout に返します。これは option parser の失敗ではなく、要求単位のエラーです（`tools/vision/strata_vision.cpp:283-334`）。

## 根拠

- parser と既定値: `tools/vision/strata_vision.cpp:88-101`
- GPU 可視性の環境変数設定と backend 初期化: `tools/vision/strata_vision.cpp:130-143`
- GPU 有無・HIP architecture 検査: `tools/vision/strata_vision.cpp:144-192`
- encoder 設定、CPU thread 条件、warm-up: `tools/vision/strata_vision.cpp:214-283`
- build backend と実行ファイル名: `tools/vision/CMakeLists.txt:18-31,68-83,96-116`
- サーバーからの `--gpu` 付与: `serve/server.py:2792-2817`
