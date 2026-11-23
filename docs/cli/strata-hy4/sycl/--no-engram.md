# `strata-hy4-sycl --no-engram`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL runner。`--serve` を付けた場合は line protocol モード） |
| オプション | `--no-engram` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

Hy4-Flash の Engram shard を runner に接続せず、Engram の検索・適用を無効にします。SYCL runner の単発実行と `--serve` のどちらにも反映されます。モデル本体の Engram metadata やレイヤー重みを読み込まなくするスイッチではありません。

## 使い方

```sh
# ids.txt の入力で単発実行し、Engram shard を使わない
strata-hy4-sycl --model SQ32.strata --tokens ids.txt --no-engram

# line protocol で起動し、指定済み shard があっても Engram を無効にする
strata-hy4-sycl --serve --native SQ32.strata --engram Engram-Q8.strata --no-engram
```

## 値と既定値

値は不要です。未指定時は `no_engram` が `false` で、`--engram` に渡されたパス（未指定なら空文字列）が runner の初期化へ渡ります。指定時は `no_engram` が `true` になります。フラグを複数回指定しても同じ真偽値を設定するだけです。`--no-engram` の直後に別の値を置く構文はなく、その値は別引数として扱われます。

parser は `--no-engram` を検出すると真偽値を立てます。`--engram` のパスも別途読み取りますが、実際の runner 初期化ではこのフラグが優先され、空のパスが渡されます。そのため引数順に関係なく、同時指定した `--engram FILE` も無効になります（`engine/src/hy4flash/sycl/sy_main.cpp:93-100`, `:153-155`, `:174`, `:226-248`, `:283-296`）。

## 実行時の動作

単発実行では `Runner::init` に空の Engram shard パスを渡します。`--serve` では `ServeOpts::no_engram` に値を渡し、serve 初期化時にも同様に空パスへ置き換えます（`engine/src/hy4flash/sycl/sy_main.cpp:226-248`, `:283-296`; `engine/src/hy4flash/sycl/sy_serve.h:28-40`, `:262-269`）。

`Runner::init` は shard パスが空なら `eio.open` を呼ばず、`engram_ready` を立てません。以降の `engram_mod_of` は `-1` を返すため、推論時に Engram layer は適用されず、prefetch も `engram_ready` が偽なら何もしません（`engine/src/hy4flash/sycl/sy_graph.h:585-590`, `:673-675`, `:810-815`）。単発実行の終了時に出す Engram 統計も、`engram_ready` が真の場合に限られるため、このフラグ指定時には出ません（`engine/src/hy4flash/sycl/sy_main.cpp:607-611`）。

## 適用条件と副作用

- 単発実行・`--serve` の両方で有効です。SYCL runner 専用の parser にあるため、CUDA/HIP 版や Metal 版の同名オプションについてはこの文書の対象外です（`engine/src/hy4flash/sycl/sy_main.cpp:174`, `:226-248`, `:283-296`）。
- shard のファイルを開かなくなりますが、`Runner::init` は引き続きモデル側の Engram metadata を読み込み、4 つの Engram layer の関連テンソルを取得してデバイスバッファへコピーします（`engine/src/hy4flash/sycl/sy_graph.h:585-616`）。従って、モデル側に必要な metadata / tensors がない場合まで救済するフラグではありません。
- `--engram` と同時指定してもエラーにはならず、runner には空パスが渡されます。`--engram` ファイルの存在・内容検査は `eio.open` を呼ばないため行われません（`engine/src/hy4flash/sycl/sy_main.cpp:153`, `:294`; `engine/src/hy4flash/sycl/sy_graph.h:587-590`）。
- 起動時にモデル初期化が失敗した場合、単発実行は `init: <理由>` を stderr に出して終了コード 1、serve は protocol 出力に `ERR init: <理由>` を出して終了コード 1 になります（`engine/src/hy4flash/sycl/sy_main.cpp:294-297`; `engine/src/hy4flash/sycl/sy_serve.h:267-270`）。引数として未知の option を渡した場合は stderr に `unknown arg ...` を出して終了コード 2 です（`engine/src/hy4flash/sycl/sy_main.cpp:190-194`）。

## 出力とエラー

このフラグ自体について専用の警告・成功メッセージは確認できません。単発実行では Engram が有効な場合に限り終了時に出る `[engram] ...` 統計行が抑止されます（`engine/src/hy4flash/sycl/sy_main.cpp:607-611`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:93-100`, `:153-155`, `:174`: parser の状態変数、`--engram` と `--no-engram` の登録。
- `engine/src/hy4flash/sycl/sy_main.cpp:226-248`, `:283-296`: serve option への転送と単発 runner 初期化での空パス選択。
- `engine/src/hy4flash/sycl/sy_serve.h:28-40`, `:262-270`: serve option の保持と serve runner 初期化。
- `engine/src/hy4flash/sycl/sy_graph.h:585-616`, `:673-675`, `:810-826`: shard の open 条件、モデル側 Engram 初期化、無効時の検索・layer 適用抑止。
- `docs/cli/README.md:1452-1507`: SYCL の command scope と `--no-engram` の索引リンク。`docs/cli/000_cli_tools.md:11`: tool ID と parser の所在。

調査範囲は対象 revision の SYCL runner 実装です。実機での挙動確認や help 実行は行っていません。
