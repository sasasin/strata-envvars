# `strata-split-N --batch`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（N = 2 / 3 / 4） |
| オプション | `--batch` |
| 別名 | なし |
| 値 | 整数。1 から `MAX_SLOTS`（8）まで |

## 役割

推論プロセスの同時リクエスト slot 数を指定する。値が 1 より大きい場合、sFNX は slot ごとの lane/session を用意し、複数リクエストを slot に割り当てて batched decoding を行える。これは `strata-split-N` の起動引数であり、通常の `strata` CLI の `--batch` とは別の parser・実装である（`engine/src/split/tools/sfnx.cpp:65-70, 448-458`）。

## 使い方

```sh
# 2 slot で sFNX サーバーを起動する例
strata-split-2 --serve --native MODEL.gguf --mtp MTP_RUNTIME_DIR --batch 2
```

`--serve`、`--native`、`--mtp` はこの例で使う起動引数である。DFlash2 を使う場合は同じ `--batch` 値が DFlash2 drafter のロード数にも渡される（`engine/src/split/tools/sfnx.cpp:73-93, 107-115, 1089-1091`）。

## 値と既定値

- 省略時は `1`。値 `1` は通常の単一リクエスト経路で、BGEN/BGENI の batch protocol は有効にならない（`engine/src/split/tools/sfnx.cpp:68, 994-997`）。
- 指定値は `1..8`。上限 `8` は `engine/src/split/tools/sfnx_input.hpp:17` の `MAX_SLOTS` で定義され、範囲外は `--batch must be 1..8` で拒否される（`engine/src/split/tools/sfnx.cpp:115`）。
- 値は必須で、次の引数がない場合は `<option> needs a value` のエラーになる。文字列から整数への変換には `std::stoi` を使う（`engine/src/split/tools/sfnx.cpp:76-81, 92`）。
- 同じ引数を複数回指定すると、走査中に `a.batch` が都度代入されるため最後の値が使われる（`engine/src/split/tools/sfnx.cpp:76-77, 92`）。
- `--batch=2` 形式は parser が認識せず、`unknown argument --batch=2` となる。オプション名と値を別々の引数として渡す（`engine/src/split/tools/sfnx.cpp:76-80, 92, 105`）。

## 実行時の動作

`--batch N` は `Args::batch` に格納され、モデル Engine に lane 数として渡される。Server は N 個の slot を確保し、追加 lane/session を用意して graph を warm up する。初期化後の標準出力 `INFO` 行には N が `batch_slots=N` として付く（N が 1 のときは表示しない）。起動情報は標準エラーにも slot 数を含めて出力される（`engine/src/split/tools/sfnx.cpp:448-458, 1131, 1142-1157`; `engine/src/split/src/engine.hpp:44-45, 140-143`）。

N が 2 以上なら、入力側は `BGEN` / `BGENI` を受け付け、要求された slot が範囲内かつ空いていることを確認してからその slot に割り当てる。slot は同時処理要求の上限であり、slot が不正または使用中の場合は `ERR BGEN: no such free slot ...` を標準出力へ返す（`engine/src/split/tools/sfnx.cpp:871-885, 990-1013`）。

## 適用条件と副作用

- 起動時に parser が値を検証するため、範囲外の値ではモデルロード前に失敗する。`--serve` と、通常の `--draft mtp` 経路で必要な `--native`・`--mtp` も別途必要（`engine/src/split/tools/sfnx.cpp:107-116, 1107-1116`）。
- slot 数に応じて Engine の lane 数、slot/session、warm graph を初期化するため、値を増やすと起動時の GPU/ホスト資源割当が増える。実際の必要量や各環境での最大安定値はソースだけでは一律に決められない（`engine/src/split/tools/sfnx.cpp:451-458, 1131`; `engine/src/split/src/engine.hpp:44-45, 140-143`）。
- `FNX_BATCH_DRAFTS` が `0` の場合、複数 slot の request batching 自体は可能だが、batched window に draft を含む `BatchDecoder` は作られない。`1`（未設定時の既定）または `lookup` では decoder を作成する（`engine/src/split/tools/sfnx.cpp:456-458`; `engine/src/split/src/engine_common.cu:1044-1052`）。対応する環境変数文書: [`FNX_BATCH_DRAFTS`](../../../envvars/FNX_BATCH_DRAFTS.md)。
- `--batch` は `strata-split-2` / `-3` / `-4` の共通 parser に登録されているが、実際に起動できる GPU 構成やメモリ条件はこの引数だけでは保証されない。実機での網羅的な条件は本調査では実行確認していない。

## 出力とエラー

- 引数の構文・値域・必須引数など parser 内のエラーは `sfnx: <理由>` を標準エラーへ出し、終了コード `2` で終了する（`engine/src/split/tools/sfnx.cpp:105-116, 1113-1116`）。
- Engine / Server 初期化後の例外は `ERR <理由>` を標準出力、`sfnx: failed: <理由>` を標準エラーへ出し、終了コード `1` で終了する（`engine/src/split/tools/sfnx.cpp:1097-1103, 1134-1135, 1161-1167`）。
- N が 1 のときに `BGEN` / `BGENI` が来ると、そのリクエストに対して `ERR ... sfnx runs without --batch` を標準出力へ返して処理を続ける（`engine/src/split/tools/sfnx.cpp:994-997`）。

## 根拠

- `engine/src/split/tools/sfnx.cpp:65-117` — `Args` の既定値、`--batch` の parser、整数変換、値域検証、他の起動条件。
- `engine/src/split/tools/sfnx_input.hpp:17` — slot 数の上限 `MAX_SLOTS = 8`。
- `engine/src/split/tools/sfnx.cpp:448-458, 871-885, 990-1016` — slot/session の初期化、batch request の受理・割当・失敗経路。
- `engine/src/split/tools/sfnx.cpp:1089-1091, 1131-1157` と `engine/src/split/src/engine.hpp:44-45, 140-143` — Engine / DFlash2 への値の伝達、起動時の lane・graph 準備と slot 数の表示。
- `engine/src/split/src/engine_common.cu:1044-1052` — `FNX_BATCH_DRAFTS` に応じた batched decoder の mode。

調査対象の Strata checkout は `git status --short --branch` で `## main...origin/main` と表示され、未コミット変更はなかった。CLI の `--help` は実行せず、parser とその使用箇所をソースで確認した。
