# `SPLIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`SPLIT` は Strata エンジンが直接読む設定ではありません。同梱ツール `tools/batch_groups_cache_test.py` が、複数 GPU を指定して起動する場合の `layer_split` 値として読み、条件を満たせば `--layer-split` 引数にしてエンジンへ渡します。このツールの冒頭には、バッチグループ設定で交互に使う会話の prompt cache 再利用を確認する手順が記載されています。

## 値と判定

| 状況 | ツールの動作 |
|---|---|
| `GPUS` が未設定または空 | `if os.environ.get("GPUS")` が偽となり、このブロックを通らないため `SPLIT` は読みません。 |
| `GPUS` が空でない、`SPLIT` が未設定 | `os.environ.get("SPLIT", "auto")` により `"auto"` を `cfg["layer_split"]` に設定します。 |
| `GPUS` が空でない、`SPLIT` が設定済み | 値を文字列のまま `cfg["layer_split"]` に渡します。空文字も設定済みとして渡されます。 |

エンジン引数へ変換されるとき、未設定値 `None`、空文字（空白だけを含む場合も含む）、および大文字小文字を区別しない `auto` は `--layer-split auto` になります。その他は、カンマ区切りの整数として処理されます。整数要素の前後の空白は除去されます。各要素は 2 以上で、後続要素は直前より大きくなければなりません。複数 GPU の場合は、GPU 数より 1 個少ない整数が必要です。helper にはモデルの層数に対する上限検査はありません。出力では整数をカンマで連結します。

たとえば 2 GPU で `SPLIT=24` は `--layer-split 24` になり、4 GPU で `SPLIT=24,36,42` は同じ値の `--layer-split` 引数になります。これは各後続 GPU が担当する最初の layer 番号であり、各 GPU の layer 数ではありません。数値変換に失敗した場合、要素数が GPU 数と合わない場合、または値が 2 から昇順にならない場合、`layer_split_value()` は形式説明付きの `ValueError` を送出します。このスクリプトはその箇所で例外を捕捉しないため、エンジン起動より前にスクリプトが失敗します。

根拠: `tools/batch_groups_cache_test.py:28-31`, `serve/server.py:3178-3208`。

## 有効になる条件

- この読み取りは `tools/batch_groups_cache_test.py` を実行したときだけ発生します。通常の Strata サーバー起動やエンジン本体が `SPLIT` を読む実装は見つかりませんでした。
- `GPUS` が空でないときだけ `SPLIT` を読みます。`GPUS` はカンマ区切りの整数へ変換され、複数 GPU で、かつ設定引数に `--peer-device` がなければ `layer_split_of()` は layer split と判定します。
- `cfg["args"]` にすでに `--layer-split` がある場合、`engine_args()` は `layer_split_value()` を呼ばず、環境変数から作った `cfg["layer_split"]` をエンジン引数へ追加しません。この場合、既存の `--layer-split` がそのまま残ります。
- `GPUS` が空でない場合でも、GPU が 1 枚だけ、または設定引数に `--peer-device` があるときは `--layer-split` の自動追加条件を満たしません。

## 実行時の詳細

スクリプトは起動時に `GPUS` を確認し、真の場合だけ `SPLIT` を読みます。設定値を `engine_args(cfg)` に渡し、その戻り値に `STRATA_EXTRA_ARGS` の分割結果を追加した後、`StrataEngine` を構築します。従って `SPLIT` はこのスクリプトが構成する起動引数に作用し、実行中に環境を変更して再評価するコードはありません。

`engine_args()` は複数 GPU かつ `--peer-device` なしの場合に `--layer-split` がまだなければ、検証・正規化した `layer_split_value(cfg)` を追加します。CLI 引数がすでにある場合の優先はこの追加条件で明示されています。無効な値は `ValueError` で起動前に表面化します。エンジン側で `--layer-split` がどう動作するかは、この変数の Strata 側の読み取り・転送動作とは別のため、ここでは説明しません。

根拠: `tools/batch_groups_cache_test.py:28-33`, `serve/server.py:3223-3226,3245-3287`。
