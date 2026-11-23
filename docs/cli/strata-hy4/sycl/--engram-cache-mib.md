# `strata-hy4-sycl --engram-cache-mib`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4-sycl` |
| コマンド | `strata-hy4-sycl`（トップレベル。通常実行と `--serve` の両方） |
| オプション | `--engram-cache-mib` |
| 別名 | なし |
| 値 | 次のコマンドライン引数を1個受け取る。値の形式・範囲は検証されない |

## 役割

このオプションは引数として受理されるものの、SYCL runner では値を読み取って破棄するため、Engram cache の容量を設定しない。Engram shard を開く場合の SYCL LRU cache 行数は `ENGRAM_DEFAULT_LRU_ROWS` の固定値で決まり、このオプションの値による変更はない。容量を調整できるように見える名前ですが、現行実装では効果がありません。

## 使い方

```sh
# 引数としては受理されるが、SYCL Engram cache 容量は変わらない
strata-hy4-sycl --model model.strata --engram engram.strata --tokens ids.txt --engram-cache-mib 512
```

## 値と既定値

- `--engram-cache-mib` の直後にある引数を値として消費します。数値変換や範囲検証はなく、文字列は保存も利用もされません。そのため `0`、負数、数値でない文字列を指定しても、このオプション自体による拒否や容量変更はありません。
- オプションを複数回指定しても各回の値を読み捨てます。
- 値を省略すると parser の `nxt()` が標準出力に `ERR --engram-cache-mib needs a value` を出し、終了コード `2` で終了します。次の引数が別のオプション表記でも値として消費されます。
- このオプションが設定する既定値はありません。Engram shard が開かれる経路では SYCL runner が `hy4::ENGRAM_DEFAULT_LRU_ROWS`（6,000,000 行）を `EngramIO::open` に渡します。

## 実行時の動作

parser は `--engram-cache-mib` を認識すると `nxt()` で次の引数を取り出し、戻り値を破棄します（`engine/src/hy4flash/sycl/sy_main.cpp:109-115,142`）。通常実行と `--serve` は同じトップレベル parser を通ります。`--serve` のときもこの値は `ServeOpts` に格納されず、serve 側の `Runner::init` に別の cache 容量指定が渡ることもありません（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`、`engine/src/hy4flash/sycl/sy_serve.h:262-267`）。

通常実行では、Engram が無効化されておらず `--engram` で shard が指定されている場合に `Runner::init` が Engram を開きます。ここでは常に `hy4::ENGRAM_DEFAULT_LRU_ROWS` を渡します。定数は 6,000,000 行で、定義コメントは行データとキー・テーブルを合わせて約 836 MiB の予算としています（`engine/src/hy4flash/sycl/sy_main.cpp:153,174,294-296`、`engine/src/hy4flash/sycl/sy_graph.h:585-590`、`engine/src/hy4flash/run/hy4_engram.h:15-21`）。`--no-engram` が有効なら通常実行側は空の shard パスを渡すため、Engram I/O cache 自体を開きません（`engine/src/hy4flash/sycl/sy_main.cpp:174,294`）。serve 側も `no_engram` に応じて同様に空パスを渡します（`engine/src/hy4flash/sycl/sy_serve.h:267`）。

同名オプションの別 backend での処理はこの文書の対象外です。SYCL parser 内では環境変数 `HY4_ENGRAM_CACHE_MIB` の設定・参照は行われず、HIP runner にある同名環境変数処理からも独立しています。

## 適用条件と副作用

- オプションの値は通常実行・serve のどちらでも Engram cache 設定に適用されません。値を環境変数へ書き込まず、ファイルや cache を直接操作する副作用もありません。
- 実際の Engram cache 初期化は `--engram` の指定と `--no-engram` の状態に依存します。Engram shard の読み込みに失敗した場合は、通常実行では `init: <理由>` を標準エラーに出して終了コード `1` で終了します。これは当オプションの値の validation error ではありません（`engine/src/hy4flash/sycl/sy_main.cpp:294-296`）。serve 経路も `Runner::init` 失敗時にエラーを返します（`engine/src/hy4flash/sycl/sy_serve.h:262-268`）。

## 出力とエラー

- 値がある場合、このオプション自体は出力しません。
- 値がない場合は標準出力に `ERR --engram-cache-mib needs a value` を出して終了コード `2` になります（`engine/src/hy4flash/sycl/sy_main.cpp:109-115`）。
- 値の形式・範囲に関するエラー経路はありません。Engram shard の open/init エラーは上記の通り別経路です。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:105-115,142` — トップレベル引数 parser。値を1個消費して破棄し、値なしの場合は標準出力へエラーを出して終了する。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248` — `--serve` への分岐と `ServeOpts` の構築。cache 値を転送しない。
- `engine/src/hy4flash/sycl/sy_main.cpp:294-296` — 通常実行での Engram 初期化と失敗時の出力・終了コード。
- `engine/src/hy4flash/sycl/sy_serve.h:262-268` — serve 実行での `Runner::init` と失敗処理。
- `engine/src/hy4flash/sycl/sy_graph.h:585-590` — SYCL runner が Engram cache を初期化し、固定の LRU 行数を渡す箇所。
- `engine/src/hy4flash/run/hy4_engram.h:15-21` — `ENGRAM_DEFAULT_LRU_ROWS` の定義と容量に関するコメント。
