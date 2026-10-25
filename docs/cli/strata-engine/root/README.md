# `strata`（Strata 推論エンジン）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ推論エンジン `strata`（Windows は `strata.exe`） |
| 主な実装 | `src/program/generate.cpp` |
| ビルド定義 | `CMakeLists.txt` の CMake ターゲット `strata` |

## 役割

モデル pack と token ID 列を受け取り、GPU 上で推論して token ID を生成するネイティブプログラムです。Terminal CLI の同名 `strata` wrapper とは別の実行ファイルです。エンジン自身には tokenizer がなく、通常実行では `--tokens` または `--tokens-file` で前処理済み token ID を渡します。モデル、GPU backend、ビルド条件に応じて、専用の Qwen3.6 実装へ処理を引き渡す経路もあります。

## 代表的な使い方

```sh
# 単発生成。token ID と pack / PLE のパスは利用環境に合わせる。
strata --pack pack/full --tokens "1,2,3" --ple-gguf /path/to/ple.gguf --max-new 16

# 常駐モード。起動後は stdin にリクエストを1行ずつ送る。
strata --pack pack/full --serve --ple-gguf /path/to/ple.gguf
```

単発モードでは `--tokens` と `--tokens-file` はどちらか一方が必要です。通常は PLE の GGUF も必要で、`--no-ple` は診断用の明示的な ablation です。ネイティブ GGUF モデルを使う場合は `--native` など対応するモデル引数も指定します。上の例は構文を示すものです。token ID は使用するモデルの語彙にある値へ、パスは実ファイルへ置き換えてください。

## 実行モード

| モード | 動作 |
| --- | --- |
| 単発生成 | prompt token ID を読み、指定数の token を生成して終了します。既定の `--max-new` は 16、通常の greedy 生成が既定です。 |
| 常駐サーバー (`--serve`) | 重み・expert arena・VRAM tier を一度ロードし、stdin の `GEN <max_new> <id,id,...>` リクエストを処理します。生成 token は stdout に `T <id>`、完了時は `DONE ...`、要求エラーは `ERR ...` 形式で出力します。`STOP` は実行中要求を次の処理段階で止め、`QUIT` はプロセスを終了します。 |
| 情報表示 | `--help` / `-h` は usage を stderr に表示して終了し、`--version` / `-V` は version を stdout に表示して終了します。これらは GPU 初期化前に処理されます。 |

常駐モードでは `--batch` / `--slots`、会話 checkpoint、画像入力などを追加できますが、利用条件は個々のオプションによって異なります。詳細は [`--serve`](--serve.md) と各オプション文書を参照してください。

## 主な動作と副作用

- `--gpu LIST` は CUDA/HIP の可視 GPU 選択環境変数をプロセス内で設定し、`CUDA_DEVICE_ORDER=PCI_BUS_ID` も設定します。既存の選択環境変数と値が異なる場合は警告します。
- `--native SHARD1` は GGUF の shard を検出し、モデルに含まれる PLE shard 等を補完します。必要な shard がない場合、対応外のモデル family の場合、または PLE を特定できない場合は起動前にエラーになります。ビルドに Qwen3.6 対応が含まれる場合、その family は GGUF header を見て専用実装へ転送されます。
- `--serve` は stdin/stdout をリクエスト・応答プロトコルとして使い、モデル状態をプロセス終了まで保持します。設定により会話状態を RAM に保持したり、session/profile をファイルに保存したりできます。
- `--dump-logits`、`--dump-residual`、`--dump-layers` などの診断オプションは指定先へファイルを書き込みます。出力先の既存ファイルを使う場合の上書き可否は各出力処理に依存するため、必要なデータを保護したパスを指定してください。

## 注意点

`src/program/generate.cpp` の usage banner は `strata generate --pack ...` と表示しますが、この revision の引数 parser は `generate` をサブコマンドとして除去・解釈せず、未知の引数として扱います。したがって、ネイティブ実行ファイルには `strata --pack ...` のようにオプションを直接渡してください。Terminal CLI の `strata launch` 等とは引数体系が異なります。

GPU/backend の利用可能性はビルドと実行環境に依存します。本調査ではバイナリの build・実行や GPU 動作を確認していません。Release 配布物の特定バージョンについても照合していないため、ここでは記載した checkout のソースを対象としています。

## 関連文書

- [Strata CLI 索引](../../README.md) — `strata-engine` のオプション文書一覧
- [`--help`](--help.md)、[`--version`](--version.md)
- [`--pack`](--pack.md)、[`--tokens`](--tokens.md)、[`--native`](--native.md)、[`--serve`](--serve.md)
- [Strata CLI の配置・配布一覧](../../000_cli_tools.md)

## 根拠

- `CMakeLists.txt:759-762` — `src/program/generate.cpp` から CMake ターゲット `strata` を生成。
- `src/program/generate.cpp:806-817,865-890` — usage banner、pack/token 入力、生成数の既定値、GPU と実行方式の概要。
- `src/program/generate.cpp:2310-2313,2331-2345,2413-2442,2787-2793` — 起動時処理、version/families の早期終了、parser、help と未知引数の処理。
- `src/program/generate.cpp:2370-2391` — `--gpu` による GPU 可視性環境変数の設定と警告。
- `src/program/generate.cpp:2393-2408` — build 条件付き Qwen3.6 model family の専用実装への転送。
- `src/program/generate.cpp:2499-2503,2637-2655,3168-3179,3232-3284,3290-3300` — `--native` / `--serve` の parser、token 入力要件、native shard と PLE の処理・validation。
- `src/program/generate.cpp:7497-7518` — 常駐モードの stdin/stdout プロトコルと会話状態の説明。
- `src/program/generate.cpp:15380-15390` — 常駐要求の完了行 `DONE` の出力。
