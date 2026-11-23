# `strata-hy4-sycl --serve`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL backend、トップレベル） |
| オプション | `--serve` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

通常の単発推論ではなく、HY4 SYCL engine を標準入力・標準出力の行プロトコルで起動するモードを選びます。モデルをロードして `INFO` と `READY` を出力した後、`GEN` 要求を受け付け、生成中の状態や token、完了情報を標準出力へ返します。ソースで確認できるこの入口は stdin/stdout を使う engine protocol で、`--serve` 自体が TCP listener やポートを設定する処理はありません（`engine/src/hy4flash/sycl/sy_serve.h:4-9, 53-62, 331-345`）。

## 使い方

```sh
# SYCL engine を起動し、対話的に要求を送る
strata-hy4-sycl --serve --native SQ32.strata --engram Engram-Q8.strata

# 最大コンテキストと draft モードも指定して起動
strata-hy4-sycl --serve --native SQ32.strata --max-context 65536 --draft off
```

`--native` の代わりに `--model` も受理されます。起動後の stdin プロトコルは概ね `GEN <max_new> [key=value ...] <token-id,...>`、停止要求は `STOP`、終了要求は `QUIT`（または stdin の EOF）です。tokenizer や会話テンプレートを使った高水準の HTTP API ではなく、engine が受理する token ID を送るインターフェースです（`engine/src/hy4flash/sycl/sy_main.cpp:129-132, 215-248`; `engine/src/hy4flash/sycl/sy_serve.h:4-9, 112-171, 335-345`）。

## 値と既定値

`--serve` は値を取らず、引数列に存在するかどうかで serve mode を有効化します（`engine/src/hy4flash/sycl/sy_main.cpp:105-106, 129`）。serve mode では `--native FILE.strata` または同義の `--model FILE.strata` が必須です。欠けている場合は stdout に `ERR --native FILE.strata is required` を出し、終了コード 2 を返します（同 `:130, 215-220`）。

このフラグ自体に既定値・数値範囲・空値の検査はありません。値を要求する他の引数の値変換は `atoi` / `atof` に依存します。serve mode の主な既定値は、`--max-context` が 131072、`--chunk` が GPU の global memory 11 GiB 以上なら 4096、それ未満なら 2048、`--draft` が `auto` です（同 `:131, 179, 226-244`）。`--draft` に指定できる文字列は `off`、`dfly2`、`auto` で、それ以外は stdout の `ERR` と終了コード 2 になります（同 `:221-224`）。

## 実行時の動作

引数を走査して `--serve` を見つけると serve mode を記録し、他の engine 引数を解析した後に `ServeOpts` を組み立てて `hy4s_serve_main` を呼びます。モデルのロード、Runner 初期化、専門家 weight の配置などを行ってから `INFO ... backend=sycl ...` と `READY <max_context> stop` を stdout に出し、stdin の行を処理します（`engine/src/hy4flash/sycl/sy_main.cpp:105-106, 129-189, 215-248`; `engine/src/hy4flash/sycl/sy_serve.h:236-333`）。GPU 実行環境は SYCL device と queue を使い、起動時の device 選択には `ONEAPI_DEVICE_SELECTOR`、`HY4S_BACKEND`、`HY4_GPUS` および `--gpu` / `--gpus` が関係します（`engine/src/hy4flash/sycl/sy_main.cpp:79-92, 199-213, 245-248`）。

stdin の `GEN` 要求は token ID と sampling 用 key を解析し、prefill chunk ごとの `PP`、生成 token ごとの `T`、最後に `DONE` を返します。`STOP` は別スレッドで受け付け、処理境界で要求をキャンセルします。`QUIT` または stdin EOF でループを抜け、プロセスを終了します（`engine/src/hy4flash/sycl/sy_serve.h:64-102, 112-171, 335-345, 428-531`）。`--session-reuse` を有効にすると、画像を含まない後続要求の prefix が resident KV と一致する場合に再利用します。これは `--serve` とは独立したオプションです（同 `:8-9, 408-424, 523-526`）。

## 適用条件と副作用

- `--serve` は SYCL 版 `strata-hy4-sycl` のトップレベル引数です。Metal/HIP 版や別ツールの同名オプションの動作はこの文書の対象外です（`engine/src/hy4flash/sycl/sy_main.cpp:1, 79-80, 215-248`）。
- モデル・Runner・GPU/SYCL 資源をロードし、要求に応じて推論を実行します。プロトコル出力は stdout、GPU 情報や load 時間などの診断は stderr に出ます（`engine/src/hy4flash/sycl/sy_serve.h:236-247, 280-312, 331-345`）。
- server mode で認識されない引数は stderr に `unknown arg ...`、stdout に `ERR unknown flag ...` を出し、終了コード 2 で起動を拒否します（`engine/src/hy4flash/sycl/sy_main.cpp:190-197`）。値を取る引数で値が欠ける場合は stdout に `ERR <option> needs a value` を出して終了コード 2 です（同 `:108-115`）。
- モデルを開けない場合は `ERR cannot load ...` を stdout に出してコード 1、初期化・専門家設定の失敗も `ERR ...` を出して終了します。`--draft dfly2` はモデルに drafter tensor がない場合や chunk が 8 未満の場合にコード 2 で拒否されます（`engine/src/hy4flash/sycl/sy_serve.h:243-285`）。
- ソース上の serve loop は標準入出力を使います。ネットワーク bind、port、認証の設定はこのオプションの処理では確認できません（同 `:53-62, 64-102, 335-345`）。

## 出力とエラー

起動成功時の標準出力は `INFO`、`READY`、要求に応じた `PP` / `T` / `DONE` 等の protocol line です。要求形式や prompt に問題がある場合は `ERR ...` を返して次の要求を処理します。GPU/SYCL 例外は `ERR sycl: ...` として返し、終了コード 1 になります（`engine/src/hy4flash/sycl/sy_serve.h:53-62, 331-345, 380-391, 532-535`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:105-106, 129` — `--serve` を値なしフラグとして認識。
- `engine/src/hy4flash/sycl/sy_main.cpp:130-189, 215-248` — serve 用引数の解析、必須 model の確認、既定値を含む `ServeOpts` 構築と handler 呼び出し。
- `engine/src/hy4flash/sycl/sy_serve.h:236-333` — SYCL モデルと実行資源の初期化、`INFO` / `READY` の出力。
- `engine/src/hy4flash/sycl/sy_serve.h:64-102, 112-171, 335-345, 428-535` — stdin protocol、要求処理、標準出力、終了・失敗経路。
