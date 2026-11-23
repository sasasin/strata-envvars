# `strata-hy4 --dump-dfly-out`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root） |
| オプション | `--dump-dfly-out` |
| 別名 | なし |
| 値 | 出力ディレクトリのパス（文字列） |

## 役割

`--dump-dfly-batch` による DFly バッチ生成で、生成データの保存先ディレクトリを指定します。このオプション単独では出力処理を有効にしません。バッチ指定がある場合、値が空でなければこのパスを使い、空または未指定なら `--out` の値（既定値 `.`）を使います（`engine/src/hy4flash/run/hy4_main.hip.cpp:347-348,368-370,421-424,707-708`）。

## 使い方

```sh
strata-hy4 --model model.strata --dump-dfly-batch prompts.txt --dump-dfly-out ./dfly-results
```

上の例では、バッチの結果を `./dfly-results` に保存します。モデルと runner の初期化後にバッチ処理へ進むため、出力先指定だけでモデルロードを省略することはできません（`engine/src/hy4flash/run/hy4_main.hip.cpp:613-616,658-665,692-708`）。

## 値と既定値

- 値は次の引数をそのまま文字列として受け取ります。数値変換やパス形式の検証は parser では行いません。値を省略すると `nxt()` が `ERR --dump-dfly-out needs a value` を標準出力に出し、終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383,422`）。
- 未指定時の内部値は空文字列です。バッチ処理では空文字列を `--out` の値に置き換えます。`--out` も未指定なら `.`（カレントディレクトリ）です（`engine/src/hy4flash/run/hy4_main.hip.cpp:347-348,368-369,707-708`）。
- 同じオプションを複数回指定すると、引数解析中に後の値で上書きされます（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-383,422`）。空文字列を最後に指定した場合は `--out` にフォールバックします。

## 実行時の動作

`--dump-dfly-batch` の値が空でない場合だけ、モデルと runner の初期化後に `run_dump_dfly_batch` が呼ばれます。その呼び出しに `--dump-dfly-out` が空でなければその値を、空なら `--out` を渡します。したがって `--dump-dfly-batch` を指定しない実行では、このオプションの値は保存処理に使われません（`engine/src/hy4flash/run/hy4_main.hip.cpp:421-424,658-665,692-708`）。

バッチ関数は出力ディレクトリを `std::filesystem::create_directories` で作成し、各 sequence を `<出力先>/seq_XXXX.bin` に書きます。ファイルは `fopen(..., "wb")` で開かれるため、同名ファイルがあれば上書きされます（`engine/src/hy4flash/run/hy4_main.hip.cpp:183-190,309-324`）。

## 適用条件と副作用

- 実際に参照されるのは `--dump-dfly-batch` が空でない場合だけです。バッチ経路は `--serve` の分岐より後に置かれ、モデルなしの実行は usage を出して終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-614,707-708`）。
- `--out` との優先順位は、`--dump-dfly-out` の値が空でない場合にそちらを使い、空なら `--out` を使う、です。両オプションの解析順ではなく、最終的に保持された値で決まります（`engine/src/hy4flash/run/hy4_main.hip.cpp:347-348,421-424,485,707-708`）。
- 出力先ディレクトリの作成と `seq_XXXX.bin` の生成・上書きが起きます。既存ファイルを保護する処理はありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:189,309-324`）。

## 出力とエラー

- バッチ処理開始時、入力 manifest、prompt 数、生成設定、出力先を標準エラーに表示します（`engine/src/hy4flash/run/hy4_main.hip.cpp:183-207`）。各 sequence の出力先と完了状況、および最後に集計を標準エラーへ表示します（同:327-331）。
- manifest を開けない場合は `dump-dfly-batch: cannot open ...` を標準エラーに出して 1 を返します。出力ファイルを開けない場合は `[dump-dfly] cannot write ...` を出して 1 を返します（同:184-188,309-315）。
- `create_directories` の失敗や `fwrite` / `fclose` のエラーは、この関数内で戻り値を検査する処理がありません（同:189,311-324）。それらの具体的な結果は、このソース範囲からは確認できません。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:347-370` — 出力先の初期値と `dump_dfly_out` の初期値。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-383,421-424` — 値の取得、値省略時のエラー、オプションの parser。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:613-665,692-708` — モデル・runner の初期化と、バッチ時の出力先選択および関数呼び出し。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:183-207,309-331` — 出力ディレクトリ作成、ファイル生成、診断出力と失敗経路。
