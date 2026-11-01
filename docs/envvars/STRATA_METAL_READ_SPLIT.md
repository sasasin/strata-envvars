# `STRATA_METAL_READ_SPLIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal の expert SSD streaming が、1 expert のファイル読み込みを何個の並行 read job に分割するかを指定します。`ExpertStream::open()` で値を読み、1〜8に clamp して `split_` に保存します。連続 expert sidecar（`<GGUF>.experts`）が使われる場合は expert 全体を指定数に分割します。sidecar が使われない場合は gate / up / down の各データ領域をそれぞれ指定数に分けるため、expert ごとの job 数は指定値の3倍です（`metal/src/engine/stream.cpp:27-30,149-150,272-300,335-345`）。

これは Strata の Metal streaming 経路の設定です。CUDA/HIP/SYCL や、Metal の resident 経路にはこのコードからは適用されません。

## 値と判定

共通 helper は `std::getenv()` で取得し、変数が未設定または空文字なら既定値を返します。それ以外は `std::atoi()` で整数変換し、その後 `[1, 8]` に clamp します。既定値は `1` です（`metal/src/engine/stream.cpp:27-30,150`）。

| 値 | helper の結果 | `split_` |
|---|---:|---:|
| 未設定、空文字 | 1（既定値） | 1 |
| `0`、負数 | 変換された整数 | 1（下限） |
| `1`〜`8` | 変換された整数 | その値 |
| `8`より大きい整数 | 変換された整数 | 8（上限） |
| 数字で始まらない非空文字列（例: `abc`） | `atoi` の結果 0 | 1 |

文字列全体の妥当性検査はありません。`atoi` の整数変換なので、先頭の空白や符号、数字の後ろの文字列は独立して検証されません（例: `  +4tail` は4として扱われます）。数値として変換できない文字列は0となり、下限 clamp により1です。CLI 引数や別の Strata 環境変数による上書きは、この読み取り箇所にはありません。

## 有効になる条件

- Metal の `Window::init()` が `ExpertStream::wanted()` の結果として streaming を選ぶことが必要です。streaming は `STRATA_METAL_STREAM=1` の明示指定時、または同変数が unset / auto 値で、GGUF の重みと余裕分が GPU working-set 上限に収まらないと判定された時に選ばれます。`STRATA_METAL_STREAM=0` なら resident 経路を選びます（`metal/src/engine/stream.cpp:33-48`; 呼び出しと stream 作成は `metal/src/engine/window.cpp:541-548`）。
- `Window::init()` は期待する Qwen3.8-Flash-Next の形状（48 layers 等）を検査します。不一致ならそこで失敗し、stream open に進みません（`metal/src/engine/window.cpp:524-532`）。
- streaming が選ばれても `ExpertStream::open()` が成功しなければ `STRATA_METAL_READ_SPLIT` の値は後続の read に使われません。変数自体に対する追加の OS / backend / build macro 判定はありません。対象実装は `metal/src/engine/` にあります。

## 実行時の詳細

値は stream open のたびに通常の関数呼び出しとして評価され、環境値の結果は当該 `ExpertStream` インスタンスの `split_` に保持されます。既存インスタンスでは open 後にプロセス環境を書き換えても再評価されず、新たに open する stream ではその時点の値が読み直されます（`metal/src/engine/stream.cpp:149-150`; stream の生成箇所は `metal/src/engine/window.cpp:543-548`）。

`submit()` は `split_`（sidecar 使用時）または `3 * split_`（GGUF から直接読む時）の `Job` を queue に積みます。各 job は対応する byte range を `pread` し、境界は 4096 byte 単位にそろえられます。read worker 数は別設定 `STRATA_METAL_IO_THREADS` から取得され、既定6、最低1です。したがって read split 数は queue に積む job 数を変えますが、同時 worker 数そのものは設定しません (`metal/src/engine/stream.cpp:149-150,272-305,307-333,335-345,481`).

読み込みに失敗すると stderr に `strata metal stream: reading expert %d of layer %d failed` を出して `exit(6)` します。空き slot がない経路も `strata metal stream: no free slot (layer %d)` を出して `exit(6)` します。これらは split 固有の警告ではなく、read/stream の失敗経路です（`metal/src/engine/stream.cpp:286-288,300-302,671-674`）。通常の診断レポートには window あたりの読み込み byte 数、read 数、待ち時間などが出ますが、`STRATA_METAL_READ_SPLIT` の値そのものを表示するログは見つかりません（`metal/src/engine/stream.cpp:803-821`）。

## 根拠

- 候補名の Strata 所有ソース全体検索で、実際の環境読み取りは `metal/src/engine/stream.cpp:150` の1箇所です。環境変数名を動的に helper へ渡す別の読み取り箇所は見つかりませんでした。
- 値変換 helper: `metal/src/engine/stream.cpp:27-30`。
- stream の適用判断と window からの呼び出し: `metal/src/engine/stream.cpp:33-48`, `metal/src/engine/window.cpp:524-548`。
- 分割 job と byte range の実装: `metal/src/engine/stream.cpp:272-305,335-345`。
- I/O thread 数と診断出力: `metal/src/engine/stream.cpp:149-150,481,803-821`。
