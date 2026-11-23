# `strata-hy4-sycl --engram`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL 実行ファイル、サブコマンド階層なし） |
| オプション | `--engram` |
| 別名 | なし |
| 値 | Engram shard の `.strata` ファイルパス（文字列） |

## 役割

Hy4-Flash モデルに対応する Engram shard を指定する。SYCL runner はモデル側の Engram metadata を使って入力 token の n-gram row ID を計算し、この shard から row データを取得してモデルの Engram 層に適用する。通常の token 推論と `--serve` の line protocol の両方で利用できる。`--no-engram` を同時に指定すると、`--engram` の値が渡されていても shard を開かない。

## 使い方

```sh
# token ID ファイルを推論し、Engram shard を使う
strata-hy4-sycl --model SQ32.strata --engram Engram-Q8.strata --tokens ids.txt

# line protocol server を起動し、リクエスト処理に Engram shard を使う
strata-hy4-sycl --serve --native SQ.strata --engram Engram-Q8.strata
```

実行ファイルの usage は通常実行で `--model ... --engram ... --tokens ...`、server 実行で `--serve --native ... --engram ...` の形を示す。parser では `--native` と `--model` が同じモデル値に設定される（`engine/src/hy4flash/sycl/sy_main.cpp:130,252`）。

## 値と既定値

値は次の argv 要素からそのまま文字列として受け取る。省略時の値は空文字列で、空のままなら Engram shard を開かず Engram I/O は無効になる。値が後続引数なしで終わる場合は `ERR --engram needs a value` を stdout に出し、終了コード 2 で終了する（`engine/src/hy4flash/sycl/sy_main.cpp:93,109-115,153`）。同じオプションを複数回指定した場合、parser は各回とも同じ変数へ代入するため最後の値が残る（同 `:107-115,153`）。

パスの拡張子やファイル存在を parser 段階では検証しない。値が空でなければ `Runner::init` から `EngramIO::open` へ渡され、そこでファイルを開き、EngramShard profile と Section 4 の 4 KiB alignment を確認する（`engine/src/hy4flash/sycl/sy_graph.h:585-589`、`engine/src/hy4flash/run/hy4_engram.cpp:446-460`）。

## 実行時の動作

通常実行では `--engram` の値を `engram` 文字列に保存し、`Runner::init` に渡す。`--no-engram` が有効なら空文字列へ置き換えてから渡す。`Runner::init` はまずモデル `.strata` の manifest から Engram metadata をロードし、shard パスが空でない場合にだけ shard を開いて `engram_ready` を立てる（`engine/src/hy4flash/sycl/sy_main.cpp:93,153,174,283-296`、`engine/src/hy4flash/sycl/sy_graph.h:585-590`）。したがって `--no-engram` は shard の利用を切るが、モデル manifest の Engram metadata 読み込み自体は省略しない。

Engram が有効な場合、各 token chunk の 4 module 分の hash row を計算し、shard から row を取得して SYCL device に転送する。該当層で row を正規化し、Engram 層の投影・適用を行う。chunk 処理では Engram fetch を非同期に先行できる経路がある（`engine/src/hy4flash/sycl/sy_graph.h:655-720,810-826,1382-1412`）。推論完了時は Engram が有効な場合に lookup、seed/LRU hit、page read、I/O 時間の統計を stderr に出す（`engine/src/hy4flash/sycl/sy_main.cpp:607-610`）。

`--serve` 経路も値を `ServeOpts` に保持し、serve runner 初期化時に shard を開く。`--no-engram` が有効ならこの経路でも空文字列を渡す（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`、`engine/src/hy4flash/sycl/sy_serve.h:262-269`）。

## 適用条件と副作用

- shard は EngramShard profile の `.strata` として開かれる。通常の POSIX 実装ではファイルを `O_RDONLY` で開き、Engram row page を読み込む（`engine/src/hy4flash/run/hy4_engram.cpp:353-382,446-460`）。
- モデルの Section 2 に互換 seed がある場合は、format ID、row byte 数、Section 4 の SHA-256 一致などの条件を満たすと seed として利用する。そうでない場合は seed を有効化せず shard から取得する（同 `:462-491`）。LRU row cache も初期化される（`engine/src/hy4flash/sycl/sy_graph.h:588`、`engine/src/hy4flash/run/hy4_engram.h:21,89-92`）。
- shard を有効にすると追加の host memory とストレージ読み込みが発生し、GPU へ row データを転送する。Engram の読み込み自体はモデルや shard を変更しない。
- `--no-engram` は `--engram` と併用でき、指定時には shard の open・row fetch を行わない。`--engram-cache-mib` は parser が値を読み捨てており、現行 SYCL parser では Engram cache size に影響しない（`engine/src/hy4flash/sycl/sy_main.cpp:142,174,294`）。

## 出力とエラー

通常実行でモデル load または `Runner::init` が失敗すると、`load: ...` または `init: ...` を stderr に出し終了コード 1 で終わる（`engine/src/hy4flash/sycl/sy_main.cpp:262-265,294-296`）。shard を開けない場合、誤った profile、または不整列の Section 4 offset などは open error となり、`init:` の経路へ伝わる（`engine/src/hy4flash/run/hy4_engram.cpp:446-460`）。row ID が範囲外、page read エラー、fetch 用 page buffer の確保失敗などは fetch error として伝播し、通常実行では `forward: ...` を stderr に出して終了コード 1、serve では protocol 出力 `ERR forward: ...` と終了コード 1 になる（同 `:557-602,625-640`、`engine/src/hy4flash/sycl/sy_graph.h:708-710,1382-1405`、`engine/src/hy4flash/sycl/sy_main.cpp:348-350`、`engine/src/hy4flash/sycl/sy_serve.h:432-453`）。

`--serve` では初期化エラーを protocol 出力 `ERR init: ...` として返し、終了コード 1 で終わる（`engine/src/hy4flash/sycl/sy_serve.h:262-269`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:93,107-115,153,174` — 値の保持、値必須処理、`--no-engram` の parser。
- `engine/src/hy4flash/sycl/sy_main.cpp:252,283-296,348-350` — usage、通常実行の shard 初期化・fetch error 表示。
- `engine/src/hy4flash/sycl/sy_graph.h:585-590,655-720,810-826` — metadata/shard 初期化、hash・fetch・転送、Engram layer 適用。
- `engine/src/hy4flash/run/hy4_engram.h:15-21,85-102` — Engram row/page/cache の形式と reader interface。
- `engine/src/hy4flash/run/hy4_engram.cpp:446-504,557-640` — shard profile/alignment の検証、seed 条件、row fetch とエラー。
- `engine/src/hy4flash/sycl/sy_serve.h:262-269,428-453` — server 経路の shard 初期化、chunk 処理と fetch error 出力。
- `engine/src/hy4flash/sycl/sy_main.cpp:607-610` — 有効時に出す Engram I/O 統計。
