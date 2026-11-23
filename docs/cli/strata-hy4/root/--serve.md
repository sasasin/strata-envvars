# `--serve`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4` |
| オプション | `--serve` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

Hy4-Flash エンジンを一度起動してモデルを GPU に読み込み、標準入力から要求行を受け取り、生成トークンや進捗を標準出力へ返す常駐モードに切り替える。通常の `strata-hy4` のオフライン実行は `--tokens` などを使う推論経路だが、`--serve` を指定すると `hy4_serve_main` へ進む。HTTP API の待受を行うオプションではなく、上位の Python サーバーがこのエンジンを子プロセスとして起動し、標準入出力で通信する。

## 使い方

```sh
# Hy4-Flash の常駐エンジンを起動する。モデルファイルは利用環境のパスに置き換える。
strata-hy4 --serve --model ./model.strata
```

## 値と既定値

- `--serve` 自体は値を取りません。指定されると `serve` が `true` になり、指定しない場合は通常のオフライン処理へ進みます（`engine/src/hy4flash/run/hy4_main.hip.cpp:353,397,544,612-613`）。
- 同じフラグを複数回指定しても真偽値を `true` にするだけです。別名は parser にありません（同 `:397-401`）。
- serve モードでは `--model FILE`（別名 `--native FILE`）が必須です。省略時は標準出力に `ERR --native FILE.strata is required` を出して終了コード 2 で終了します（同 `:401,544-548`）。

## 実行時の動作

parser は `--serve` を検出するとフラグを立て、引数解析後に GPU 選択などを済ませてから serve 分岐に入ります。serve 用の `ServeOpts` を作り、モデル、コンテキスト長、chunk、Engram、session reuse、draft、vision、GPU などの関連設定を渡して `hy4_serve_main` を呼びます。モデル引数がない場合と不正な `--draft` 値は起動前に拒否されます。`--draft` は serve 経路で `off`、`dfly2`、`auto` のみ受理し、省略時は `auto` です（`engine/src/hy4flash/run/hy4_main.hip.cpp:361-364,397,401,406,544-577,611`）。

serve 本体は GPU の情報を stderr に記録し、モデル読み込みと Runner 初期化を行います。成功すると標準出力に `INFO ...` と `READY <max_context> stop` を返し、その後 `GEN` 要求を処理して `PP`（prefill 進捗）、`T`（token）、`DONE` などの行を返します。`QUIT` または stdin の EOF で要求ループを抜け、GPU 同期後に終了します（`engine/src/hy4flash/run/hy4_serve.hip.h:262-317,345-371,373-384,605-609`）。

Hy4 用の上位サーバー `terminal/serve/server.py` は `[exe, "--serve", *args]` を起動し、stdin/stdout を pipe に接続してエンジンと通信します（`terminal/serve/server.py:714-716,827-829`）。したがって、このフラグ単独で TCP ポートを開いたり、HTTP API を提供したりする動作はソース上で確認できません。

## 適用条件と副作用

- 対象は索引上 CUDA/HIP 実装として登録されている `strata-hy4` です。serve 分岐は GPU デバイス情報の取得、モデルの GPU 読み込み、Runner 初期化を伴い、プロセス終了までエンジンを常駐させます（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-611`; `engine/src/hy4flash/run/hy4_serve.hip.h:262-317`）。
- モデル読み込みや初期化に失敗すると、標準出力に `ERR ...` を返して終了コード 1 になります。具体的にはモデル読み込み失敗で `ERR cannot load ...`、Runner 初期化失敗で `ERR init: ...` です（`engine/src/hy4flash/run/hy4_serve.hip.h:294-303,314-317`）。
- `--serve` は他の CLI 引数と同じ引数列で解析されます。serve モードで未知の引数に遭遇すると stderr に `unknown arg ...`、stdout に `ERR unknown flag ...` を出し、終了コード 2 で終了します。値を必要とする別オプションの値が欠けている場合は `ERR <option> needs a value` を stdout に出し、終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384,498-505`）。
- 引数解析中に未知引数が `--serve` より先に現れると、その時点では `serve` が未設定のため `ERR unknown flag` 行は出ず、stderr の診断と終了コード 2 のみになります（同 `:397-399,498-505`）。
- 要求行の形式不正や対応外キーは `ERR ...` を返して次の要求へ進みます。推論中の forward 失敗は `ERR forward: ...` を返して終了コード 1 になります（`engine/src/hy4flash/run/hy4_serve.hip.h:373-384,527-530,597-600`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:353,375-405` — `serve` の初期値、引数解析、`--serve` が値なしフラグであること、およびモデル指定 parser。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-577,611-613` — serve 分岐、必須モデルと draft の検査、`ServeOpts` への設定、および非 serve 経路との分岐。
- `engine/src/hy4flash/run/hy4_serve.hip.h:262-317,345-384,605-609` — GPU/model/Runner の初期化、`INFO`/`READY` と要求ループ、終了処理。
- `engine/src/hy4flash/run/hy4_serve.hip.h:527-530,597-600` — 推論失敗時の `ERR` 出力と終了コード。
- `terminal/serve/server.py:714-716,827-829` — 上位サーバーが `--serve` を付けたエンジンを起動し、標準入出力を pipe 接続する箇所。
