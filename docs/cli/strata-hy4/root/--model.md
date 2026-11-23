# `--model`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP root） |
| オプション | `--model` |
| 別名 | `--native` |
| 値 | 読み込むモデル `.strata` ファイルのパス。必須（既定値なし） |

## 役割

推論エンジンが読み込む Hy4-Flash モデルファイルを指定する。通常のオフライン実行では GPU 上のモデル読み込みと推論の基礎になり、`--serve` ではサーバー起動時に同じモデルをロードする。これは CUDA/HIP 実装の root オプションであり、Metal と SYCL は索引上の別スコープである。

## 使い方

```sh
# オフライン実行: モデルと Engram shard、token ID 列を指定
strata-hy4 --model ./Hy4-Flash-SQ-64.strata --engram ./Hy4-Flash-Engram-Q8.strata --tokens ./ids.txt

# サーバーモード: モデルと Engram shard を指定
strata-hy4 --serve --model ./Hy4-Flash-SQ-64.strata --engram ./Hy4-Flash-Engram-Q8.strata
```

## 値と既定値

- 値は次の argv 要素をそのままファイルパス文字列として受け取る。別名 `--native` も同じ変数に設定する。既定値はなく、複数回指定した場合は後の値が前の値を置き換える（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384,401`）。
- parser 段階では拡張子、存在、空文字列を個別検証しない。値を省略してオプションが末尾にある場合は `ERR --model needs a value` を stdout に出して終了コード 2 で終了する。空文字列やモデル未指定は、後段の必須確認で未指定として扱われる（同 `:377-384,544-548,613-615`）。

## 実行時の動作

- `--serve` の場合、値を `ServeOpts::model` に渡し、serve 側が `plan_memory` と `load_gpu_model` に利用する。読み込みに失敗すると `ERR cannot load <path>` をプロトコル出力して終了コード 1 となる（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-577,611`、`engine/src/hy4flash/run/hy4_serve.hip.h:291-296`）。
- 通常実行では GPU メモリ計画にモデルパスを渡し、`load_gpu_model` が `.strata` を開いて manifest と section 情報を読み、モデル重みを GPU または条件に応じて mapped host memory に読み込む。モデルを開けない、形式・ヘッダーを読めないなどの読み込み失敗時は stderr に理由を出し、呼び出し元は終了コード 1 で終了する（`engine/src/hy4flash/run/hy4_main.hip.cpp:648-659`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1267-1276,1336-1398`）。
- モデルファイルの読み込みは `StrataFileReader::open` が行い、ファイルをバイナリ読み込みで開き、4 KiB ヘッダー、Strata magic、section 数・alignment、manifest の読み込みを検査する（`engine/src/artifact/strata_reader.cpp:33-75`）。
- `--info FILE`、`--export-tokenizer FILE DIR`、`--version` の専用処理は引数走査後の通常ロードより先に戻るため、これらのモードでモデル情報を指定する位置引数・モード引数は `--model` とは別である（`engine/src/hy4flash/run/hy4_main.hip.cpp:385-396,507`）。

## 適用条件と副作用

- `--serve` ではモデル指定が必須で、未指定なら `ERR --native FILE.strata is required` を stdout に出して終了コード 2 となる。通常のオフライン経路では未指定時に usage を stderr に出して終了コード 2 となる（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-548,613-615`）。
- 指定ファイルを読み込み、メモリ計画に使う。parser にモデルファイルの拡張子制限はないが、後続の reader が Strata 形式としてのヘッダーと manifest を検査する。ファイル内容や GPU メモリなどによる読み込み条件の詳細は `load_gpu_model` に依存する。
- 本文書は索引で指定された CUDA/HIP root parser を対象とする。Metal と SYCL には別 parser・別文書スコープがあるため、そこにおける同名オプションの詳細は扱わない（`docs/cli/README.md:1277-1282,1358,1452`）。

## 出力とエラー

- オプション末尾で値が欠けると stdout に `ERR --model needs a value` を出力し、終了コード 2（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-382`）。
- モデル未指定時は serve で stdout に必須指定エラー、通常実行で stderr に usage を出し、いずれも終了コード 2（同 `:544-548,613-615`）。
- ファイルを開けない場合、reader は `Failed to open .strata file: <path>` 等の理由を返し、通常ロード経路は `open: <理由>` を stderr に出す。serve では protocol エラー `ERR cannot load <path>` が出力される（`engine/src/artifact/strata_reader.cpp:33-49`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1267-1274`、`engine/src/hy4flash/run/hy4_serve.hip.h:294-296`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:347-384,401` — モデル変数、値取得、`--model` と `--native` の同一 parser 分岐、値欠落時の処理。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-577,611-615,648-659` — serve/offline の必須条件、値の引き渡し、計画・ロード呼び出し。
- `engine/src/hy4flash/run/hy4_serve.hip.h:291-296` — serve でのモデル計画・ロード失敗経路。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1267-1276,1336-1398` — ファイルを開いて manifest を読み、重みを配置するロード処理とエラー。
- `engine/src/artifact/strata_reader.cpp:33-75` — Strata reader のファイル、header、manifest 検査。
- `docs/cli/README.md:1277-1282` — `strata-hy4` CUDA/HIP root の索引上の scope と `--model` / `--native` のリンク。
