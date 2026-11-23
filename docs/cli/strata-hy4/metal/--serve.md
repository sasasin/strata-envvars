# `strata-hy4-metal --serve`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4-metal` |
| コマンド | `strata-hy4-metal`（Metal runner のトップレベル呼び出し） |
| オプション | `--serve` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

`--serve` を指定すると、Metal runner はトークンファイルを一度処理する通常経路ではなく、標準入力から要求を受け取るエンジンの行プロトコル経路に入る。起動後は `INFO` と `READY` を標準出力に出し、`GEN` 要求に対して進捗・生成 token・完了行を返す。入力の `QUIT` または EOF で終了する。parser はこのフラグを `serve` に設定し、モデル読み込み後に server 実装へ分岐する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1504,1589,1611-1674`、`engine/src/hy4flash/metal/hy4_metal_serve.h:1-9,219-255,302-315,570-593`）。

## 使い方

```sh
# Metal runner を行プロトコルの待ち受け状態で起動する
./strata-hy4-metal --native /models/hy4.strata --serve
```

`--native` は `--model` と同じモデル変数に設定される。起動後の標準入力には `GEN <max_new> [key=value ...] <token-id,...>` を1行ずつ渡し、終了時は `QUIT` を送るか入力を閉じる（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1507-1508,1589-1591`、`engine/src/hy4flash/metal/hy4_metal_serve.h:4-9,52-80,100-159,310-317`）。

## 値と既定値

値は不要で、引数解析時に `serve = true` とする。指定しない場合は `serve` が `false` のままで、モデル読み込み後に通常のトークンファイル処理へ進む。複数回指定しても同じ真偽値を設定するだけで、追加の効果はない。値を伴う構文は定義されておらず、たとえば `--serve=1` や `--serve 1` は未知引数として扱われる（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1494,1504-1506,1589,1603-1609,1676-1681`）。

## 実行時の動作

`--serve` はモデルを省略可能にはしない。引数解析後にモデル名が空なら usage を stderr に出して終了コード 2、モデルのロードに失敗すればエラーを stderr に出して終了コード 1 となる。モデルロードと `--warm` の処理後、`--load-only` が指定されていれば server 分岐より先に終了するため、`--serve --load-only` ではプロトコル待ち受けを開始しない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1635`）。

server 分岐では、`ServeOpts` を組み立てて `hy4_serve_main` を呼ぶ。`--ctx` が正数なら最大 context に使い、それ以外は 131072。`--chunk` が正数なら使い、未指定または非正数なら cold-expert モードで 2048、それ以外で 4096 にする。`--tokens` と `--gen` は server 設定へ渡されず、通常経路のトークンファイル読み込みも分岐後にあるため、このモードの要求入力には使われない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1491,1504-1514,1642-1655,1674-1681`）。

server 側は `Runner` と KV 状態を初期化し、標準出力へ `INFO ...`、続けて `READY <max_context> stop` を出す。入力スレッドは標準入力の行をキューに入れ、`STOP` は生成を次の token / chunk 境界で止める要求、`QUIT` または EOF は server 終了として処理される。`GEN` 要求の成功時は `PP`、`T`、`DONE` 等を標準出力に返す。`proto()` は行を stdout に書いて flush し、診断ログは stderr に書かれる（`engine/src/hy4flash/metal/hy4_metal_serve.h:4-9,40-50,52-89,302-317,487-510,524-568,570-593`）。

## 適用条件と副作用

この option は `engine/src/hy4flash/metal/hy4_metal_main.cpp` の Metal runner に属し、起動時に Metal context を作成してモデルをロードした後、Metal runner の server loop を実行する（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1,1615-1623,1636-1674`）。server は標準入力を継続して読み、要求処理用の runner/KV 状態を保持する。`--session-reuse` が有効な場合は会話 slot を使い、spill が有効な構成ではディスク上の保存・再読込も行う。永続 spill の有効時は `QUIT` / EOF の終了処理で保持対象の会話状態を書き出すが、これらは関連 option の設定条件付きであり、`--serve` 単独では有効化されない（`engine/src/hy4flash/metal/hy4_metal_serve.h:227-231,263-276,375-461,570-592`）。

この実装の要求受付は `std::cin` の行入力である。ここで確認した server 実装には TCP listener の生成はなく、外部 server が本プロセスをどう起動・接続するかは本調査範囲では確認していない（`engine/src/hy4flash/metal/hy4_metal_serve.h:52-80,308-315`）。

## 出力とエラー

- 通常起動では `INFO` と `READY` が stdout に出る。各 `GEN` 要求は `PP` / `T` / `DONE`、または `ERR ...` のプロトコル行を返す（`engine/src/hy4flash/metal/hy4_metal_serve.h:40-50,302-304,315-317,485-495,514-520,559-568`）。
- Runner 初期化失敗は `ERR init: ...` を stdout に出して終了コード 1。`--draft dfly2` を指定して drafter がない場合や chunk が 16 未満の場合は `ERR ...` を出して終了コード 2（`engine/src/hy4flash/metal/hy4_metal_serve.h:233-252`）。
- 未知引数は `ERR unknown flag ...` を stdout、`unknown arg ...` を stderr に出して終了コード 2。指定された `--serve` 自体に個別の値検証や警告はない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1609`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1504,1589` — Metal runner の parser と `--serve` の真偽値設定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1676` — モデル必須条件、ロードと `--load-only` の先行処理、server 用設定、呼び出しと通常処理への分岐。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:1-9,219-255,302-317,570-593` — 行プロトコル、初期化・起動出力、要求ループ、終了処理。
- 索引では `strata-hy4-metal`（Metal; `engine/src/hy4flash/metal/hy4_metal_main.cpp`）の option として掲載されている（`docs/cli/README.md:1358,1430`）。
