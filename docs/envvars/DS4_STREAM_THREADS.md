# `DS4_STREAM_THREADS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek 4.1（DS4）エンジンの PCIe lane が、ストリーミングする expert を pinned host staging に読み込むために作る reader pool のスレッド数を指定します。GPU 側の計算スレッド数ではありません。環境変数は `src/dsv41/ds4_model.cu` の `lane_setup_gpus()` で一度読み、値を `ln_readers` に保持して `Pool` の生成と起動ログに使います（`src/dsv41/ds4_model.cu:10420-10427,10457-10468,10635-10642`）。

## 値と判定

`std::atoi` で整数化した後、1〜8 に制限します。文字列全体の妥当性は検査しません。

| 値 | `ln_readers` |
|---|---:|
| 未設定 | 2 |
| `0`、空文字、整数に変換できない文字列 | 1 |
| 1〜8 に変換される整数 | その整数 |
| 8 より大きい整数 | 8 |
| 負の整数 | 1 |

`atoi` のため、先頭の空白や符号を含む整数、整数の後ろに文字が続く値は数値部分で変換されます（例: `4workers` は 4）。値が設定されていても数値に変換できなければ 0 となり、下限 clamp により 1 です。無効値について警告やエラーは出しません。読み取りと clamp は `src/dsv41/ds4_model.cu:10457-10458` にあります。

## 有効になる条件

この値は DS4 の PCIe lane 初期化に到達した場合だけ参照されます。lane の staging 確保は GGUF、`DS4_STREAM`（または `STRATA_DS4_STREAM`）が有効、MoE token 経路、同期 decode ではないことを条件とし、対象 layer に GPU に収まらない MXFP4 expert があることなども必要です。各 GPU の空き VRAM、既存の lane calibration、CUDA staging 確保結果によって lane が作られない場合もあります（`src/dsv41/ds4_model.cu:9711-9719,9722-9725,9753-9785`）。

`DS4_STREAM_THREADS` 自体に OS や GPU 世代による値判定分岐はありません。DS4 model 初期化は lane 確保後に `lane_setup()` を呼び、GPU lane の staging が一つもない場合は reader 数を読む前に戻ります（`src/dsv41/ds4_model.cu:3789-3792,10420-10427`）。この変数を上書きする CLI 引数や別環境変数は同箇所にはありません。`DS4_STREAM=2` は staging slot を保持しながら streaming しない試験経路ですが、lane setup に達すると reader pool 自体は作成されます（`src/dsv41/ds4_model.cu:9711-9719,10616-10623`）。

## 実行時の詳細

読み取りは model 初期化中の `lane_setup_gpus()` で一度だけです。プロセス中に環境を書き換えても再読み込みされません。値から作った `Pool` はその数の worker thread を生成します（`src/dsv41/ds4_model.cu:10457-10468`; `src/dsv41/ds4_pool.hpp:35-41`）。reader pool はストリーム対象 expert ごとの read job を処理し、job の完了を呼び出し側が待ちます（`src/dsv41/ds4_model.cu:9808-9829,9859-9882`; `src/dsv41/ds4_pool.hpp:53-56,78-85`）。

起動時の lane レポートには実際に採用された reader 数が `(%d reading threads; ...)` として出ます（`src/dsv41/ds4_model.cu:10635-10642`）。値が無効でもこの表示以外に値固有の警告はありません。staging の割り当て失敗時は `ds4: PCIe lane off: ...`、expert の読み込み失敗時は `ds4: PCIe lane: reading a streamed expert failed - that token went without it` が出る経路がありますが、これらは `DS4_STREAM_THREADS` の値判定によるエラーではありません（`src/dsv41/ds4_model.cu:10460-10465,9924,10026`）。

## 根拠

- 候補名の全参照は `src/dsv41/ds4_model.cu:9619`（説明コメント）と `src/dsv41/ds4_model.cu:10457`（唯一の実読み取り）です。汎用 helper や動的な名前渡しによる追加参照はありません。
- default、`atoi` 変換、clamp と pool への反映: `src/dsv41/ds4_model.cu:10457-10468`。
- reader pool の thread 生成と job 実行: `src/dsv41/ds4_pool.hpp:35-41,53-56,78-85`。
- lane の有効条件と初期化順: `src/dsv41/ds4_model.cu:3789-3792,9711-9719,9722-9725,9753-9785,10420-10427`。
- 起動ログ: `src/dsv41/ds4_model.cu:10635-10642`。
