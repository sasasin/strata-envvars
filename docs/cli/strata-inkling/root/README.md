# `strata-inkling`（CUDA/HIP）

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling` |
| 入口 | CMake component `inkling2` が生成する実行ファイル `strata-inkling` |
| 主な実装 | `engine/src/inkling2/ink_main.cpp`、共通処理 `engine/src/inkling2/ink_serve.h` |

## 役割

Inkling-2-Mini 向けの shape engine で、`.strata` v1.1 のほか Hugging Face safetensors ディレクトリと GGUF を読み込みます。起動引数に応じてモデル情報表示、tokenizer ファイルの書き出し、backend の自己診断、性能計測・参照 logits 評価を行うほか、通常はモデルを開いて backend と KV slot を初期化し、トークン ID 列を生成します。`--serve` を指定した場合は同じモデル処理を常駐させ、標準入力から Strata の行プロトコルを受け取ります。

## 基本的な使い方

```sh
# モデルの構造情報を表示する
strata-inkling --info /models/Inkling-2-Mini.strata

# 1 slot のベンチマークを実行する（モデルのロードと推論を行う）
strata-inkling --bench --native /models/Inkling-2-Mini.strata --parallel 1

# backend の自己診断を行い、モデルの section hash も検証する
strata-inkling --selfcheck --native /models/Inkling-2-Mini.strata --verify-hash

# server モードで起動する。制御コマンドは標準入力から渡す
strata-inkling --serve --native /models/Inkling-2-Mini.strata
```

直接生成する場合は、例えば `strata-inkling --native /models/Inkling-2-Mini.strata --gen 32` と実行します。既定の prompt token ID を使い、生成 token ID をカンマ区切りで標準出力へ出します。明示する prompt token 列は `--prompt-ids` で渡せます。

## 実行モード

| モード | 呼び出し例 | 動作 |
|---|---|---|
| バージョン・ヘルプ | `strata-inkling --version` / `strata-inkling --help` | バージョンまたは利用法を表示して終了。モデルを読み込まない。 |
| 情報表示 | `strata-inkling --info MODEL` | モデル（または対応する VisionShard）の情報を表示して終了。 |
| tokenizer 書き出し | `strata-inkling --export-tokenizer MODEL OUT_DIR` | tokenizer 関連ファイルを出力ディレクトリに作成または書き込みして終了。 |
| 自己診断 | `strata-inkling --selfcheck [--native MODEL]` | 選択 backend の自己診断を実行する。モデル指定時はロード・初期化も行い、`--verify-hash` も併用すると model section の hash を検証する。 |
| ベンチマーク | `strata-inkling --bench --native MODEL` | 合成 prompt を使って prefill/decode を実行し、計測値を標準出力へ出す。 |
| 参照評価 | `strata-inkling --kld-eval REF.bin --native MODEL` または `strata-inkling --dump-ref OUT.bin --native MODEL` | 参照データとの KLD / Top-1 / PPL 評価、または評価用 logits ファイルの書き出しを行う。 |
| 常駐 server | `strata-inkling --serve --native MODEL` | 初期化後 `INFO` / `READY` を出し、標準入力のプロトコル要求を処理し続ける。HTTP/TCP listener を開始する処理ではない。 |
| 直接生成（既定） | `strata-inkling --native MODEL [--prompt-ids IDS] [--gen N]` | 1 slot で生成し、生成 token ID を標準出力へ出す。 |

## 主な動作

引数を左から解析して backend 設定を組み立て、モードを選びます。モード用フラグを複数指定した場合は、`--info`、`--export-tokenizer`、`--selfcheck`、`--kld-eval`、`--dump-ref`、`--bench`、`--serve`、直接生成の順に先に一致した処理へ進みます。`--version` と `--help` は解析中に即時終了します。

server と直接生成では `--native`（別名 `--model`）で指定したモデルを開き、選択された backend を初期化します。server は `--parallel` で指定された slot を確保して `INFO` と `READY` を標準出力へ返し、標準入力の要求を継続処理します。直接生成は slot 0 を確保し、prompt を prefill した後、EOS/EOT token または生成数に達するまで token ID を出力します。モデル形式と backend によってロード・初期化・生成は失敗し得ます。

`--bench` は実際に model/backend を初期化して推論する計測モードです。既定の計測用 prompt 長は 64、生成長は 32 で、`--prompt-len` と `--gen` で変えられます。自己診断・ベンチマーク・生成は GPU または CPU backend の計算資源を使います。`--serve` の `--vision` 指定時は VisionShard を確認し、画像要求が来るまで Vision のメモリ確保を遅らせます。

tokenizer 書き出しは出力ディレクトリを作成し、空でない `chat_template.jinja` と `tokenizer.hf.json` を書き込みます。同名ファイルがある場合の保護や一時ファイル経由の置換は実装されていないため、既存ファイルを含むディレクトリを指定しないでください。

## オプションの文書

すべての root オプション文書は [CLI 索引の `strata-inkling` 節](../../../README.md#strata-inkling) にあります。実行モードの選択・モデル指定は [`--serve`](--serve.md)、[`--bench`](--bench.md)、[`--native`](--native.md) を参照してください。診断・情報確認には [`--info`](--info.md)、[`--selfcheck`](--selfcheck.md)、[`--verify-hash`](--verify-hash.md)、tokenizer 書き出しには [`--export-tokenizer`](--export-tokenizer.md) があります。prompt・生成数と実行構成は [`--prompt-ids`](--prompt-ids.md)、[`--gen`](--gen.md)、[`--parallel`](--parallel.md)、[`--max-context`](--max-context.md) の各文書を参照してください。

## 根拠

- `engine/src/inkling2/CMakeLists.txt:143-147` — `ink_main.cpp` を用いる `strata-inkling` 実行ファイルの定義。
- `engine/src/inkling2/ink_main.cpp:360-374` — 起動処理、serve 設定と各モード状態の初期化。
- `engine/src/inkling2/ink_main.cpp:379-502` — parser、別名、help の構文、未知 option のエラー処理。
- `engine/src/inkling2/ink_main.cpp:540-579` — モード選択の優先順、model/backend 初期化、server 分岐。
- `engine/src/inkling2/ink_main.cpp:575-613` — 直接生成の prompt、生成ループ、EOS/EOT 停止、token ID 出力。
- `engine/src/inkling2/ink_main.cpp:32-56` — tokenizer ファイル出力と失敗時の処理。
- `engine/src/inkling2/ink_main.cpp:130-164`、`:246-249` — benchmark の初期化、実行と計測結果出力。
- `engine/src/inkling2/ink_serve.h:441-485`、`:721-745` — serve の slot 準備、`INFO` / `READY`、標準入力を使う継続イベントループ。
- `docs/cli/README.md:1511-1547` — tool ID、CUDA/HIP root scope、概要リンク、root オプション文書。
- `docs/cli/000_cli_tools.md:12` — Inkling 向け CLI の入口と CUDA/HIP・Metal・SYCL の scope。

調査範囲は上記 revision の Strata 所有ソースと CLI 索引です。実機の GPU/backend ごとの起動可否や性能、protocol の外部利用側との互換性は実行・追加検証していません。
