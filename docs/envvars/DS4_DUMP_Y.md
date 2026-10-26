# `DS4_DUMP_Y`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 engine で、`run_set()` が処理する expert-set ごとの gate/up 中間値 `h` と down projection 結果 `y` をバイナリファイルへ出力する診断用フックです。ソースコメントは chunk path 用としていますが、`run_set()` は chunked prompt と layer/window 処理の両方から呼ばれます。設定値の形式は `<layer>:<file>` で、負の layer は全 layer を選びます。記録には layer、行範囲、expert 数、weight の格納場所が ring かどうか、行上限、expert-row 境界、`h`、`y` が含まれます。

この実装は通常の `strata` target ではなく、`STRATA_BUILD_DSV41` が有効なときに作られる独立実行ファイル `strata-dsv41` に含まれます。この CMake option は既定 OFF です（`STRATA_HIP_GFX906` の場合も target を作らない条件があります）。

## 値と判定

| 環境変数 | layer 選択値 | 出力ファイル | 結果 |
|---|---|---|---|
| 未設定 | `-1` | なし | FILE が開かれず、何も出力しない |
| `<整数>:<file>` | `atoi()` で読んだ整数 | 最初の `:` より後ろ全部 | 負数なら全 layer、0 以上ならその layer だけ |
| 設定あり、`:` なし | `atoi()` の結果 | なし | FILE が開かれず、何も出力しない |

`atoi()` は先頭の空白と符号を許し、数字列の後ろにある `:` などは変換対象外です。数字列が始まらない値（例: `x:/tmp/y.bin`）や空文字では layer 値は 0 になります。したがって `-1:/tmp/y.bin` は全 layer、`2:/tmp/y.bin` は layer 2、`0:/tmp/y.bin` は layer 0 を選びます。変換不能時の errno や範囲外の数値は検査していません。`:` の後ろが空、または `fopen()` に失敗した場合、FILE は null のままで記録されません。ファイルは `fopen(..., "wb")` で開くため、成功すると既存ファイルを切り詰めます。

## 有効になる条件

- `strata-dsv41` を含む build が必要です。通常の Strata executable にはこのコードは含まれません。
- `dump_y` が正常に開けていることが必要です。
- `run_set()` が expert を処理し、かつ layer が指定と一致する（または layer 指定が負数）区間で記録します。`run_set()` は chunked prompt の `layer_chunk()` と layer/window 処理の両方から呼ばれます。値を設定しても `run_set()` を通る処理がなければ記録されません。
- 指定 layer と一致しない場合、その `run_set()` は記録を飛ばします。実装に環境変数の読み取り失敗や書き込み失敗を報告する専用ログはありません。

## 実行時の詳細

`Model::Model()` が `Impl` を作る際に、`DS4_DUMP_Y` を読みます。layer は member 初期化時に `atoi()` で一度設定され、ファイルも同じ環境変数の最初のコロンより後ろを `fopen(..., "wb")` します。したがって、その `Model` の稼働中に環境変数を変更しても既存の layer 選択や FILE は更新されません。新しい `Model` instance はその生成時点の環境を読みます。

対象 layer の `run_set()` は、expert の gate/up と down kernel を stream に enqueue した後、stream を同期し、`c.h16` を F16 として、`c.y` を F32 として device-to-host copy します。mutex で保護しながら、6 個の int64 header (`layer`, `row0`, `rows`, `n_exp`, `wbase kind`, `max_rows`)、int32 の `n_exp + 1` 個の row bounds、`rows × ff` 個の F16 `h`、`rows × dim` 個の F32 `y` を順に書き、各 record の後で `fflush()` します。`wbase kind` は ring 内なら 1、それ以外は 0 です。この同期とファイル I/O は選択 layer の処理に追加されます。

`tools/dsv41/dumpcmp.py` の `read_y()` は同じ record 配列を読み、`dumpscan_y.py` や `dumpcmp.py` が解析に使います。値の受け渡しや子プロセスへの設定を行うコードは、この環境変数の直接参照では見つかりません。

## 根拠

- `src/dsv41/ds4_model.cu:1127-1144`: `DS4_DUMP_Y` の読み取り、layer の `atoi()`、最初のコロン以降を出力先にして `wb` で開く処理。
- `src/dsv41/ds4_model.cu:3535-3538,3577-3588,3596-3600,3649-3665,7400-7410`: chunked prompt と layer/window 処理から呼ばれる `run_set()`、layer 条件、同期・copy・record 出力。
- `src/dsv41/ds4_model.cu:9352`: `Model` 生成時に `Impl` を作る。
- `CMakeLists.txt:797-811`: `strata-dsv41` は `STRATA_BUILD_DSV41` で追加される独立 target で、option 既定値は OFF。
- `tools/dsv41/dumpcmp.py:58-75`: 出力 record の header、bounds、F16 `h`、F32 `y` を読むツール側形式。
- `docs/DETAILS.md` には `DS4_DUMP_Y` の説明や測定値は見当たらず、性能・正確性についての主張は記載していません。
