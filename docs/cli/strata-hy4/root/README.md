# `strata-hy4`（CUDA/HIP）

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4` |
| 入口 | CMake が生成する `strata-hy4` 実行ファイル |
| 主な実装 | `engine/src/hy4flash/run/hy4_main.hip.cpp`（引数解析・オフライン実行）、`engine/src/hy4flash/run/hy4_serve.hip.h`（serve モード） |

## 役割

Tencent Hy4-Flash 用の `.strata` 推論エンジンです。通常モードではモデルを GPU に読み込み、token ID ファイルをチャンク単位で prefill して次 token の上位候補を表示し、`--gen` が正なら通常は greedy decode を行います。`--draft dfly2` を選ぶと DFly2 speculative decode の経路に入ります。`--serve` では同じエンジンを標準入出力の行プロトコルで起動し、モデルを常駐させて複数の生成要求を受け付けます。モデル情報の表示、tokenizer 資料の書き出し、モデル読込だけの実行も別モードとして提供します。CMake ではこのターゲットは既定で無効で、CUDA または HIP を有効にしたビルドが必要です（`engine/CMakeLists.txt:846-852,884-908`）。

## 基本的な使い方

以下は実行ファイルが PATH 上にあり、各 `.strata` と token ID ファイルが用意されている環境での例です。

```sh
# token ID の prompt を評価し、greedy decode を最大 64 token 実行する
strata-hy4 --model ./model.strata --engram ./engram.strata --tokens ./prompt.ids --gen 64

# 常駐エンジンを起動し、親プロセスと標準入出力で要求・応答をやりとりする
strata-hy4 --serve --native ./model.strata --engram ./engram.strata

# GPU を使わずモデルの manifest 情報を一行で確認する
strata-hy4 --info ./model.strata

