# `strata-hy4 --load-only`（CUDA/HIP）

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP root） |
| オプション | `--load-only` |
| 別名 | なし |
| 値 | 取らないフラグ。既定値は無効 |

## 役割

オフライン実行で `.strata` モデルを実行用に読み込んだ後、プロンプト処理や生成を始めずに正常終了する。モデル読み込みの確認に使えるが、GPU の選択・メモリ情報取得・メモリ計画・モデル本体と expert のロードは実行するため、GPU とモデルを使わずに済む検査モードではない。

## 使い方

```sh
strata-hy4 --model ./model.strata --load-only
```

`--native FILE` は `--model FILE` と同じ値を設定する別表記。`--tokens`、`--gen` などは指定しなくても、このフラグによるモデル読み込み後の早期終了が可能。

## 値と既定値

値を取らず、指定されなければ `false`、指定すると `true` になる。重複指定しても同じ真偽値を設定するだけ。後続の独立した引数は別の CLI 引数として処理され、未知の引数なら `unknown arg ...` を stderr に出して終了コード 2 となる。オプション自身の値検証はない（parser: `engine/src/hy4flash/run/hy4_main.hip.cpp:351,375-384,489,498-505`）。

## 実行時の動作

オフライン経路では、`--model`（または alias `--native`）が必要。GPU 情報を stderr に出し、必要なら入力トークン数などからメモリ計画を行ってから `load_gpu_model` を呼び出し、`--dfly-override` があればそれも適用する。その後、ロード時間を stderr に出力し、`--load-only` が有効なら終了コード 0 で return する。この位置は画像ファイルの準備、トークン入力の検査、`Runner` の構築と初期化、prefill・生成より前にあるため、それらは実行されない（`engine/src/hy4flash/run/hy4_main.hip.cpp:613-665,666-705`）。

したがって、`--tokens` に指定したファイルはこの経路では開かれず、`--image` の画像も処理されない。`--out` ディレクトリへの logits や dump の出力も、この早期 return からは発生しない（同 `:634-639,666-705,777-778`）。モデル自体のロード時には `.strata` ファイルを開き、manifest を読み、GPU/host メモリへのロード処理を行う（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1267-1284`）。

`--serve` と併用しても load-only 終了にはならない。serve 分岐がオフライン経路のロードと早期 return より先に `hy4_serve_main` へ移るため、このフラグの分岐は通らず、通常の serve 初期化・実行に進む（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-611,613-665`）。また、`--info` は引数解析後に独立して早期終了するため、併記してもモデル GPU ロードは行われない（同 `:389-392,507`）。

## 適用条件と副作用

この説明は索引上の `strata-hy4` CUDA/HIP 実装（`engine/src/hy4flash/run/hy4_main.hip.cpp`）に限る。同名オプションを持つ Metal と SYCL 実装は別 scope であり、この文書では扱わない（`docs/cli/README.md:1277-1281,1358-1362,1452-1456`）。

オフライン経路では `--model`/`--native` が空なら usage を stderr に出し終了コード 2。モデルを開けない場合は `open: ...` を stderr に出し、ロード失敗で終了コード 1 となる。`--dfly-override` の適用に失敗した場合も理由を stderr に出し終了コード 1（`engine/src/hy4flash/run/hy4_main.hip.cpp:613-616,658-665`; loader: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1267-1275`）。GPU 情報取得やロードの低水準エラーの全出力・終了挙動は、このオプション固有の処理ではなく、ここでは詳細化しない。

## 出力とエラー

成功時はモデルロードの進捗・ロード時間などを stderr に出した後、コード 0 で終了する。通常のオフライン実行が出す prefill 結果や生成結果は出力されない。GPU 情報は `--load-only` の分岐より前に出力される（`engine/src/hy4flash/run/hy4_main.hip.cpp:617-621,658-665`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:351,489` — フラグの既定値と parser 登録。値を消費しない。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-611,613-665` — serve とオフライン経路の順序、モデル必須条件、GPU/ロード処理、ロード後の早期 return。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:634-639,666-705,777-778` — トークン読み込み・画像処理・Runner 初期化・出力処理が早期 return の後にあること。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1267-1276` — モデルファイルを開き、manifest を解析するロード処理。
- `docs/cli/README.md:1277-1281,1358-1362,1452-1456` — 索引上の tool ID、root scope と Metal/SYCL の別 scope。
