# `strata-hy4 --no-engram`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP、root） |
| オプション | `--no-engram` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

Hy4-Flash の Engram shard を runtime に開かず、Engram row の読み込み・適用を無効にする。通常実行と `--serve` の両方で受理される。モデルに含まれる Engram metadata の読み込み自体は別処理で常に行われるため、このフラグはモデル内 metadata の検査やロードを省略する指定ではない（`engine/src/hy4flash/run/hy4_main.hip.cpp:397-399,483-495,544-565,703-705`、`engine/src/hy4flash/run/hy4_graph.hip.h:1658-1677`）。

## 使い方

```sh
# オフライン生成。指定した Engram shard を開かずに実行する
strata-hy4 --model SQ64.strata --engram Engram-Q8.strata --tokens ids.txt --gen 32 --no-engram

# server モードでも同じ指定を使用できる（モデルは必須）
strata-hy4 --serve --model SQ64.strata --engram Engram-Q8.strata --no-engram
```

この root parser には `--help` の処理がなく、未知の引数として終了する。利用可能な引数の例はオフライン経路の usage 表示に記載されている（`engine/src/hy4flash/run/hy4_main.hip.cpp:498-505,613-615`）。

## 値と既定値

値を取らない真偽フラグで、指定すると内部の `no_engram` が `true` になる。省略時は `false`。複数回指定しても同じ `true` の代入が繰り返される。明示的な値の検証や数値範囲検査はない。別途 `--engram FILE` を指定しても、最終的に runtime 初期化へ渡す shard path はこのフラグが優先される（`engine/src/hy4flash/run/hy4_main.hip.cpp:351,483-495,555-565,703`）。

## 実行時の動作

- オフライン実行では `r.init()` に空の path を渡す。`--engram` の値を指定していても、その shard は `EngramIO::open()` に渡らず、`engram_ready` は有効にならない（`engine/src/hy4flash/run/hy4_main.hip.cpp:483,493,692-705`、`engine/src/hy4flash/run/hy4_graph.hip.h:1658-1677`）。
- `--serve` では parser の値を `ServeOpts::no_engram` に渡し、server 初期化で同じく空の path を `r.init()` に渡す（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-565`、`engine/src/hy4flash/run/hy4_serve.hip.h:43-49,315-317`）。
- `Runner::init()` は shard path が空かどうかにかかわらず、モデル内の Engram metadata を読み込む。path が空でなければ cache 設定を決めて `eio.open()` を呼び、成功時に `engram_ready = true` とする（`engine/src/hy4flash/run/hy4_graph.hip.h:1658-1677`）。Engram 処理の実行箇所は `engram_ready` が真の場合に限られる（例: 同 `:1851-1853,3424-3432`）。
- parser はコマンドライン全体を読んでから実行経路を選ぶため、`--engram` と `--no-engram` の並び順で無効化の優先度は変わらない（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384,483,493,506-507,544-565`）。
- もともと `--engram` を指定しなければ path は空なので、shard を開かない点では `--no-engram` 省略時と同じ。この場合、フラグが追加で変える処理はない（同 `:347,483,493,703`）。

## 適用条件と副作用

CUDA/HIP の `strata-hy4` root parser のみを対象とする。索引では Metal と SYCL にも同名の option があるが、それらの parser と挙動はこの文書の対象外（`docs/cli/README.md:1277-1283,1322,1358-1362,1402,1452-1455`）。

フラグ自体はファイルを書き換えない。`--no-engram` が真なら指定された Engram shard を開かないため、その shard の open/profile 検査や Engram shard の行読み込みは発生しない。一方、`Runner::init()` によるモデル内 metadata の読み込みは行われる。モデルロードや GPU 初期化を省略するものではない（`engine/src/hy4flash/run/hy4_graph.hip.h:1437-1445,1658-1677`）。

## 出力とエラー

通常実行では `Runner::init()` が失敗すると `stderr` に `init: <理由>` を出し、終了コード 1 で終了する。`--no-engram` により shard を開かないため、その shard path に由来する open 失敗はこの経路では発生しないが、モデル metadata 等の初期化失敗は引き続き起こり得る（`engine/src/hy4flash/run/hy4_main.hip.cpp:702-705`）。server 経路では初期化失敗を `proto("ERR init: ...")` へ渡し、戻り値 1 となる（`engine/src/hy4flash/run/hy4_serve.hip.h:314-317`）。

## 根拠

- `docs/cli/README.md:1277-1283,1322` — `strata-hy4` CUDA/HIP root の索引節と対象リンク。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:347-353,375-384,483-505` — 初期値、引数読み取り、値なしフラグ、未知引数のエラー。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-565,611-615,692-705` — server と offline の分岐、値の転送、offline の初期化・失敗経路。
- `engine/src/hy4flash/run/hy4_serve.hip.h:43-49,262-317` — server option と初期化時の Engram 無効化。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1437-1445,1658-1677,1851-1853` — runtime 初期化、metadata の読み込み、shard を開く条件、Engram 準備の有効条件。
