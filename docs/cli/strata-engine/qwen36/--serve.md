# `--serve`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 (`qwen35moe`) 経路、または `strata-q36` |
| オプション | `--serve` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

Qwen3.6 エンジンを一度初期化してプロセス内に保持し、標準入力の行プロトコルで推論要求を受け付けるモードを選びます。`strata` は `--model` / `--native` が指す GGUF の architecture を読んで `qwen35moe` と判定した場合、この専用実装へ引き渡します。Qwen3.6 用の引数を渡す通常の使い方では、起動後に `READY` を標準出力へ返し、その後 `GEN` / `GENI` 等の要求行に対してトークン行と `DONE` を出力します。ターミナル向けの対話 UI を開始するスイッチではありません（`engine/src/program/generate.cpp:3805-3818`、`engine/src/qwen35/q36_engine.cu:4720-4724,5281-5299`）。

## 使い方

```sh
# Qwen3.6 GGUF を指定して標準入出力プロトコルで起動
strata --model /models/qwen36.gguf --serve

# 専用実行ファイルを使う場合（ビルド構成により利用可能）
strata-q36 --model /models/qwen36.gguf --serve
```

どちらもモデルを指定しないと起動エラーになります。呼び出し元プログラムは標準入力・標準出力を接続し、`READY` を待ってから要求行を送る必要があります。サーバー側の `StrataEngine` は実際に `[exe, "--serve", *args]` として子プロセスを起動し、標準入出力を pipe につなぎます（`terminal/serve/server.py:720-726,831-835,843-869`）。

## 値と既定値

- 値は不要です。parser は `--serve` を見つけると `serve_mode = true` にし、複数回指定しても同じ真偽値のままです（`engine/src/qwen35/q36_engine.cu:5346-5364`）。
- `--serve` 自体に既定で有効な状態はありません。指定しない場合は後続の `--tokens` / benchmark 経路などが選ばれます。
- モデル指定は別途必須です。`--model` / `--native` が空なら `strata-q36: --model is required` を stderr に出して終了コード 2 になります（`engine/src/qwen35/q36_engine.cu:5354-5355,5420`）。

## 実行時の動作

1. parser が `--serve` を記録します。Qwen3.6 用の `--model` / `--native`、コンテキストや配置など他の認識済み引数も同じ parser で処理します（`engine/src/qwen35/q36_engine.cu:5348-5404`）。
2. モデルを読み込み、Engine を初期化し、experts を配置します。モデル読み込み例外・失敗は stderr に理由を出して終了コード 1、expert 配置失敗も stderr に理由を出して終了コード 1 です（`engine/src/qwen35/q36_engine.cu:5458-5465,5522-5526`）。
3. 指定がなければ warmup を行い、その後 `serve_mode` が真なら serve loop に入ります。この判定は benchmark と `--tokens` の処理より前なので、`--serve` とそれらを同時に指定した場合も serve 経路が優先されます。ただし model load・初期化・warmup は省略されません（`engine/src/qwen35/q36_engine.cu:5555-5563,5595-5597`）。
4. serve loop は、複数 session のとき `INFO batch_slots=...`、expert 情報があるときその `INFO` 行を出し、続けて `READY <context> stop` を stdout に出します。別スレッドが stdin を行単位で読み、空行以外の制御行を処理します（`engine/src/qwen35/q36_engine.cu:5281-5299,5300-5328`）。
5. `GEN <max_new> [key=value ...] <token ids>` はテキスト要求、`GENI ... <embedding-file> <token ids>` は画像入力要求です。要求ごとに `T <id>` を stdout に逐次出力し、完了時に `DONE ...` を出します。prompt の再利用・session 状態もエンジン内に保持します（`engine/src/qwen35/q36_engine.cu:5004-5011,5060-5089,5091-5114,5226-5235,5264-5278`）。

要求ごとの `max_new`、token id、context 超過、語彙範囲、画像要求時の `--vision` 条件は serve loop 内で検査されます。`--batch N`（別文書）は複数 session の挙動を有効にし、通常の要求行のほか batch 用制御行も処理されます（`engine/src/qwen35/q36_engine.cu:4720-4724,5014-5023,5067-5089,5316-5325`）。

## 適用条件と副作用

- `strata` の汎用 engine 入口では、`--model` または `--native` が示す先頭 GGUF shard の architecture が `qwen35moe` の場合にだけ Qwen3.6 parser へ分岐します。その他の model はこの parser を通りません（`engine/src/program/generate.cpp:3804-3819`）。
- 起動中はモデル・Engine・session state をプロセス内に保持し、標準入力を待ち続けます。`--serve` 自体による server socket の bind はこの実装にはなく、通信は stdin/stdout です（`engine/src/qwen35/q36_engine.cu:5281-5299`）。モデル読込や GPU / expert 配置の副作用は起動時に発生します。
- `--no-warmup` が同時指定されると warmup は行いません（`engine/src/qwen35/q36_engine.cu:5561-5562`）。`--batch-mtp` など他の Qwen3.6 引数は別途条件を満たす場合に serve の動作へ影響します。
- serve mode で未知の `--long-option` が parser に現れた場合、次の引数が `--` で始まらなければその値と一緒に stderr へ「ignoring … (not an option of this engine)」と出して読み飛ばします。未知引数が `--serve` より前にあるとこの寛容分岐は有効でなく、usage を stderr に出して終了コード 2 になります（`engine/src/qwen35/q36_engine.cu:5405-5417`）。

## 出力とエラー

- 起動成功後の stdout は機械可読プロトコルです。起動時の `READY <context> stop`、生成中の `T <id>`、完了時の `DONE ...` を利用側が読みます。batch 使用時は追加の `INFO` / `BT` / `BDONE` 等もあります（`engine/src/qwen35/q36_engine.cu:5281-5285,5190-5217,5226-5268`）。
- stderr には起動失敗、未知引数の警告、要求処理の統計などが出ます。壊れた要求形式は `ERR expected: ...`、不正な `max_new` / 空 token 列、context 超過、範囲外 token id、vision 無効時の画像要求はそれぞれ `ERR ...` 行を stdout へ返し、その要求を終了します。これらはserveプロセス自体を直ちに終了させる経路ではありません（`engine/src/qwen35/q36_engine.cu:5007-5010,5067-5089,5316-5325`）。
- stdin が EOF になり、処理中の要求がなくなると serve loop は終了コード 0 で戻ります（`engine/src/qwen35/q36_engine.cu:5286-5298,5300-5312`）。

## 根拠

- `engine/src/program/generate.cpp:3804-3819` — 汎用 `strata` から Qwen3.6 parser への architecture 判定と dispatch。
- `engine/src/qwen35/q36_main.cpp:1-5`、`engine/include/strata/qwen35/engine.hpp:6-13` — 専用 `strata-q36` entry が共通 `strata::qwen35::run` を呼ぶこと。
- `engine/src/qwen35/q36_engine.cu:5339-5420` — Qwen3.6 parser、フラグ受理、serve 時の未知 option 処理、model 必須条件。
- `engine/src/qwen35/q36_engine.cu:5456-5526,5555-5563` — validation、モデル・Engine 初期化、serve 選択順序。
- `engine/src/qwen35/q36_engine.cu:4720-4724,5004-5089,5281-5335` — serve protocol と要求・応答・失敗経路。
- `terminal/serve/server.py:720-726,831-869` — Terminal server 側での子プロセス起動、pipe 接続、`READY` 待機。CLI parser の定義ではなく利用側の根拠。