# GPU モデルを読み込んで初期化し、生成に進まず終了する
strata-hy4 --model ./model.strata --load-only
```

オフライン推論では `--tokens` に空白区切りの整数 token ID を記したファイルを渡します。サーバーモードは入力に `GEN <max_new> ... <ids>`、終了に `QUIT` などのプロトコル行を使います。モデルや補助データの指定など、個別オプションの値と動作は[CLI 索引の strata-hy4 節](../../README.md#strata-hy4)を参照してください。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| オフライン推論（既定） | `strata-hy4 --model MODEL --engram ENGRAM --tokens IDS --gen 64` | GPU を選択し、メモリ計画・モデル読込・Runner 初期化後、prompt を prefill します。`--gen` が正なら token を生成します。`--gen` の既定値は 0 なので、指定しない場合は prompt 評価までです。 |
| エンジン serve | `strata-hy4 --serve --native MODEL --engram ENGRAM` | GPU にモデルと Runner を常駐させ、stdout に `INFO` と `READY` を出した後、stdin の `GEN` 要求を処理します。`STOP` は実行中要求の停止、`QUIT` または EOF は終了です。HTTP listener はこの実行ファイルではなく、呼び出し元の Python Terminal 側が担います。 |
| 情報確認 | `strata-hy4 --info MODEL` | `.strata` manifest から architecture、層数、語彙数などを表示します。ソースコメント上、GPU 不要の経路です。`--info` と同時に `--vision SHARD` を指定すると、その shard の可用性も確認します。 |
| tokenizer の書き出し | `strata-hy4 --export-tokenizer MODEL DIR` | manifest の tokenizer JSON と chat template を `DIR/tokenizer.hf.json`、`DIR/chat_template.jinja` に書きます。GPU は使いません。 |
| バージョン表示 | `strata-hy4 --version` | バージョン文字列を表示して終了します。 |
| 読込のみ | `strata-hy4 --model MODEL --load-only` | オフライン経路で GPU モデルを読み込み、ロード時間を表示して生成初期化へ進まず終了します。 |

## 主な動作

- 引数は `main` 内で左から順に処理されます。`--serve` と `--model` / `--native` などから実行モードと設定を組み立てます。未知の引数は `unknown arg` を stderr に出して終了コード 2 になります。serve 中は加えて `ERR unknown flag` を stdout に出します。値が必要な引数で値が欠ける場合は `ERR ... needs a value` を stdout に出して終了コード 2 です（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-405,483-505`）。
- `--info`、`--version`、`--export-tokenizer` は通常の GPU 推論分岐より前に処理されます。tokenizer 出力ファイルはバイナリ書込みで開かれるため同名ファイルがあれば上書きされ、出力ディレクトリ自体はこの処理では作成されません。ファイルを開けない・書込みに失敗する場合はエラーを表示して非ゼロで終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:25-49,385-396,507`）。
- serve モードは `--native`（`--model` の別名）を必須とし、未指定時や `--draft` が `off` / `dfly2` / `auto` 以外のときはプロトコル用エラーを stdout に出して終了コード 2 です。設定を `ServeOpts` に渡して serve 処理へ進みます（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-577,611`）。モデル読込後、Runner を初期化し、`INFO` と `READY` を出して要求ループに入ります。開始時ロード失敗はプロトコル `ERR` と非ゼロ終了になります（`engine/src/hy4flash/run/hy4_serve.hip.h:291-317,365-384`）。
- serve の標準出力は `INFO` / `READY` / `GEN` への応答などプロトコル行です。通常ログは stderr に送られます。要求行の形式は `GEN <max_new> [key=value ...] [image=<path> ...] <ids>` で、不正な形式や負の `max_new` は `ERR` 応答になります（`engine/src/hy4flash/run/hy4_serve.hip.h:1-13,69-82,137-158,373-384`）。
- 通常モードでは指定 GPU の情報を stderr に表示し、token ID ファイルを読み込みます。context が未指定なら token 数と生成数から上限を決め、カード情報と指定値を使って chunk を計画します。モデルと DFly override をロードした後、`--load-only` ならそこで終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:613-665`）。
- 通常の推論では画像を使う場合に画像を CPU で準備し、`--vision` とともに image placeholder を展開します。続いて Runner を初期化し、prompt を chunk ごとに forward して prefill の進捗を stderr に、最後の位置の top-5 token を stdout に出します。`--dump` または `--save-logits` を指定した場合、logits を `<out>/logits.npy` に保存します（`--out` の既定値は `.`）。`--gen` が正なら続けて decode します（`engine/src/hy4flash/run/hy4_main.hip.cpp:347-352,632-705,748-790,1018-1079`）。
- `--image` を通常モードで使うには `--vision` が必要です。画像の準備失敗や shard 欠落はエラーを表示して終了します。serve で画像を含む要求を扱うには起動時の `--vision` shard が必要で、未指定・不正 shard の場合、その要求に `ERR image` が返ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:666-685`; `engine/src/hy4flash/run/hy4_serve.hip.h:355-364,392-416`）。

## オプションの文書

CUDA/HIP 版のルートオプションは[CLI 索引の strata-hy4 節](../../README.md#strata-hy4)にまとめています。ここではコマンド全体のモードを説明し、各オプションの値・既定値・詳細な効果は個別文書に委ねます。

## 根拠

- `engine/CMakeLists.txt:846-852,884-908` — ターゲットの役割、CUDA/HIP のビルド条件、ターゲット構成。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:25-87` — tokenizer 書出し、GPU 不要の情報表示と出力。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:334-505` — parser の既定値、主なモード分岐、引数エラー。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:543-705,748-790,1018-1079` — serve 設定、GPU 読込、オフライン prefill / decode と出力。
- `engine/src/hy4flash/run/hy4_serve.hip.h:1-13,291-317,365-384` — Python Terminal とのプロトコル境界、モデル初期化、serve 要求ループ。
- `engine/src/hy4flash/run/hy4_serve.hip.h:137-158,390-429` — `GEN` 要求構文、入力 validation、画像・prompt の失敗応答。

調査範囲は CUDA/HIP 版の `strata-hy4` です。Metal と SYCL は別 parser・別実行ファイルのため、この概要には含めていません。コマンドの組込み help 表示は確認しておらず、CLI 構文と動作は対象 revision の parser および処理コードに基づいています。
